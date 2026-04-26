from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.recipe import Recipe


def check_variety(menu: dict) -> bool:
    recipes = [r for r in menu.values() if r is not None]
    ingredients = [getattr(r, "main_ingredient", None) for r in recipes if hasattr(r, "main_ingredient")]
    unique = set(i for i in ingredients if i)
    return len(unique) >= len(ingredients) * 0.6
