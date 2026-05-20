from datetime import date


# Fixed-date festivals (month, day)
_FIXED_FESTIVALS: dict[tuple[int, int], str] = {
    (1, 1): "New Year",
    (1, 14): "Makar Sankranti",
    (1, 26): "Republic Day",
    (4, 14): "Baisakhi",
    (8, 15): "Independence Day",
    (10, 2): "Gandhi Jayanti",
    (12, 25): "Christmas",
    (12, 31): "New Year's Eve",
}

# Variable festivals indexed by (year, month, day)
_VARIABLE_FESTIVALS: dict[tuple[int, int, int], str] = {
    (2024, 11, 1): "Diwali",
    (2025, 10, 20): "Diwali",
    (2026, 11, 8): "Diwali",
    (2027, 10, 29): "Diwali",
    (2024, 3, 25): "Holi",
    (2025, 3, 14): "Holi",
    (2026, 3, 3): "Holi",
    (2027, 3, 22): "Holi",
    (2024, 4, 10): "Eid ul-Fitr",
    (2025, 3, 31): "Eid ul-Fitr",
    (2026, 3, 20): "Eid ul-Fitr",
    (2027, 3, 9): "Eid ul-Fitr",
    (2024, 6, 17): "Eid ul-Adha",
    (2025, 6, 7): "Eid ul-Adha",
    (2026, 5, 27): "Eid ul-Adha",
    (2024, 10, 3): "Navratri",
    (2025, 9, 22): "Navratri",
    (2026, 10, 11): "Navratri",
    (2024, 10, 12): "Durga Puja",
    (2025, 10, 2): "Durga Puja",
    (2026, 10, 20): "Durga Puja",
    (2024, 9, 7): "Ganesh Chaturthi",
    (2025, 8, 27): "Ganesh Chaturthi",
    (2026, 9, 14): "Ganesh Chaturthi",
    (2024, 9, 15): "Onam",
    (2025, 9, 5): "Onam",
    (2026, 8, 25): "Onam",
    (2024, 1, 15): "Pongal",
    (2025, 1, 14): "Pongal",
    (2026, 1, 14): "Pongal",
    (2024, 4, 9): "Ugadi",
    (2025, 3, 30): "Ugadi",
    (2026, 4, 18): "Ugadi",
    (2027, 4, 7): "Ugadi",
    (2024, 8, 19): "Raksha Bandhan",
    (2025, 8, 9): "Raksha Bandhan",
    (2026, 8, 28): "Raksha Bandhan",
    (2024, 8, 26): "Janmashtami",
    (2025, 8, 16): "Janmashtami",
    (2026, 9, 4): "Janmashtami",
    (2024, 3, 8): "Maha Shivratri",
    (2025, 2, 26): "Maha Shivratri",
    (2026, 2, 15): "Maha Shivratri",
    (2024, 11, 3): "Bhai Dooj",
    (2025, 10, 22): "Bhai Dooj",
    (2026, 11, 10): "Bhai Dooj",
}

FESTIVAL_CUISINE_MAP: dict[str, str] = {
    "Diwali": "north_indian",
    "Holi": "north_indian",
    "Eid ul-Fitr": "hyderabadi",
    "Eid ul-Adha": "hyderabadi",
    "Navratri": "sattvic",
    "Durga Puja": "bengali",
    "Ganesh Chaturthi": "maharashtrian",
    "Onam": "kerala",
    "Pongal": "tamil",
    "Ugadi": "andhra",
    "Janmashtami": "north_indian",
    "Ram Navami": "north_indian",
    "Maha Shivratri": "sattvic",
    "Makar Sankranti": "gujarati",
    "Baisakhi": "punjabi",
    "Christmas": "goan",
    "Raksha Bandhan": "north_indian",
}


def get_festival(d: date) -> str | None:
    variable = _VARIABLE_FESTIVALS.get((d.year, d.month, d.day))
    if variable:
        return variable
    return _FIXED_FESTIVALS.get((d.month, d.day))


def is_festival(d: date) -> bool:
    return get_festival(d) is not None
