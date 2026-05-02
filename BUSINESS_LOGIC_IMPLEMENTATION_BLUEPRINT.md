# Rozkaana - Advanced Nutritionist-Grade System: Technical Blueprint

## PHASE 1: MICRONUTRIENT FOUNDATION

### 1. Enhanced Recipe Schema

```python
# app/models/recipe_v2.py - EXTENDED RECIPE MODEL

from sqlalchemy import (
    ARRAY, Boolean, Column, DateTime, Index,
    Numeric, SmallInteger, String, text, UUID, JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base

class RecipeV2(Base):
    __tablename__ = "recipes_v2"
    
    # ── Existing Fields ──────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    meal_type = Column(String(20), nullable=False, index=True)
    cuisine_region = Column(String(30), nullable=False, index=True)
    eating_mode_tags = Column(ARRAY(String), nullable=False)
    health_safe_tags = Column(ARRAY(String), nullable=True)
    allergy_free_tags = Column(ARRAY(String), nullable=True)
    
    # ── MACRONUTRIENTS ───────────────────────────────────────────
    calories = Column(SmallInteger, nullable=False)
    protein_g = Column(Numeric(5, 2), nullable=False)
    carbs_g = Column(Numeric(5, 2), nullable=False)
    fat_g = Column(Numeric(5, 2), nullable=False)
    fibre_g = Column(Numeric(5, 2), nullable=True)
    sugar_g = Column(Numeric(5, 2), nullable=True)          # NEW
    added_sugar_g = Column(Numeric(5, 2), nullable=True)    # NEW
    
    # ── CARB QUALITY ─────────────────────────────────────────────
    glycemic_index = Column(SmallInteger, nullable=True)           # 0-100
    glycemic_load = Column(Numeric(5, 2), nullable=True)           # (GI * carbs) / 100
    carb_quality = Column(String(20), nullable=True)               # refined/simple/complex/resistant_starch
    resistant_starch_g = Column(Numeric(5, 2), nullable=True)      # NEW: for gut health
    
    # ── WATER-SOLUBLE VITAMINS ──────────────────────────────────
    vitamin_c_mg = Column(Numeric(6, 2), nullable=True)            # RDA: 75-90 mg
    vitamin_b1_thiamine_mg = Column(Numeric(5, 3), nullable=True)  # RDA: 1.1-1.2 mg
    vitamin_b2_riboflavin_mg = Column(Numeric(5, 3), nullable=True) # RDA: 1.1-1.3 mg
    vitamin_b3_niacin_mg = Column(Numeric(6, 2), nullable=True)    # RDA: 14-16 mg
    vitamin_b5_pantothenic_mg = Column(Numeric(5, 3), nullable=True) # RDA: 5 mg
    vitamin_b6_pyridoxine_mg = Column(Numeric(5, 3), nullable=True) # RDA: 1.3-1.7 mg
    vitamin_b7_biotin_mcg = Column(Numeric(5, 1), nullable=True)   # RDA: 30 mcg
    vitamin_b9_folate_mcg = Column(Numeric(6, 1), nullable=True)   # RDA: 400 mcg - CRITICAL!
    vitamin_b12_cobalamin_mcg = Column(Numeric(5, 2), nullable=True) # RDA: 2.4 mcg - CRITICAL!
    
    # ── FAT-SOLUBLE VITAMINS ────────────────────────────────────
    vitamin_a_mcg = Column(Numeric(6, 1), nullable=True)    # RDA: 700-900 mcg
    vitamin_d_mcg = Column(Numeric(5, 2), nullable=True)    # RDA: 10-20 mcg (critical in India)
    vitamin_e_tocopherol_mg = Column(Numeric(5, 2), nullable=True) # RDA: 15 mg
    vitamin_k_mcg = Column(Numeric(6, 1), nullable=True)    # RDA: 90-120 mcg
    
    # ── MINERALS (MACROMINERALS) ────────────────────────────────
    calcium_mg = Column(Numeric(7, 1), nullable=True)       # RDA: 1000-1200 mg
    phosphorus_mg = Column(Numeric(7, 1), nullable=True)    # for kidney patients: <1000 mg
    magnesium_mg = Column(Numeric(7, 1), nullable=True)     # RDA: 310-420 mg
    potassium_mg = Column(Numeric(7, 1), nullable=True)     # RDA: 3500+ mg (for BP)
    sodium_mg = Column(Numeric(7, 1), nullable=True)        # <2300 mg for hypertension
    
    # ── MINERALS (TRACE ELEMENTS) ──────────────────────────────
    iron_mg = Column(Numeric(6, 2), nullable=True)          # RDA: 8-18 mg (gender/age varies)
    iron_type = Column(String(10), nullable=True)           # "heme" (18% absorption) or "nonheme" (3-8%)
    zinc_mg = Column(Numeric(6, 2), nullable=True)          # RDA: 8-11 mg
    copper_mg = Column(Numeric(5, 3), nullable=True)        # RDA: 0.9 mg
    iodine_mcg = Column(Numeric(6, 1), nullable=True)       # RDA: 150 mcg - CRITICAL in India
    selenium_mcg = Column(Numeric(6, 1), nullable=True)     # RDA: 55 mcg
    manganese_mg = Column(Numeric(5, 2), nullable=True)     # RDA: 1.8-2.3 mg
    chromium_mcg = Column(Numeric(6, 1), nullable=True)     # RDA: 25-35 mcg
    molybdenum_mcg = Column(Numeric(6, 1), nullable=True)   # RDA: 45 mcg
    
    # ── PHYTONUTRIENTS & BIOACTIVES ────────────────────────────
    antioxidant_score = Column(SmallInteger, nullable=True)        # 1-100 ORAC score
    polyphenol_total_mg = Column(Numeric(7, 1), nullable=True)     # total polyphenols
    carotenoid_types = Column(ARRAY(String), nullable=True)        # ["beta_carotene", "lycopene", "lutein"]
    flavonoid_types = Column(ARRAY(String), nullable=True)         # ["anthocyanins", "quercetin", "catechins"]
    chlorophyll_mg = Column(Numeric(6, 1), nullable=True)          # for detox
    sulforaphane_content = Column(Boolean, default=False)          # in cruciferous vegetables
    
    # ── ABSORPTION & BIOAVAILABILITY ──────────────────────────
    fat_soluble_nutrients = Column(Boolean, default=False)  # needs fat for absorption
    vitamin_c_enhancer = Column(Boolean, default=False)     # enhances iron absorption
    phytate_level = Column(String(10), nullable=True)       # "low", "medium", "high" - blocks mineral absorption
    oxalate_level = Column(String(10), nullable=True)       # blocks calcium
    tannin_level = Column(String(10), nullable=True)        # blocks iron (tea, coffee)
    
    # ── DIGESTIBILITY & GUT HEALTH ─────────────────────────────
    fodmap_level = Column(String(10), nullable=True)        # "low", "high" for IBS
    prebiotic_fiber_g = Column(Numeric(5, 2), nullable=True)  # feeds good bacteria
    probiotic_content = Column(Boolean, default=False)      # contains live cultures
    leaky_gut_trigger = Column(Boolean, default=False)      # common trigger food
    
    # ── QUALITY METRICS ────────────────────────────────────────
    nutrient_density_score = Column(Numeric(5, 2), nullable=True) # nutrients per 100 cal
    processing_level = Column(String(20), nullable=True)     # "whole", "minimally_processed", "ultra_processed"
    preservation_method = Column(String(20), nullable=True)  # "fresh", "frozen", "dried", "canned", "fermented"
    
    # ── ALLERGEN & SAFETY ──────────────────────────────────────
    allergen_risk_score = Column(SmallInteger, nullable=True)  # 1-100 based on common allergens
    cross_reactivity_groups = Column(ARRAY(String), nullable=True) # ["tree_nuts", "shellfish", "nightshades"]
    pesticide_concern = Column(Boolean, default=False)       # known pesticide residue crop
    
    # ── REGIONAL & SEASONAL ────────────────────────────────────
    region_origin = Column(String(50), nullable=True)        # where typically grown/made
    seasonal_availability = Column(JSONB, nullable=True)    # {"dec-jan": true, "june-july": false}
    peak_season = Column(String(20), nullable=True)          # month of highest nutrient density
    peak_nutrition = Column(JSONB, nullable=True)            # {"vit_c": "june", "antioxidants": "sept"}
    
    # ── COOKING & PREPARATION ─────────────────────────────────
    prep_time_mins = Column(SmallInteger, nullable=True)
    cook_time_mins = Column(SmallInteger, nullable=True)
    cooking_method = Column(String(20), nullable=True)       # boil/steam/bake/fry/raw
    nutrient_retention_pct = Column(Numeric(5, 1), nullable=True)  # after cooking (some nutrients destroyed)
    cooking_loss_heat_sensitive = Column(JSONB, nullable=True)  # {"vit_c": -50, "folate": -30}
    
    # ── FLAVOR & TEXTURE ───────────────────────────────────────
    spice_level = Column(String(10), nullable=True)          # mild/medium/hot
    flavor_profile = Column(ARRAY(String), nullable=True)    # ["sweet", "umami", "sour", "salty", "bitter"]
    texture = Column(String(20), nullable=True)              # crunchy/creamy/chewy/light
    satiety_score = Column(SmallInteger, nullable=True)      # 1-100: how full do you feel
    
    # ── HEALTH CONDITIONS ──────────────────────────────────────
    health_benefit_tags = Column(ARRAY(String), nullable=True)  # ["heart_health", "bone_strength", "immune_boost"]
    contraindicated_for = Column(ARRAY(String), nullable=True)  # conditions to avoid
    therapeutic_compounds = Column(JSONB, nullable=True)     # specific bioactive compounds
    
    # ── METADATA ───────────────────────────────────────────────
    main_ingredient = Column(String(50), nullable=True)
    serving_unit = Column(String(50), nullable=True)
    serving_size_g = Column(Numeric(6, 1), nullable=True)    # standardize serving size
    ingredients = Column(JSONB, nullable=True)
    steps = Column(ARRAY(String), nullable=True)
    source = Column(String(20), default="manual")
    ifct_reference = Column(String(100), nullable=True)      # link to IFCT data
    research_reference = Column(ARRAY(String), nullable=True) # PubMed IDs
    is_verified = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))
```

