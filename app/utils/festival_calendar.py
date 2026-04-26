import holidays

indian_holidays = holidays.India()

def is_festival(date):
    return date in indian_holidays