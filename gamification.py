from datetime import datetime, date, timedelta
from db import db, UserProgress, LogEntry, BADGES, AVATAR_STYLES
import random


# ============================================================================
# PROGRESS TRACKING
# ============================================================================

def get_or_create_user_progress(user_id: int) -> UserProgress:
    """
    Get the user's progress record, creating one if it doesn't exist.

    Args:
        user_id: ID of the user

    Returns:
        UserProgress object for the user
    """
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    return progress


def update_streak(user_id: int, log_date: date):
    """
    Update the user's logging streak based on new entry.

    Streak rules:
    - Increments if logged today or yesterday
    - Resets if gap > 1 day (but we don't shame the user!)

    Args:
        user_id: ID of the user
        log_date: Date of the new log entry
    """
    progress = get_or_create_user_progress(user_id)
    today = date.today()

    # First log ever
    if not progress.last_log_date:
        progress.current_streak = 1
        progress.longest_streak = 1
        progress.last_log_date = log_date
        progress.total_logs = 1
        db.session.commit()
        check_and_award_badges(progress)
        return

    # Calculate days since last log
    days_since_last = (log_date - progress.last_log_date).days

    if days_since_last == 0:
        # Same day, just increment total logs
        progress.total_logs += 1
    elif days_since_last == 1:
        # Consecutive day - increment streak
        progress.current_streak += 1
        progress.total_logs += 1

        # Update longest streak if necessary
        if progress.current_streak > progress.longest_streak:
            progress.longest_streak = progress.current_streak
    else:
        # Streak broken - reset (but keep longest streak for motivation)
        progress.current_streak = 1
        progress.total_logs += 1

    progress.last_log_date = log_date
    db.session.commit()

    # Check for newly earned badges
    check_and_award_badges(progress)


def check_and_award_badges(progress: UserProgress):
    """
    Check if user has earned any new badges and award them.

    Triggers avatar unlocks if applicable.

    Args:
        progress: UserProgress object
    """
    newly_earned = []

    # Check streak-based badges
    if progress.current_streak >= 3 and not progress.has_badge('streak_3'):
        progress.add_badge('streak_3')
        newly_earned.append(BADGES['streak_3'])

    if progress.current_streak >= 7 and not progress.has_badge('streak_7'):
        progress.add_badge('streak_7')
        newly_earned.append(BADGES['streak_7'])
        # Unlock space avatar
        progress.unlock_avatar('space')

    if progress.current_streak >= 30 and not progress.has_badge('streak_30'):
        progress.add_badge('streak_30')
        newly_earned.append(BADGES['streak_30'])
        # Unlock rainbow avatar
        progress.unlock_avatar('rainbow')

    # Check total log badges
    if progress.total_logs >= 1 and not progress.has_badge('first_log'):
        progress.add_badge('first_log')
        newly_earned.append(BADGES['first_log'])

    if progress.total_logs >= 50 and not progress.has_badge('logs_50'):
        progress.add_badge('logs_50')
        newly_earned.append(BADGES['logs_50'])
        # Unlock nature avatar
        progress.unlock_avatar('nature')

    if progress.total_logs >= 100 and not progress.has_badge('logs_100'):
        progress.add_badge('logs_100')
        newly_earned.append(BADGES['logs_100'])

    db.session.commit()
    return newly_earned


def calculate_weekly_consistency(user_id: int) -> float:
    """
    Calculate what percentage of the past 7 days have logs.

    Used for progress bar visualization.

    Args:
        user_id: ID of the user

    Returns:
        Percentage (0-100) of days with at least one log
    """
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= seven_days_ago
    ).all()

    if not entries:
        return 0.0

    # Get unique dates
    unique_dates = set(e.timestamp.date() for e in entries)

    # Calculate percentage
    consistency = (len(unique_dates) / 7) * 100
    return round(consistency, 1)


# ============================================================================
# TIP OF THE DAY
# ============================================================================

