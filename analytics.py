from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional
from db import LogEntry

# ============================================================================
# GLUCOSE RANGES (mmol/L)
# ============================================================================
GLUCOSE_TARGET_MIN = 3.9
GLUCOSE_TARGET_MAX = 10.0
GLUCOSE_HIGH_THRESHOLD = 11.1
GLUCOSE_LOW_THRESHOLD = 3.3


# ============================================================================
# TREND ANALYSIS FUNCTIONS
# ============================================================================

def analyze_weekly_trend(entries: List[LogEntry]) -> Dict:
    """
    Analyze glucose patterns over the past week.

    Returns insights about:
    - Average glucose level
    - Time-in-range percentage
    - Consistency score
    - Overall trend (improving/stable/needs attention)

    Args:
        entries: List of LogEntry objects from the past 7 days

    Returns:
        Dictionary containing analysis results and encouraging message
    """
    if not entries:
        return {
            'status': 'no_data',
            'message': "Start logging to see your personalized insights!",
            'icon': '📊'
        }

    # Calculate key metrics
    glucose_values = [e.blood_glucose for e in entries]
    avg_glucose = sum(glucose_values) / len(glucose_values)

    # Time in range calculation
    in_range = [g for g in glucose_values if GLUCOSE_TARGET_MIN <= g <= GLUCOSE_TARGET_MAX]
    time_in_range = (len(in_range) / len(glucose_values)) * 100

    # Variability (standard deviation as proxy for consistency)
    variance = sum((x - avg_glucose) ** 2 for x in glucose_values) / len(glucose_values)
    std_dev = variance ** 0.5
    consistency_score = max(0, 100 - (std_dev / 2))  # Lower std_dev = higher consistency

    # Determine overall trend and generate encouraging message
    if time_in_range >= 70 and consistency_score >= 70:
        return {
            'status': 'excellent',
            'message': '🌟 Amazing work this week! Your glucose levels show great consistency.',
            'icon': '🎉',
            'time_in_range': round(time_in_range, 1),
            'avg_glucose': round(avg_glucose, 1),
            'consistency': round(consistency_score, 1)
        }
    elif time_in_range >= 50:
        return {
            'status': 'good',
            'message': '💪 You\'re doing well! Keep up the steady progress.',
            'icon': '✨',
            'time_in_range': round(time_in_range, 1),
            'avg_glucose': round(avg_glucose, 1),
            'consistency': round(consistency_score, 1)
        }
    else:
        return {
            'status': 'needs_attention',
            'message': '🤗 We see you\'re working on it. Every log helps you understand patterns better!',
            'icon': '💙',
            'time_in_range': round(time_in_range, 1),
            'avg_glucose': round(avg_glucose, 1),
            'consistency': round(consistency_score, 1)
        }


def identify_recurring_patterns(entries: List[LogEntry]) -> List[Dict]:
    """
    Identify recurring high or low glucose patterns by time and meal type.

    Looks for patterns like:
    - "You often see highs after dinner"
    - "Morning readings tend to be in range"

    Args:
        entries: List of LogEntry objects

    Returns:
        List of pattern dictionaries with supportive messaging
    """
    if len(entries) < 3:  # Need minimum data for pattern detection
        return []

    patterns = []

    # Group by meal type
    meal_groups = defaultdict(list)
    for entry in entries:
        meal_groups[entry.meal_type].append(entry.blood_glucose)

    # Analyze each meal type
    for meal_type, glucose_values in meal_groups.items():
        if len(glucose_values) < 2:
            continue

        avg = sum(glucose_values) / len(glucose_values)
        high_count = sum(1 for g in glucose_values if g > GLUCOSE_HIGH_THRESHOLD)
        low_count = sum(1 for g in glucose_values if g < GLUCOSE_LOW_THRESHOLD)

        # Pattern: Consistent highs after a meal
        if high_count >= len(glucose_values) * 0.6:  # 60%+ highs
            patterns.append({
                'type': 'recurring_high',
                'context': meal_type,
                'message': f'📈 You often see higher readings after {meal_type}. Consider checking portion sizes or insulin timing.',
                'severity': 'info'
            })

        # Pattern: Consistent lows
        elif low_count >= len(glucose_values) * 0.5:  # 50%+ lows
            patterns.append({
                'type': 'recurring_low',
                'context': meal_type,
                'message': f'⚠️ You\'ve had some lows around {meal_type} time. Let\'s keep an eye on this pattern together.',
                'severity': 'warning'
            })

        # Pattern: Good consistency
        elif GLUCOSE_TARGET_MIN <= avg <= GLUCOSE_TARGET_MAX:
            patterns.append({
                'type': 'in_range',
                'context': meal_type,
                'message': f'✅ Great job keeping {meal_type} readings in range!',
                'severity': 'success'
            })

    return patterns[:3]  # Return top 3 patterns to avoid overwhelming


