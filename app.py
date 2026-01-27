"""
PancrePal - Diabetes Companion Web App
Iteration 4: Authentication + PWA Support
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

# SQLAlchemy configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pancrepal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import db after app is created
from db import db, User, LogEntry, UserProgress
from gamification import update_streak, check_and_award_badges, get_daily_tip, should_show_reminder

# Initialize database with app
db.init_app(app)

# Create tables if they don't exist
with app.app_context():
    db.create_all()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # Validation
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html')

        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'error')
            return render_template('register.html')

        # Create user
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Create user progress record
        progress = UserProgress(user_id=user.id)
        db.session.add(progress)
        db.session.commit()

        login_user(user)
        flash('Account created successfully! Welcome to PancrePal.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Welcome back!', 'success')

            # Redirect to next page if specified, otherwise dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Log out current user."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ============================================================================
# MAIN APPLICATION ROUTES
# ============================================================================

@app.route('/')
@login_required
def index():
    """Dashboard - main page showing glucose trends and insights."""
    user_id = current_user.id

    # Get recent entries (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= seven_days_ago
    ).order_by(LogEntry.timestamp.desc()).all()

    # Get user progress
    progress = UserProgress.query.filter_by(user_id=user_id).first()
    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    # Check and update streak for today
    if entries:
        today = datetime.now().date()
        latest_entry_date = entries[0].timestamp.date()
        if latest_entry_date == today:
            update_streak(user_id, today)

    # Get daily tip
    daily_tip = get_daily_tip()

    # Check if reminder should be shown
    reminder = should_show_reminder(user_id)

    # Prepare chart data
    chart_data = {
        'labels': [],
        'glucose': [],
        'mood': []
    }

    for entry in reversed(entries):  # Oldest to newest for chart
        chart_data['labels'].append(entry.timestamp.strftime('%a %d'))
        chart_data['glucose'].append(entry.blood_glucose)
        # Convert mood to numeric
        mood_map = {'happy': 5, 'calm': 4, 'stressed': 3, 'tired': 2, 'frustrated': 1}
        chart_data['mood'].append(mood_map.get(entry.mood, 3))

    # Simple insights
    insights = {}
    if entries:
        avg_glucose = sum(e.blood_glucose for e in entries) / len(entries)
        insights['average'] = round(avg_glucose, 1)
        insights['count'] = len(entries)

    return render_template(
        'index.html',
        entries=entries,
        progress=progress.to_dict(),
        insights=insights,
        daily_tip=daily_tip,
        chart_data=chart_data,
        reminder=reminder
    )


@app.route('/log', methods=['GET', 'POST'])
@login_required
def log_entry():
    """Quick log page for adding glucose entries."""
    if request.method == 'POST':
        user_id = current_user.id
        glucose_level = request.form.get('glucose_level')
        meal_type = request.form.get('meal_type', 'none')
        mood = request.form.get('mood')
        notes = request.form.get('notes', '').strip()

        # Validation
        if not glucose_level or not mood:
            flash('Glucose level and mood are required.', 'error')
            return render_template('log.html')

        try:
            glucose_level = float(glucose_level)
            if glucose_level < 2.0 or glucose_level > 30.0:
                flash('Glucose level must be between 2.0 and 30.0 mmol/L.', 'error')
                return render_template('log.html')
        except ValueError:
            flash('Invalid glucose level.', 'error')
            return render_template('log.html')

        # Add entry
        entry = LogEntry(
            user_id=user_id,
            blood_glucose=glucose_level,
            meal_type=meal_type,
            mood=mood,
            notes=notes
        )
        db.session.add(entry)
        db.session.commit()

        # Update streak with today's date
        today = datetime.now().date()
        update_streak(user_id, today)

        # Get user progress to check for new badges
        progress = UserProgress.query.filter_by(user_id=user_id).first()
        if progress:
            newly_earned = check_and_award_badges(progress)

            # Flash message for badges
            if newly_earned:
                for badge in newly_earned:
                    flash(f'🏆 Badge earned: {badge["name"]}!', 'success')

        flash('Entry logged successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('log.html')


@app.route('/avatar')
@login_required
def avatar():
    """Avatar customization page."""
    user_id = current_user.id
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    # Get available avatars (basic set always available)
    available_avatars = ['default']

    # Add unlocked avatars
    unlocked = progress.get_unlocked_avatars()
    available_avatars.extend([a for a in unlocked if a != 'default'])

    return render_template('avatar.html', progress=progress.to_dict(), avatars=available_avatars)


@app.route('/avatar/update', methods=['POST'])
@login_required
def update_avatar():
    """Update user's avatar selection."""
    user_id = current_user.id
    avatar_id = request.form.get('avatar_id')

    if avatar_id:
        progress = UserProgress.query.filter_by(user_id=user_id).first()
        if progress:
            progress.selected_avatar = avatar_id
            db.session.commit()
            flash('Avatar updated!', 'success')

    return redirect(url_for('avatar'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page."""
    if request.method == 'POST':
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))

    user_id = current_user.id
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    return render_template('settings.html', progress=progress.to_dict())


@app.route('/ethics')
def ethics():
    """Data Ethics & Privacy page - accessible without login."""
    return render_template('ethics.html')


# ============================================================================
# API ROUTES (for future mobile app integration)
# ============================================================================

@app.route('/api/entries', methods=['GET'])
@login_required
def api_entries():
    """API endpoint to get user's entries."""
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).order_by(LogEntry.timestamp.desc()).all()

    return jsonify([e.to_dict() for e in entries])


@app.route('/api/progress', methods=['GET'])
@login_required
def api_progress():
    """API endpoint to get user's progress."""
    user_id = current_user.id
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        return jsonify({'error': 'No progress found'}), 404

    return jsonify(progress.to_dict())


# ============================================================================
# PWA ROUTES - USER STORY 18
# ============================================================================

@app.route('/manifest.json')
def manifest():
    """Serve PWA manifest file."""
    return send_from_directory('static', 'manifest.json')


@app.route('/service-worker.js')
def service_worker():
    """Serve service worker file."""
    return send_from_directory('static', 'service-worker.js')


@app.route('/apple-touch-icon.png')
def apple_touch_icon():
    """Serve Apple touch icon for iOS."""
    return send_from_directory('static/icons', 'icon-192x192.png')


@app.route('/favicon.ico')
def favicon():
    """Serve favicon."""
    return send_from_directory('static/icons', 'icon-192x192.png')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
else:
    with app.app_context():
        db.create_all()