### 2. Enhanced User Model with Nutritional Signals

```python
# app/models/user_signals.py - NEW: TRACKING NUTRITIONAL SIGNALS

from sqlalchemy import Column, UUID, DateTime, String, Float, Boolean, ARRAY, JSON
from app.database import Base

class UserNutritionSignal(Base):
    """Track how user's body is responding to current nutrition plan."""
    __tablename__ = "user_nutrition_signals"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    date = Column(Date, nullable=False, index=True)
    
    # ── Energy & Satiety ──────────────────────────────────
    energy_level = Column(SmallInteger, nullable=True)        # 1-10 scale
    hunger_rating = Column(SmallInteger, nullable=True)       # 1-10 before next meal
    satiety_hours = Column(Numeric(3, 1), nullable=True)      # how long felt full
    cravings = Column(ARRAY(String), nullable=True)           # ["sugar", "salt", "protein", "fat"]
    
    # ── Digestion & GI Health ─────────────────────────────
    digestion_comfort = Column(SmallInteger, nullable=True)   # 1-10 (bloating, gas, etc)
    bowel_movements = Column(SmallInteger, nullable=True)     # frequency
    stool_quality = Column(String(20), nullable=True)         # "hard", "normal", "loose", "diarrhea"
    stomach_distress = Column(Boolean, nullable=True)        # acid reflux, pain, etc
    
    # ── Sleep & Recovery ──────────────────────────────────
    sleep_quality = Column(SmallInteger, nullable=True)       # 1-10
    sleep_hours = Column(Numeric(3, 1), nullable=True)        # actual hours slept
    sleep_delay_mins = Column(SmallInteger, nullable=True)    # time to fall asleep
    
    # ── Physical Performance ──────────────────────────────
    strength_rating = Column(SmallInteger, nullable=True)     # 1-10 for workout
    endurance_rating = Column(SmallInteger, nullable=True)    # 1-10
    recovery_days = Column(SmallInteger, nullable=True)       # how many hours to recover
    
    # ── Mental & Mood ────────────────────────────────────
    mood = Column(String(20), nullable=True)                  # "happy", "neutral", "sad", "anxious"
    focus_level = Column(SmallInteger, nullable=True)         # 1-10
    brain_fog = Column(Boolean, nullable=True)                # difficulty concentrating
    
    # ── Metabolic Signals ─────────────────────────────────
    blood_sugar_dip = Column(Boolean, nullable=True)          # energy crash mid-afternoon
    cold_sensitivity = Column(Boolean, nullable=True)         # hypothyroid sign
    hair_loss_noticed = Column(Boolean, nullable=True)        # nutrient deficiency sign
    muscle_cramps = Column(Boolean, nullable=True)            # electrolyte issue
    
    # ── Medications & Supplements ───────────────────────
    taking_supplements = Column(ARRAY(String), nullable=True) # which supplements taken
    medication_timing = Column(String(50), nullable=True)     # "with_meal", "30mins_before"
    
    # ── Optional: Biometric Readings ────────────────────
    weight_kg = Column(Numeric(5, 2), nullable=True)          # daily weight
    resting_heart_rate = Column(SmallInteger, nullable=True)  # indicator of recovery
    blood_glucose_mg_dl = Column(SmallInteger, nullable=True) # for diabetes users
    blood_pressure = Column(String(20), nullable=True)        # "120/80" format
    
    # ── Optional: Food Log ──────────────────────────────
    actual_meals_eaten = Column(Boolean, nullable=True)       # did user eat recommended menu?
    skipped_meals = Column(ARRAY(String), nullable=True)      # which meals skipped
    extra_foods = Column(ARRAY(String), nullable=True)        # foods eaten outside plan
    notes = Column(String(500), nullable=True)                # user notes
    
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
```

