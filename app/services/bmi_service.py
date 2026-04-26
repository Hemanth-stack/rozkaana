from typing import TYPE_CHECKING

from app.services.macro_scorer import calculate_targets

if TYPE_CHECKING:
    from app.models.user import User


def calculate_and_store_bmi(user: "User") -> "User":
    weight = float(user.weight_kg or 0)
    height_m = float(user.height_cm or 0) / 100

    if weight > 0 and height_m > 0:
        bmi = round(weight / (height_m ** 2), 2)
        user.bmi = bmi

        if bmi < 18.5:
            user.bmi_band = "underweight"
        elif bmi < 25.0:
            user.bmi_band = "normal"
        elif bmi < 30.0:
            user.bmi_band = "overweight"
        else:
            user.bmi_band = "obese"
    else:
        user.bmi = None
        user.bmi_band = None

    if user.age and user.gender and weight > 0 and height_m > 0:
        targets = calculate_targets(user)
        user.daily_calorie_target = targets["daily_calorie_target"]
        user.daily_protein_target_g = targets["daily_protein_target_g"]
        user.daily_carbs_target_g = targets["daily_carbs_target_g"]
        user.daily_fat_target_g = targets["daily_fat_target_g"]

    return user


def calculate_bmi(weight: float, height: float) -> float:
    height_m = height / 100
    if height_m <= 0:
        return 0.0
    return round(weight / (height_m ** 2), 2)
