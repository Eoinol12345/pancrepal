"""
Seed script for PancrePal database - Iteration 4
Generates realistic sample data for testing and demonstration
"""
import random
from datetime import datetime, timedelta, timezone
from app import app, db
from db import User, LogEntry, UserProgress
from gamification import update_streak

print("🌱 Starting database seed...")

# Create application context
with app.app_context():
    # Get or create a user
    print("👤 Checking for existing user...")
    user = User.query.first()

    if not user:
        print("❌ No user found! Please run migrate_to_iteration4.py first to create a user.")
        print("   Then log in at least once before running seed.py")
        exit(1)

    user_id = user.id
    print(f"✅ Using user: {user.email} (ID: {user_id})")

    # Clear existing data for this user
    print("📝 Clearing existing data...")
    LogEntry.query.filter_by(user_id=user_id).delete()

    # Get or create user progress
    progress = UserProgress.query.filter_by(user_id=user_id).first()
    if progress:
        # Reset progress
        progress.current_streak = 0
        progress.longest_streak = 0
        progress.total_logs = 0
        progress.last_log_date = None
    else:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)

    db.session.commit()

    print("✨ Generating sample log entries...")

    # Define realistic options
    meal_types = ['breakfast', 'lunch', 'dinner', 'snack', 'none']
    moods = ['happy', 'calm', 'stressed', 'tired', 'frustrated']

    # Sample notes for variety
    sample_notes = [
        "Felt great after this meal",
        "Had a big portion",
        "Exercised before eating",
        "Forgot to take insulin on time",
        "Stressed about exams",
        "Slept well last night",
        "Had a snack at school",
        None,  # Some entries have no notes
        None,
        None
    ]

    # Get today's date (timezone-aware)
    today = datetime.now(timezone.utc).date()

    # Generate 7 days of data with varying entries per day
    entries_created = 0

    for day_offset in range(7):
        # Calculate the date (going backwards from today)
        entry_date = today - timedelta(days=6 - day_offset)

        # Vary number of entries per day (3-5 entries per day for realism)
        num_entries = random.randint(3, 5)

        for entry_num in range(num_entries):
            # Generate realistic blood glucose values (mmol/L)
            # Weighted distribution: more likely to be in normal range
            if random.random() < 0.6:  # 60% in normal range (3.9-10.0)
                blood_glucose = round(random.uniform(4.4, 7.8), 1)
            elif random.random() < 0.3:  # 30% slightly high (10.0-11.1)
                blood_glucose = round(random.uniform(7.8, 11.1), 1)
            else:  # 10% low or very high (3.3-13.9)
                blood_glucose = round(random.uniform(3.3, 13.9), 1)

            # Determine meal type based on time of day
            hour = 6 + (entry_num * 4) + random.randint(0, 2)  # Spread throughout day
            if hour < 10:
                meal_type = 'breakfast'
            elif hour < 14:
                meal_type = 'lunch'
            elif hour < 17:
                meal_type = 'snack'
            elif hour < 21:
                meal_type = 'dinner'
            else:
                meal_type = random.choice(meal_types)

            # Create timestamp for this entry (timezone-aware)
            timestamp = datetime.combine(
                entry_date,
                datetime.min.time()
            ).replace(tzinfo=timezone.utc) + timedelta(hours=hour, minutes=random.randint(0, 59))

            # Create entry
            entry = LogEntry(
                user_id=user_id,  # Associate with user
                blood_glucose=blood_glucose,
                meal_type=meal_type,
                mood=random.choice(moods),
                notes=random.choice(sample_notes),
                timestamp=timestamp
            )

            db.session.add(entry)
            entries_created += 1

        # Commit entries for this day
        db.session.commit()

        # Update streak for each day (FIXED: now passes both user_id and date)
        update_streak(user_id, entry_date)

    print(f"✅ Seed complete!")
    print(f"   📊 {entries_created} log entries created")
    print(f"   📅 7 days of data generated")
    print(f"   🔥 Streak updated")

    # Show summary statistics
    total_logs = LogEntry.query.filter_by(user_id=user_id).count()
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    print("\n📈 Summary:")
    print(f"   Total logs in database: {total_logs}")
    if progress:
        print(f"   Current streak: {progress.current_streak} days")
        print(f"   Longest streak: {progress.longest_streak} days")
        print(f"   Total logs tracked: {progress.total_logs}")

        # Show badges earned
        if progress.badges_earned:
            badges = progress.badges_earned.split(',')
            print(f"   Badges earned: {len(badges)}")
            for badge_id in badges:
                if badge_id:
                    print(f"      - {badge_id}")

    print("\n🎉 Database seeded successfully!")
    print(f"   User: {user.email}")
    print("   Visit http://localhost:5002 to see your data!")