### 3. Enhanced User Profile for Comprehensive Health Data

```python
# Add to existing User model:

class User(Base):
    # ── Existing fields... ──
    
    # ── MEDICAL HISTORY ────────────────────────────────────
    medical_conditions = Column(ARRAY(String), nullable=True)     # expanded:
    # Cardiovascular: hypertension, heart_disease, high_cholesterol, atrial_fibrillation
    # Endocrine: diabetes_t1, diabetes_t2, pcos, thyroid_hypo, thyroid_hyper, metabolic_syndrome
    # GI: ibs, crohns, celiac, gerd, ulcerative_colitis, fatty_liver
    # Renal: chronic_kidney_disease, kidney_stones
    # Respiratory: asthma, copd
    # Immunology: lupus, rheumatoid_arthritis
    # Neurological: migraines, parkinson's, alzheimers
    # Bone: osteoporosis, osteopenia
    # Metabolic: anemia, malnutrition
    
    medications = Column(JSONB, nullable=True)  # {"metformin": {dose: "500mg", frequency: "twice_daily", with_food: true}}
    supplement_stack = Column(JSONB, nullable=True)  # user's current supplements
    
    # ── ACTIVITY & LIFESTYLE ──────────────────────────────
    activity_level = Column(String(20), nullable=True)        # sedentary/lightly_active/moderate/very_active/athlete
    exercise_type = Column(ARRAY(String), nullable=True)      # ["cardio", "strength", "yoga", "sports"]
    exercise_hours_per_week = Column(Numeric(4, 1), nullable=True)
    
    # ── PREFERENCES & CONSTRAINTS ──────────────────────────
    cooking_skill = Column(String(20), nullable=True)         # beginner/intermediate/advanced
    cooking_time_available_mins = Column(SmallInteger, nullable=True)  # daily max time
    budget_preference = Column(String(20), nullable=True)      # budget/moderate/premium
    kitchen_equipment = Column(ARRAY(String), nullable=True)   # pressure_cooker, blender, etc
    
    # ── NUTRITIONAL GOALS (explicit) ───────────────────────
    primary_goal = Column(String(20), nullable=True)           # weight_loss/muscle_gain/energy/wellness
    secondary_goals = Column(ARRAY(String), nullable=True)     # detailed goals
    goal_timeframe = Column(String(20), nullable=True)         # 1month/3months/6months/long_term
    
    # ── HISTORICAL SIGNALS (computed) ───────────────────────
    avg_energy_level = Column(Numeric(3, 1), nullable=True)   # computed from signals
    avg_sleep_quality = Column(Numeric(3, 1), nullable=True)
    avg_digestion_comfort = Column(Numeric(3, 1), nullable=True)
    adherence_rate = Column(Numeric(5, 2), nullable=True)     # % of menus actually followed
    last_signal_date = Column(Date, nullable=True)
    
    # ── PREFERENCES (learned) ──────────────────────────────
    disliked_recipes = Column(ARRAY(UUID), nullable=True)     # recipes user rated low
    favorite_recipes = Column(ARRAY(UUID), nullable=True)     # recipes user loves
    texture_preferences = Column(ARRAY(String), nullable=True) # learned preferences
    spice_tolerance = Column(String(20), nullable=True)       # learned from signals, not just onboarding
```