def generate_weekly_suggestion(entries: List[LogEntry]) -> Optional[str]:
    """
    Generate a proactive, actionable suggestion based on weekly patterns.

    Suggestions are:
    - Specific and actionable
    - Non-judgmental and supportive
    - Based on observable patterns

    Args:
        entries: List of LogEntry objects

    Returns:
        Suggestion string or None if insufficient data
    """
    if len(entries) < 5:
        return None

    # Analyze time-of-day patterns
    morning_entries = [e for e in entries if 5 <= e.timestamp.hour < 12]
    evening_entries = [e for e in entries if 18 <= e.timestamp.hour < 23]

    # Check for breakfast skipping (few morning logs)
    if len(morning_entries) < len(entries) * 0.2:
        return "💡 Try logging breakfast readings more consistently. Morning data helps spot patterns!"

    # Check for late-night highs
    if evening_entries:
        evening_avg = sum(e.blood_glucose for e in evening_entries) / len(evening_entries)
        if evening_avg > GLUCOSE_HIGH_THRESHOLD:
            return "🌙 Your evening readings tend to run high. Consider an earlier dinner or checking bedtime insulin."

    # Check meal diversity
    meal_types = set(e.meal_type for e in entries)
    if len(meal_types) < 3:
        return "🍽️ Varying your meal types helps build a complete picture of your patterns."

    # Check for mood patterns with highs
    stressed_highs = [e for e in entries if e.mood == 'stressed' and e.blood_glucose > GLUCOSE_HIGH_THRESHOLD]
    if len(stressed_highs) >= 3:
        return "💙 Stress might be affecting your glucose. Try some deep breathing when levels spike!"

    # Default encouraging message
    return "⭐ You're building great habits! Keep logging to unlock more personalized insights."


def calculate_consistency_streak(entries: List[LogEntry]) -> int:
    """
    Calculate the current logging streak (consecutive days with at least one log).

    Used for gamification in Iteration 3, but foundation laid here.

    Args:
        entries: All LogEntry objects ordered by timestamp desc

    Returns:
        Number of consecutive days with logs
    """
    if not entries:
        return 0

    # Get unique dates
    log_dates = sorted(set(e.timestamp.date() for e in entries), reverse=True)

    if not log_dates:
        return 0

    # Count consecutive days starting from most recent
    streak = 1
    for i in range(len(log_dates) - 1):
        days_diff = (log_dates[i] - log_dates[i + 1]).days
        if days_diff == 1:
            streak += 1
        else:
            break

    return streak


# ============================================================================
# MOOD-GLUCOSE CORRELATION (Advanced Insight)
# ============================================================================

def analyze_mood_glucose_correlation(entries: List[LogEntry]) -> Optional[Dict]:
    """
    Identify if certain moods correlate with glucose levels.

    This provides emotional support by validating the mind-body connection.

    Args:
        entries: List of LogEntry objects

    Returns:
        Correlation insight or None if insufficient data
    """
    if len(entries) < 10:
        return None

    mood_glucose = defaultdict(list)
    for entry in entries:
        mood_glucose[entry.mood].append(entry.blood_glucose)

    # Find mood with highest average glucose
    mood_averages = {
        mood: sum(values) / len(values)
        for mood, values in mood_glucose.items()
        if len(values) >= 3
    }

    if not mood_averages:
        return None

    highest_mood = max(mood_averages, key=mood_averages.get)
    lowest_mood = min(mood_averages, key=mood_averages.get)

    # Only report if difference is meaningful (>1.7 mmol/L)
    if mood_averages[highest_mood] - mood_averages[lowest_mood] > 1.7:
        return {
            'high_mood': highest_mood,
            'low_mood': lowest_mood,
            'message': f'💭 Interesting: Your glucose tends to be higher when you\'re feeling {highest_mood}. Mind and body are connected!'
        }

    return None