TIPS = [
    {
        'category': 'glucose',
        'tip': '💧 Staying hydrated helps keep blood sugar stable. Aim for 8 glasses of water daily!'
    },
    {
        'category': 'mood',
        'tip': '🧘 Stress can affect glucose levels. Try 5 deep breaths when you feel overwhelmed.'
    },
    {
        'category': 'food',
        'tip': '🥗 Pairing carbs with protein or healthy fats slows glucose spikes. Try adding nuts to your snacks!'
    },
    {
        'category': 'activity',
        'tip': '🚶 Even a 10-minute walk after meals can help lower post-meal glucose.'
    },
    {
        'category': 'sleep',
        'tip': '😴 Good sleep improves insulin sensitivity. Aim for 8-9 hours as a teen!'
    },
    {
        'category': 'logging',
        'tip': '📝 The more you log, the better you understand your patterns. Every entry helps!'
    },
    {
        'category': 'timing',
        'tip': '⏰ Checking glucose at the same times daily (like before meals) helps spot trends.'
    },
    {
        'category': 'support',
        'tip': '💙 Managing diabetes is a team effort. Don\'t hesitate to reach out to your care team.'
    },
    {
        'category': 'celebration',
        'tip': '🎉 Celebrate your wins! Every day you log is a step toward understanding your body better.'
    },
    {
        'category': 'flexibility',
        'tip': '🌈 Some days will be harder than others, and that\'s okay. Progress isn\'t always linear.'
    }
]


def get_daily_tip() -> dict:
    """
    Get tip of the day based on date seed for consistency.

    Uses date as random seed so same tip shows all day.

    Returns:
        Dictionary with tip content and category
    """
    # Use today's date as seed for consistent daily tip
    today = date.today()
    seed = int(today.strftime('%Y%m%d'))
    random.seed(seed)

    tip = random.choice(TIPS)

    # Reset random seed
    random.seed()

    return tip


# ============================================================================
# REMINDER SYSTEM (Placeholder)
# ============================================================================

def set_reminder_preference(user_id: int, time_str: str, enabled: bool):
    """
    Set user's reminder preferences.

    Note: Actual reminder implementation would require:
    - Background task scheduler (Celery, APScheduler)
    - Browser notifications API or email integration

    This is a placeholder for the database structure.

    Args:
        user_id: ID of the user
        time_str: Time string in HH:MM format
        enabled: Whether reminders are enabled
    """
    progress = get_or_create_user_progress(user_id)

    if time_str:
        from datetime import datetime
        reminder_time = datetime.strptime(time_str, '%H:%M').time()
        progress.reminder_time = reminder_time

    progress.reminders_enabled = enabled
    db.session.commit()


def get_gentle_reminder_message() -> str:
    """
    Generate a gentle, non-intrusive reminder message.

    Returns:
        Encouraging reminder text
    """
    messages = [
        "Hi! Just a friendly reminder to log your glucose when you get a chance. 💙",
        "No pressure, but logging today helps keep your streak going! 🌟",
        "Your future self will thank you for logging today. ✨",
        "Quick check-in time! Let's log together. 🥞",
        "Remember: Every log teaches you something about your body. 📊"
    ]

    return random.choice(messages)


def should_show_reminder(user_id: int) -> dict:
    """
    Check if user should see a reminder to log today.

    Args:
        user_id: ID of the user

    Returns:
        Dictionary with:
        - show: Boolean indicating if reminder should be shown
        - message: The reminder message to display
        - time_based: Boolean indicating if it's past the user's preferred time
    """
    progress = get_or_create_user_progress(user_id)

    # Check if reminders are enabled
    if not progress.reminders_enabled:
        return {
            'show': False,
            'message': None,
            'time_based': False
        }

    # Check if user has logged today
    today = date.today()
    has_logged_today = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        db.func.date(LogEntry.timestamp) == today
    ).first() is not None

    if has_logged_today:
        return {
            'show': False,
            'message': None,
            'time_based': False
        }

    # User hasn't logged today - check if it's past their preferred time
    time_based = False
    if progress.reminder_time:
        current_time = datetime.now().time()
        if current_time >= progress.reminder_time:
            time_based = True

    return {
        'show': True,
        'message': get_gentle_reminder_message(),
        'time_based': time_based
    }