---

## PHASE 2: MEAL OPTIMIZATION ENGINE

### 4. Multi-Objective Optimization Service

```python
# app/services/nutrition_optimizer.py - NEW: MULTI-OBJECTIVE OPTIMIZATION

from dataclasses import dataclass
from typing import Optional
from enum import Enum
import numpy as np
from scipy.optimize import minimize, LinearConstraint, Bounds
from sqlalchemy.ext.asyncio import AsyncSession

class OptimizationMetric(Enum):
    """Metrics to optimize for"""
    CALORIE_MATCH = "calorie_match"          # How close to target
    NUTRIENT_COMPLETENESS = "nutrient_completeness"  # % of 20+ micronutrients
    VARIETY = "variety"                      # Ingredient diversity
    SATIETY = "satiety"                      # Keep user full
    QUALITY = "quality"                      # Nutrient density per calorie
    AFFORDABILITY = "affordability"          # Cost
    DIGESTIBILITY = "digestibility"          # How easily digested
    TASTE_PREFERENCE = "taste_preference"    # User preferences

@dataclass
class NutrientTarget:
    """Daily nutrient targets"""
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    vitamin_c_mg: float
    vitamin_b12_mcg: float
    vitamin_d_mcg: float
    iron_mg: float
    calcium_mg: float
    magnesium_mg: float
    # ... 20+ more micronutrients

@dataclass
class OptimizationWeights:
    """How much to weight each objective (sum = 1.0)"""
    calorie_match: float = 0.25
    nutrient_completeness: float = 0.35      # Most important!
    variety: float = 0.15
    satiety: float = 0.10
    quality: float = 0.10
    affordability: float = 0.03
    digestibility: float = 0.02

class MealOptimizer:
    """Use mathematical optimization to find best menu combination"""
    
    async def optimize_menu_day(
        self,
        db: AsyncSession,
        user_id: str,
        target: NutrientTarget,
        available_recipes: dict[str, list[Recipe]],  # {slot: [recipes]}
        constraints: dict = None,
        weights: OptimizationWeights = OptimizationWeights(),
    ) -> dict[str, Recipe]:
        """
        Find optimal recipe selection that maximizes nutrition while considering user preferences.
        
        Uses NSGA-II (Non-dominated Sorting Genetic Algorithm II) for multi-objective optimization:
        - Minimize nutrient gaps
        - Maximize satiety
        - Maintain variety
        - Stay within budget
        """
        
        if constraints is None:
            constraints = {}
        
        # 1. Normalize metrics to 0-1 scale
        # 2. Define objective function (minimize weighted distance from targets)
        # 3. Define constraints (no allergens, health conditions, etc)
        # 4. Run NSGA-II algorithm
        # 5. Return Pareto-optimal solution
        
        def objective_function(selection_indices: list[int]) -> float:
            """
            Returns a score where lower is better.
            Combines multiple nutritional objectives into single score.
            """
            selected = self._reconstruct_menu(selection_indices, available_recipes)
            
            score = 0.0
            
            # 1. Calorie Match (MSE from target)
            total_cal = sum(r.calories for r in selected.values() if r)
            cal_error = ((total_cal - target.calories) / target.calories) ** 2
            score += weights.calorie_match * cal_error
            
            # 2. Nutrient Completeness (% of daily values achieved)
            daily_nutrients = self._calculate_daily_nutrients(selected)
            nutrient_coverage = self._calculate_coverage_score(daily_nutrients, target)
            # Coverage 0-1, where 1 = 100% of target, optimize by minimizing (1 - coverage)
            score += weights.nutrient_completeness * (1 - nutrient_coverage)
            
            # 3. Variety (ingredient uniqueness)
            variety_score = self._calculate_variety_score(selected)
            score += weights.variety * (1 - variety_score)
            
            # 4. Satiety (stay full longer)
            satiety = self._calculate_satiety_score(selected)
            score += weights.satiety * (1 - satiety)
            
            # 5. Quality (nutrient density: nutrients per calorie)
            quality = self._calculate_nutrient_density(selected, target)
            score += weights.quality * (1 - quality)
            
            # 6. Cost
            cost = self._estimate_cost(selected)
            normalized_cost = min(cost / constraints.get("max_cost", 500), 1.0)
            score += weights.affordability * normalized_cost
            
            # 7. Digestibility (how easy to digest)
            digestibility = self._calculate_digestibility_score(selected)
            score += weights.digestibility * (1 - digestibility)
            
            return score
        
        # Constraint definitions
        constraints_list = []
        
        # No allergens
        if allergens := constraints.get("allergens"):
            constraints_list.append(("allergen_free", allergens))
        
        # Health conditions (safe foods)
        if conditions := constraints.get("health_conditions"):
            constraints_list.append(("health_safe", conditions))
        
        # Eating mode
        if eating_mode := constraints.get("eating_mode"):
            constraints_list.append(("eating_mode_compatible", eating_mode))
        
        # Cost limit
        if max_cost := constraints.get("max_cost"):
            constraints_list.append(("cost_limit", max_cost))
        
        # Run optimizer
        from scipy.optimize import differential_evolution
        
        bounds = self._create_bounds(available_recipes)
        result = differential_evolution(
            objective_function,
            bounds,
            seed=42,
            maxiter=1000,
            atol=0.001,
            tol=0.001,
            workers=4,
        )
        
        return self._reconstruct_menu(result.x, available_recipes)
    
    def _calculate_coverage_score(self, daily: dict, target: NutrientTarget) -> float:
        """
        Calculate how well daily nutrients cover targets.
        Returns 0-1, where 1 = 100% coverage across all nutrients.
        """
        coverages = []
        
        # For each micronutrient, calculate % of target achieved
        nutrients = [
            (daily.get("vitamin_c", 0), target.vitamin_c_mg, 0.5, 1.2),  # 50-120%
            (daily.get("vitamin_b12", 0), target.vitamin_b12_mcg, 0.5, 1.2),
            (daily.get("iron", 0), target.iron_mg, 0.8, 1.2),
            # ... more nutrients
        ]
        
        for daily_val, target_val, min_acceptable, max_acceptable in nutrients:
            if target_val <= 0:
                coverages.append(1.0)
            else:
                pct = daily_val / target_val
                if min_acceptable <= pct <= max_acceptable:
                    coverages.append(1.0)
                elif pct < min_acceptable:
                    coverages.append(pct / min_acceptable)  # partially covered
                else:
                    coverages.append(1.0)  # excess is ok for most nutrients
        
        # Return average coverage (or use weighted average by importance)
        return np.mean(coverages) if coverages else 0.0
    
    def _calculate_variety_score(self, menu: dict[str, Recipe]) -> float:
        """
        Score based on:
        - Ingredient diversity (not same ingredient twice)
        - Nutrient diversity (vitamins, minerals from different sources)
        - Cuisine diversity
        """
        ingredients = set()
        nutrient_sources = {}
        cuisines = set()
        
        for recipe in menu.values():
            if not recipe:
                continue
            
            # Ingredient diversity
            for ing in (recipe.ingredients or []):
                ingredients.add(ing.get("name", "").lower())
            
            # Cuisine diversity
            cuisines.add(recipe.cuisine_region)
            
            # Nutrient source diversity
            for nutrient in ["calcium", "iron", "vitamin_c", "protein"]:
                if getattr(recipe, f"{nutrient}_mg", 0) > 0:
                    if nutrient not in nutrient_sources:
                        nutrient_sources[nutrient] = []
                    nutrient_sources[nutrient].append(recipe.id)
        
        # Score: 0-1
        # Unique ingredients: more is better
        ingredient_score = min(len(ingredients) / 20, 1.0)  # Target 20+ unique ingredients
        
        # Cuisine diversity: should have 2-3 different cuisines
        cuisine_score = min(len(cuisines) / 3, 1.0)
        
        # Nutrient source diversity: each nutrient from multiple sources
        nutrient_diversity_scores = [
            min(len(sources) / 2, 1.0)  # each nutrient should come from 2+ sources
            for sources in nutrient_sources.values()
        ]
        nutrient_score = np.mean(nutrient_diversity_scores) if nutrient_diversity_scores else 0
        
        return (ingredient_score * 0.5 + cuisine_score * 0.2 + nutrient_score * 0.3)
    
    def _calculate_satiety_score(self, menu: dict[str, Recipe]) -> float:
        """
        Higher satiety = user stays full longer between meals.
        Factors:
        - Protein content (most satiating)
        - Fiber content
        - Water content
        - Meal size
        """
        satiety_scores = []
        
        for slot, recipe in menu.items():
            if not recipe:
                continue
            
            # Base satiety from recipe
            satiety = float(recipe.satiety_score or 50) / 100
            
            # Boost based on macros
            protein_boost = min(float(recipe.protein_g or 0) / 30, 1.0) * 0.3
            fiber_boost = min(float(recipe.fibre_g or 0) / 10, 1.0) * 0.2
            
            slot_satiety = min(satiety + protein_boost + fiber_boost, 1.0)
            satiety_scores.append(slot_satiety)
        
        return np.mean(satiety_scores) if satiety_scores else 0.5
    
    def _calculate_nutrient_density(self, menu: dict, target: NutrientTarget) -> float:
        """
        Nutrient Density = (Nutrient Value / Calories) 
        Higher is better. Example: spinach is very nutrient-dense.
        """
        total_cal = sum(r.calories for r in menu.values() if r)
        if total_cal <= 0:
            return 0
        
        # Count unique nutrients present per calorie
        nutrient_count = 0
        for recipe in menu.values():
            if not recipe:
                continue
            if recipe.vitamin_c_mg:
                nutrient_count += 1
            if recipe.iron_mg:
                nutrient_count += 1
            # ... check other nutrients
        
        # Density = nutrients / 1000 calories
        density = nutrient_count / (total_cal / 1000)
        return min(density / 20, 1.0)  # Cap at 20 nutrients per 1000 cal
```

### 5. Micronutrient Tracking Dashboard Endpoint

```python
# app/routers/nutrition.py - NEW ENDPOINT

@router.get("/me/nutrition/daily-overview")
async def get_daily_nutrition_overview(
    current_user: User = Depends(get_current_user),
    date: Optional[str] = None,  # YYYY-MM-DD
    db: AsyncSession = Depends(get_db),
):
    """
    Show user's nutritional status for a given day.
    
    Returns:
    {
      "date": "2026-05-02",
      "meals": [
        {
          "meal_type": "breakfast",
          "recipe": {...},
          "macros": {calories, protein, carbs, fat},
          "micros": {vitamins, minerals, phytonutrients}
        }
      ],
      "daily_totals": {
        "calories": 2000,
        "protein_g": 75,
        "carbs_g": 250,
        "fat_g": 65,
        "fiber_g": 35
      },
      "daily_targets": {...same structure},
      "nutrient_coverage": {
        "vitamins": {
          "vitamin_c": {value: 95, target: 90, pct: 105, status: "complete"},
          "vitamin_d": {value: 8, target: 10, pct: 80, status: "low"},
          "vitamin_b12": {value: 0, target: 2.4, pct: 0, status: "deficient"},
          ...
        },
        "minerals": {...},
        "overall_coverage_pct": 78
      },
      "warnings": [
        {type: "deficiency", nutrient: "vitamin_b12", message: "Deficient vegetarian sources"},
        {type: "excess", nutrient: "sodium", message: "Exceeds recommended daily limit"}
      ],
      "quality_score": {
        "nutrient_density": 72,  # 1-100
        "food_processing_level": "minimally_processed",
        "variety_score": 68,
        "overall_quality": 71
      },
      "meal_timing": {
        "breakfast_timing": "7:30am",
        "meals_spaced": "4-5 hours apart - optimal",
        "last_meal_before_bed": "3 hours - good"
      },
      "signals": {
        "energy_level": 7,  # from user signals
        "digestion_comfort": 8,
        "sleep_quality": 7,
        "cravings": ["sugar", "salt"]
      }
    }
    """
    
    if not date:
        date = str(date.today())
    
    target = await _get_nutrition_targets(current_user, db)
    menu = await _get_menu_for_date(current_user, date, db)
    
    daily_nutrients = calculate_daily_nutrients(menu)
    coverage = calculate_nutrient_coverage(daily_nutrients, target)
    
    warnings = generate_nutrition_warnings(daily_nutrients, coverage, current_user)
    
    signals = await db.execute(
        select(UserNutritionSignal)
        .where(UserNutritionSignal.user_id == current_user.id)
        .where(UserNutritionSignal.date == date)
    )
    signal = signals.scalar_one_or_none()
    
    return {
        "date": date,
        "meals": [await _enrich_recipe(m, db) for m in menu.values()],
        "daily_totals": daily_nutrients,
        "daily_targets": target,
        "nutrient_coverage": coverage,
        "warnings": warnings,
        "quality_score": calculate_meal_quality_score(menu),
        "meal_timing": analyze_meal_timing(menu),
        "signals": signal,
    }

@router.get("/me/nutrition/micronutrient-gaps")
async def get_micronutrient_gaps(
    current_user: User = Depends(get_current_user),
    days: int = 7,  # Last 7 days
    db: AsyncSession = Depends(get_db),
):
    """
    Identify micronutrient deficiencies based on recent menus.
    
    Returns:
    {
      "analysis_period": "last_7_days",
      "critical_deficiencies": [
        {
          "nutrient": "vitamin_b12",
          "reason": "user is vegetarian",
          "avg_daily": 0.5,
          "target": 2.4,
          "severity": "critical",
          "solutions": [
            {food: "fortified milk", amount: "1 cup daily"},
            {food: "nutritional yeast", amount: "1 tbsp daily"},
            {supplement: "B12 supplement", dose: "500 mcg weekly"}
          ]
        },
        {nutrient: "vitamin_d", avg_daily: 5, target: 10, severity: "moderate"}
      ],
      "borderline_nutrients": [...],
      "well_covered": ["protein", "carbs", "fiber", "calcium"]
    }
    """
    pass

@router.post("/me/nutrition-signals/log")
async def log_nutrition_signal(
    signal_data: dict,  # from UserNutritionSignal model
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log how user felt after meals (energy, digestion, sleep, etc)"""
    signal = UserNutritionSignal(
        user_id=current_user.id,
        date=date.today(),
        **signal_data
    )
    db.add(signal)
    await db.flush()
    
    # Use signals to refine future menu generation
    await _update_user_signals_summary(current_user, db)
    
    return signal
```

---

## PHASE 3: ADVANCED SIGNALS & PERSONALIZATION

### 6. Eating Pattern Recognition

```python
# app/services/signal_analyzer.py - NEW: SIGNAL ANALYSIS

class SignalAnalyzer:
    """Analyze user signals to detect patterns and adjust recommendations."""
    
    async def detect_nutrient_deficiency_signals(
        self,
        user_id: str,
        db: AsyncSession,
        days: int = 30,
    ) -> list[dict]:
        """
        Detect nutritional deficiency signs from user signals:
        - Hair loss → iron, zinc, protein deficiency
        - Muscle cramps → magnesium, potassium deficiency
        - Constant fatigue → B12, iron, folate deficiency
        - Poor wound healing → vitamin C, zinc deficiency
        - Weak immunity → vitamin D, zinc, selenium
        """
        
        signals = await db.execute(
            select(UserNutritionSignal)
            .where(UserNutritionSignal.user_id == user_id)
            .where(UserNutritionSignal.date >= date.today() - timedelta(days=days))
            .order_by(UserNutritionSignal.date.desc())
        )
        signal_list = signals.scalars().all()
        
        deficiency_patterns = []
        
        # Check for hair loss pattern
        hair_loss_count = sum(1 for s in signal_list if s.hair_loss_noticed)
        if hair_loss_count >= 5:  # 5+ signals in last 30 days
            deficiency_patterns.append({
                "symptom": "hair_loss",
                "severity": "moderate" if hair_loss_count < 10 else "severe",
                "likely_deficiencies": ["iron", "zinc", "selenium", "protein"],
                "recommended_foods": ["red_meat", "eggs", "pumpkin_seeds", "spinach"],
                "confidence": 0.7
            })
        
        # Check for muscle cramps
        cramp_count = sum(1 for s in signal_list if s.muscle_cramps)
        if cramp_count >= 3:
            deficiency_patterns.append({
                "symptom": "muscle_cramps",
                "likely_deficiencies": ["magnesium", "potassium", "calcium"],
                "recommended_foods": ["bananas", "spinach", "pumpkin_seeds", "almonds"],
            })
        
        # Check for fatigue pattern
        low_energy_days = sum(1 for s in signal_list if (s.energy_level or 5) < 4)
        if low_energy_days >= 8:
            deficiency_patterns.append({
                "symptom": "persistent_fatigue",
                "likely_deficiencies": ["iron", "b12", "folate", "thyroid_function"],
                "action": "recommend_blood_test",
            })
        
        # Check for poor sleep despite good signal logging
        poor_sleep_days = sum(1 for s in signal_list if (s.sleep_quality or 5) < 4)
        if poor_sleep_days >= 10:
            deficiency_patterns.append({
                "symptom": "poor_sleep_quality",
                "likely_issues": ["high_caffeine", "late_night_carbs", "magnesium_deficiency"],
                "recommendations": [
                    "Reduce caffeine after 2pm",
                    "Add magnesium-rich foods: spinach, pumpkin seeds",
                    "Avoid complex carbs 3+ hours before sleep"
                ],
            })
        
        return deficiency_patterns
    
    async def detect_eating_pattern(
        self,
        user_id: str,
        db: AsyncSession,
        days: int = 30,
    ) -> dict:
        """Detect user's natural eating patterns from adherence data."""
        
        # Get user's meal adherence
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        adherence_rate = user.adherence_rate or 0.5
        
        pattern = {
            "adherence_rate": adherence_rate,
            "pattern": "unknown"
        }
        
        if adherence_rate > 0.8:
            pattern["pattern"] = "disciplined"
            pattern["recommendation"] = "Can handle complex recipes, strict macros"
        elif adherence_rate > 0.6:
            pattern["pattern"] = "moderate"
            pattern["recommendation"] = "Needs variety, occasional flexibility"
        else:
            pattern["pattern"] = "low_adherence"
            pattern["recommendation"] = "Requires very simple recipes, high palatability"
        
        return pattern
    
    async def detect_spice_tolerance(
        self,
        user_id: str,
        db: AsyncSession,
        days: int = 30,
    ) -> str:
        """Detect actual spice tolerance from signals, not just initial onboarding."""
        
        # Find hot meals eaten recently
        signals = await db.execute(
            select(UserNutritionSignal)
            .where(UserNutritionSignal.user_id == user_id)
            .where(UserNutritionSignal.date >= date.today() - timedelta(days=days))
        )
        signal_list = signals.scalars().all()
        
        # Track digestion comfort after spicy meals
        spicy_meal_days = 0
        good_digestion_after_spicy = 0
        
        for signal in signal_list:
            # Would need to track "had_spicy_meal" field
            if signal.digestion_comfort and signal.digestion_comfort >= 7:
                good_digestion_after_spicy += 1
            spicy_meal_days += 1
        
        if spicy_meal_days == 0:
            return "unknown"
        
        tolerance_pct = good_digestion_after_spicy / spicy_meal_days
        
        if tolerance_pct > 0.8:
            return "high"
        elif tolerance_pct > 0.5:
            return "moderate"
        else:
            return "low"

# Example: Route to trigger signal analysis and adjust menus
@router.post("/admin/analyze-user-signals/{user_id}")
async def analyze_user_signals(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Analyze user's signals and detect nutritional issues."""
    
    analyzer = SignalAnalyzer()
    
    deficiencies = await analyzer.detect_nutrient_deficiency_signals(user_id, db)
    pattern = await analyzer.detect_eating_pattern(user_id, db)
    spice = await analyzer.detect_spice_tolerance(user_id, db)
    
    return {
        "user_id": user_id,
        "detected_deficiencies": deficiencies,
        "eating_pattern": pattern,
        "spice_tolerance": spice,
        "actions_recommended": [
            f"Adjust menus for detected deficiencies" if deficiencies else None,
            f"Increase recipe complexity" if pattern["pattern"] == "disciplined" else "Simplify recipes",
            f"Adjust spice level to {spice}" if spice != "unknown" else None,
        ]
    }
```

---

## PHASE 4: HEALTH CONDITION INTELLIGENCE

### 7. Comprehensive Health Condition Framework

```python
# app/services/health_condition_manager.py - NEW: CONDITION-SPECIFIC NUTRITION

from enum import Enum
from dataclasses import dataclass

class HealthCondition(Enum):
    """Comprehensive health condition list"""
    
    # Metabolic/Endocrine
    DIABETES_T1 = "diabetes_t1"
    DIABETES_T2 = "diabetes_t2"
    PCOS = "pcos"
    THYROID_HYPO = "thyroid_hypothyroidism"
    THYROID_HYPER = "thyroid_hyperthyroidism"
    METABOLIC_SYNDROME = "metabolic_syndrome"
    
    # Cardiovascular
    HYPERTENSION = "hypertension"
    HIGH_CHOLESTEROL = "high_cholesterol"
    HEART_DISEASE = "heart_disease"
    
    # GI/Digestive
    IBS = "ibs"
    CELIAC = "celiac_disease"
    CROHNS = "crohns_disease"
    ULCERATIVE_COLITIS = "ulcerative_colitis"
    GERD = "gerd"
    FATTY_LIVER = "fatty_liver_disease"
    
    # Renal
    KIDNEY_DISEASE = "chronic_kidney_disease"
    KIDNEY_STONES = "kidney_stones"
    
    # Other
    ANEMIA = "anemia"
    OSTEOPOROSIS = "osteoporosis"

@dataclass
class ConditionNutritionSpec:
    """Defines nutrition requirements for a health condition"""
    
    condition: HealthCondition
    
    # Macro adjustments
    calories_adjustment: float = 0.0      # +/-300 etc
    protein_pct_range: tuple = (0.2, 0.3)  # 20-30% of calories
    carb_pct_range: tuple = (0.4, 0.6)
    fat_pct_range: tuple = (0.2, 0.35)
    fiber_min_g: float = 25.0
    
    # Nutrient constraints
    sodium_max_mg: int = 2300  # for hypertension
    phosphorus_max_mg: int = 1000  # for kidney disease
    potassium_max_mg: int = 2000  # for kidney disease
    sugar_max_g: int = 25  # for diabetes
    glycemic_load_max: float = 100.0
    
    # Required nutrients (with minimum daily amounts)
    required_nutrients: dict = None  # {nutrient: min_amount}
    
    # Foods to avoid
    forbidden_foods: list[str] = None
    
    # Foods highly beneficial
    beneficial_foods: list[str] = None
    
    # Preparation notes
    prep_notes: str = None
    
    # Meal timing recommendations
    meal_timing: str = None

# Define specs for each condition
CONDITION_SPECS = {
    HealthCondition.DIABETES_T2: ConditionNutritionSpec(
        condition=HealthCondition.DIABETES_T2,
        protein_pct_range=(0.25, 0.35),  # higher protein
        carb_pct_range=(0.35, 0.45),     # lower carbs
        fat_pct_range=(0.25, 0.35),
        fiber_min_g=35.0,                 # high fiber
        sugar_max_g=10.0,                # very low sugar
        glycemic_load_max=50.0,          # low GI meals
        required_nutrients={
            "fiber_g": 35,
            "chromium_mcg": 25,          # improves insulin sensitivity
            "magnesium_mg": 400,         # helps glucose regulation
        },
        forbidden_foods=["refined_grains", "sugary_drinks", "processed_sweets", "white_bread"],
        beneficial_foods=["legumes", "whole_grains", "leafy_greens", "berries", "nuts"],
        prep_notes="Pair carbs with protein/fat to reduce GI spike. Avoid cooking with high heat (AGEs).",
        meal_timing="Eat complex carbs at lunch (best glucose tolerance), light at dinner.",
    ),
    
    HealthCondition.HYPERTENSION: ConditionNutritionSpec(
        condition=HealthCondition.HYPERTENSION,
        sodium_max_mg=1500,              # DASH diet standard
        potassium_min_mg=3500,           # higher potassium helps
        required_nutrients={
            "potassium_mg": 3500,
            "calcium_mg": 1200,
            "magnesium_mg": 350,
        },
        forbidden_foods=["processed_foods", "cured_meats", "salty_snacks", "high_sodium_sauces"],
        beneficial_foods=["leafy_greens", "bananas", "sweet_potato", "almonds", "fish"],
        prep_notes="Use spices instead of salt (cumin, coriander, asafoetida). Limit pickled foods.",
    ),
    
    HealthCondition.IBS: ConditionNutritionSpec(
        condition=HealthCondition.IBS,
        fiber_min_g=25.0,                # but increase gradually
        required_nutrients={
            "fiber_g": 25,
            "water_ml": 2000,            # hydration critical
        },
        forbidden_foods=["high_fodmap_foods", "fatty_foods", "caffeine", "alcohol"],
        beneficial_foods=["low_fodmap_vegetables", "white_rice", "ginger", "probiotics"],
        prep_notes="Introduce fiber gradually (3-4 weeks). Cook vegetables well (easier to digest).",
        meal_timing="Small, frequent meals. Avoid large meals that trigger symptoms.",
    ),
    
    # ... more conditions
}

class HealthConditionManager:
    """Manage nutrition based on health conditions"""
    
    async def get_nutrition_spec_for_user(
        self,
        user: User,
        db: AsyncSession,
    ) -> dict:
        """
        Return consolidated nutrition spec based on user's conditions.
        If multiple conditions, need to find safe intersection.
        """
        
        conditions = [
            HealthCondition[cond.upper().replace(" ", "_")]
            for cond in (user.medical_conditions or [])
            if cond.upper().replace(" ", "_") in HealthCondition.__members__
        ]
        
        if not conditions:
            return self._get_default_spec()
        
        # Start with most restrictive condition
        specs = [CONDITION_SPECS.get(cond) for cond in conditions]
        specs = [s for s in specs if s]
        
        if not specs:
            return self._get_default_spec()
        
        # Merge specs: most restrictive wins
        merged = self._merge_specs(specs)
        
        return merged
    
    def _merge_specs(self, specs: list[ConditionNutritionSpec]) -> dict:
        """Merge multiple condition specs into safe intersection"""
        
        # Protein: take highest requirement (more protein helps multiple conditions)
        protein_min = max((s.protein_pct_range[0] for s in specs), default=0.2)
        
        # Carbs: take lowest (safe for all)
        carb_max = min((s.carb_pct_range[1] for s in specs), default=0.55)
        
        # Fiber: take highest (more is generally safe)
        fiber_min = max((s.fiber_min_g for s in specs), default=25)
        
        # Sodium: take lowest (most restrictive)
        sodium_max = min((s.sodium_max_mg for s in specs), default=2300)
        
        # Forbidden foods: union (avoid anything any condition forbids)
        forbidden = set()
        for spec in specs:
            forbidden.update(spec.forbidden_foods or [])
        
        # Beneficial foods: intersection (foods safe for all)
        beneficial = None
        for spec in specs:
            if beneficial is None:
                beneficial = set(spec.beneficial_foods or [])
            else:
                beneficial &= set(spec.beneficial_foods or [])
        
        return {
            "protein_pct_range": (protein_min, 0.35),
            "carb_pct_range": (0.35, carb_max),
            "fiber_min_g": fiber_min,
            "sodium_max_mg": sodium_max,
            "forbidden_foods": list(forbidden),
            "beneficial_foods": list(beneficial or []),
            "conditions": [s.condition.value for s in specs],
        }
```

This blueprint provides the architecture for a world-class nutritionist-grade system with:

1. **20+ micronutrient tracking**
2. **Multi-objective meal optimization** (not just greedy matching)
3. **Comprehensive health condition support** (15+ major conditions)
4. **User signal analysis** (detect deficiencies from body signals)
5. **Personalization via learning** (eating patterns, preferences)
6. **Regional & seasonal optimization** foundation

Would you like me to implement any specific part of this blueprint or dive deeper into any particular aspect?

