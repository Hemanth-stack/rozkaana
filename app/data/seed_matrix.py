"""
Recipe Generation Matrix — targeting 8000+ recipes across all cuisines.

south_indian split into andhra, tamil, karnataka sub-regions (kerala already separate).
south_indian kept as a small legacy pool for generic dishes shared across all states.

Structure: (meal_type, cuisine_region, eating_mode, health_tags, count)

Distribution target (updated):
  breakfast     ~2 000 recipes
  lunch         ~2 400 recipes
  dinner        ~2 400 recipes
  morning_snack ~  700 recipes
  evening_snack ~  700 recipes
  Total         ~8 200 recipes

Cost estimate: ~1 600 Claude API calls ≈ $50-65
Runtime estimate: ~100-120 minutes
"""

CUISINES = [
    "north_indian", "andhra", "tamil", "karnataka", "bengali", "gujarati",
    "maharashtrian", "punjabi", "hyderabadi", "rajasthani", "kerala", "goan",
    "sattvic", "south_indian",
]

# (meal_type, cuisine, eating_mode, health_tags, count)
GENERATION_MATRIX = [

    # ═══════════════════════════════════════════════════════════════
    # BREAKFAST  — target ~1 400
    # 11 cuisines × 5 eating modes × 15 = 825 base
    # + health variants                 = ~575
    # ═══════════════════════════════════════════════════════════════

    # ── north_indian ──
    ("breakfast", "north_indian", "pure_veg",       [],                    15),
    ("breakfast", "north_indian", "full_nv",         [],                    12),
    ("breakfast", "north_indian", "jain",            [],                    12),
    ("breakfast", "north_indian", "sattvic",         [],                    12),
    ("breakfast", "north_indian", "conditional_nv",  [],                    10),
    ("breakfast", "north_indian", "pure_veg",        ["diabetes_t2"],       15),
    ("breakfast", "north_indian", "pure_veg",        ["hypertension"],      12),
    ("breakfast", "north_indian", "pure_veg",        ["weight_loss"],       12),
    ("breakfast", "north_indian", "pure_veg",        ["pcos"],              10),
    ("breakfast", "north_indian", "pure_veg",        ["thyroid_hypo"],      10),
    ("breakfast", "north_indian", "pure_veg",        ["anemia"],            10),

    # ── andhra ──
    # Pesarattu, gongura chutney idli, upma with gongura, punugulu, attu, pesarattu-upma combo
    ("breakfast", "andhra",       "pure_veg",         [],                    15),
    ("breakfast", "andhra",       "full_nv",           [],                    10),
    ("breakfast", "andhra",       "pure_veg",          ["diabetes_t2"],       12),
    ("breakfast", "andhra",       "pure_veg",          ["pcos"],              10),
    ("breakfast", "andhra",       "pure_veg",          ["weight_loss"],       10),
    ("breakfast", "andhra",       "pure_veg",          ["hypertension"],      8),
    ("breakfast", "andhra",       "pure_veg",          ["anemia"],            8),

    # ── tamil ──
    # Ven pongal, adai, idiyappam, kozhukattai, aappam, kuzhi paniyaram, kollu dosai
    ("breakfast", "tamil",        "pure_veg",          [],                    15),
    ("breakfast", "tamil",        "full_nv",            [],                    10),
    ("breakfast", "tamil",        "sattvic",            [],                    8),
    ("breakfast", "tamil",        "pure_veg",           ["diabetes_t2"],       12),
    ("breakfast", "tamil",        "pure_veg",           ["pcos"],              10),
    ("breakfast", "tamil",        "pure_veg",           ["weight_loss"],       10),
    ("breakfast", "tamil",        "pure_veg",           ["hypertension"],      8),

    # ── karnataka ──
    # Ragi mudde, akki roti, set dosa, neer dosa, rave idli, uddina vade, obbattu
    ("breakfast", "karnataka",    "pure_veg",           [],                    15),
    ("breakfast", "karnataka",    "full_nv",             [],                    8),
    ("breakfast", "karnataka",    "sattvic",             [],                    8),
    ("breakfast", "karnataka",    "pure_veg",            ["diabetes_t2"],       10),
    ("breakfast", "karnataka",    "pure_veg",            ["weight_loss"],       8),
    ("breakfast", "karnataka",    "pure_veg",            ["hypertension"],      8),

    # ── south_indian (legacy — generic dishes shared across states) ──
    ("breakfast", "south_indian", "pure_veg",        [],                    8),
    ("breakfast", "south_indian", "sattvic",          [],                    5),
    ("breakfast", "south_indian", "pure_veg",         ["diabetes_t2"],       5),

    # ── gujarati ──
    ("breakfast", "gujarati",     "pure_veg",         [],                    12),
    ("breakfast", "gujarati",     "jain",             [],                    12),
    ("breakfast", "gujarati",     "sattvic",          [],                    8),
    ("breakfast", "gujarati",     "pure_veg",         ["diabetes_t2"],       10),

    # ── bengali ──
    ("breakfast", "bengali",      "pure_veg",         [],                    12),
    ("breakfast", "bengali",      "full_nv",           [],                    10),
    ("breakfast", "bengali",      "pure_veg",          ["anemia"],            8),

    # ── maharashtrian ──
    ("breakfast", "maharashtrian","pure_veg",          [],                    12),
    ("breakfast", "maharashtrian","full_nv",            [],                    10),
    ("breakfast", "maharashtrian","pure_veg",           ["diabetes_t2"],       8),
    ("breakfast", "maharashtrian","jain",               [],                    8),

    # ── punjabi ──
    ("breakfast", "punjabi",      "pure_veg",          [],                    12),
    ("breakfast", "punjabi",      "full_nv",            [],                    10),
    ("breakfast", "punjabi",      "pure_veg",           ["weight_loss"],       8),

    # ── hyderabadi ──
    ("breakfast", "hyderabadi",   "pure_veg",           [],                    10),
    ("breakfast", "hyderabadi",   "full_nv",             [],                    10),

    # ── rajasthani ──
    ("breakfast", "rajasthani",   "pure_veg",           [],                    12),
    ("breakfast", "rajasthani",   "jain",               [],                    10),

    # ── kerala ──
    ("breakfast", "kerala",       "pure_veg",           [],                    12),
    ("breakfast", "kerala",       "full_nv",             [],                    10),
    ("breakfast", "kerala",       "pure_veg",            ["diabetes_t2"],       8),

    # ── goan ──
    ("breakfast", "goan",         "pure_veg",           [],                    10),
    ("breakfast", "goan",         "full_nv",             [],                    10),

    # ── sattvic ──
    ("breakfast", "sattvic",      "sattvic",            [],                    15),
    ("breakfast", "sattvic",      "pure_veg",           [],                    10),
    ("breakfast", "sattvic",      "sattvic",            ["diabetes_t2"],       10),


    # ═══════════════════════════════════════════════════════════════
    # MORNING SNACK  — target ~500
    # ═══════════════════════════════════════════════════════════════

    ("morning_snack", "north_indian",    "pure_veg",    [],                    12),
    ("morning_snack", "north_indian",    "jain",        [],                    10),
    ("morning_snack", "north_indian",    "pure_veg",    ["diabetes_t2"],       12),
    ("morning_snack", "north_indian",    "pure_veg",    ["weight_loss"],       10),
    ("morning_snack", "north_indian",    "pure_veg",    ["hypertension"],      8),
    ("morning_snack", "andhra",          "pure_veg",    [],                    8),
    ("morning_snack", "andhra",          "pure_veg",    ["diabetes_t2"],       6),
    ("morning_snack", "tamil",           "pure_veg",    [],                    8),
    ("morning_snack", "tamil",           "pure_veg",    ["diabetes_t2"],       6),
    ("morning_snack", "karnataka",       "pure_veg",    [],                    6),
    ("morning_snack", "south_indian",    "pure_veg",    [],                    4),
    ("morning_snack", "gujarati",        "pure_veg",    [],                    10),
    ("morning_snack", "gujarati",        "jain",        [],                    10),
    ("morning_snack", "maharashtrian",   "pure_veg",    [],                    8),
    ("morning_snack", "bengali",         "pure_veg",    [],                    8),
    ("morning_snack", "punjabi",         "pure_veg",    [],                    8),
    ("morning_snack", "kerala",          "pure_veg",    [],                    8),
    ("morning_snack", "rajasthani",      "pure_veg",    [],                    8),
    ("morning_snack", "hyderabadi",      "pure_veg",    [],                    8),
    ("morning_snack", "sattvic",         "sattvic",     [],                    10),


    # ═══════════════════════════════════════════════════════════════
    # LUNCH  — target ~1 700
    # 11 cuisines × 5 eating modes × 20 = 1100 base
    # + health variants                  = ~600
    # ═══════════════════════════════════════════════════════════════

    # ── north_indian ──
    ("lunch", "north_indian",  "pure_veg",       [],                    20),
    ("lunch", "north_indian",  "full_nv",         [],                    15),
    ("lunch", "north_indian",  "jain",            [],                    15),
    ("lunch", "north_indian",  "sattvic",         [],                    12),
    ("lunch", "north_indian",  "conditional_nv",  [],                    12),
    ("lunch", "north_indian",  "pure_veg",        ["diabetes_t2"],       15),
    ("lunch", "north_indian",  "pure_veg",        ["hypertension"],      12),
    ("lunch", "north_indian",  "pure_veg",        ["weight_loss"],       12),
    ("lunch", "north_indian",  "pure_veg",        ["pcos"],              10),
    ("lunch", "north_indian",  "pure_veg",        ["anemia"],            10),
    ("lunch", "north_indian",  "pure_veg",        ["high_cholesterol"],  10),
    ("lunch", "north_indian",  "full_nv",          ["diabetes_t2"],       10),

    # ── andhra ──
    # Gongura pappu, pulihora, gutti vankaya kura, mamidikaya pappu, challa pulusu, ulava charu,
    # tomato pappu, kobbari annam, perugu annam, avakaya pickle sides, tomato kura, dondakaya fry
    ("lunch", "andhra",        "pure_veg",         [],                    20),
    ("lunch", "andhra",        "full_nv",           [],                    15),
    ("lunch", "andhra",        "conditional_nv",    [],                    10),
    ("lunch", "andhra",        "pure_veg",          ["diabetes_t2"],       12),
    ("lunch", "andhra",        "pure_veg",          ["pcos"],              10),
    ("lunch", "andhra",        "pure_veg",          ["hypertension"],      10),
    ("lunch", "andhra",        "pure_veg",          ["weight_loss"],       10),
    ("lunch", "andhra",        "pure_veg",          ["anemia"],            8),

    # ── tamil ──
    # Sambar sadam, rasam sadam, kootu, kuzhambu, kollu rasam, mor kuzhambu, kaara kuzhambu,
    # poriyal varieties, thayir sadam, variety rice (lemon rice, tamarind rice, coconut rice)
    ("lunch", "tamil",         "pure_veg",          [],                    20),
    ("lunch", "tamil",         "full_nv",            [],                    15),
    ("lunch", "tamil",         "sattvic",            [],                    8),
    ("lunch", "tamil",         "pure_veg",           ["diabetes_t2"],       12),
    ("lunch", "tamil",         "pure_veg",           ["pcos"],              10),
    ("lunch", "tamil",         "pure_veg",           ["hypertension"],      10),
    ("lunch", "tamil",         "pure_veg",           ["weight_loss"],       10),

    # ── karnataka ──
    # Bisi bele bath, jolada rotti with saaru, akki roti with majjige huli, kootu curry,
    # gojju, palya varieties, hesaru kalu bath, vangi bath, chitranna (lemon rice)
    ("lunch", "karnataka",     "pure_veg",           [],                    18),
    ("lunch", "karnataka",     "full_nv",             [],                    12),
    ("lunch", "karnataka",     "sattvic",             [],                    8),
    ("lunch", "karnataka",     "pure_veg",            ["diabetes_t2"],       10),
    ("lunch", "karnataka",     "pure_veg",            ["hypertension"],      8),
    ("lunch", "karnataka",     "pure_veg",            ["weight_loss"],       8),

    # ── south_indian (legacy generic) ──
    ("lunch", "south_indian",  "pure_veg",          [],                    8),
    ("lunch", "south_indian",  "sattvic",            [],                    5),
    ("lunch", "south_indian",  "pure_veg",           ["diabetes_t2"],       5),

    # ── gujarati ──
    ("lunch", "gujarati",      "pure_veg",         [],                    15),
    ("lunch", "gujarati",      "jain",             [],                    15),
    ("lunch", "gujarati",      "sattvic",          [],                    10),
    ("lunch", "gujarati",      "pure_veg",         ["diabetes_t2"],       10),
    ("lunch", "gujarati",      "pure_veg",         ["weight_loss"],       8),

    # ── bengali ──
    ("lunch", "bengali",       "pure_veg",         [],                    12),
    ("lunch", "bengali",       "full_nv",           [],                    15),
    ("lunch", "bengali",       "pure_veg",          ["anemia"],            10),

    # ── maharashtrian ──
    ("lunch", "maharashtrian", "pure_veg",          [],                    15),
    ("lunch", "maharashtrian", "full_nv",            [],                    12),
    ("lunch", "maharashtrian", "jain",               [],                    10),
    ("lunch", "maharashtrian", "pure_veg",           ["diabetes_t2"],       8),

    # ── punjabi ──
    ("lunch", "punjabi",       "pure_veg",          [],                    15),
    ("lunch", "punjabi",       "full_nv",            [],                    15),
    ("lunch", "punjabi",       "pure_veg",           ["weight_loss"],       10),
    ("lunch", "punjabi",       "pure_veg",           ["high_cholesterol"],  8),

    # ── hyderabadi ──
    ("lunch", "hyderabadi",    "full_nv",             [],                    15),
    ("lunch", "hyderabadi",    "pure_veg",            [],                    12),
    ("lunch", "hyderabadi",    "pure_veg",            ["hypertension"],      8),

    # ── rajasthani ──
    ("lunch", "rajasthani",    "pure_veg",            [],                    15),
    ("lunch", "rajasthani",    "jain",                [],                    12),
    ("lunch", "rajasthani",    "pure_veg",            ["diabetes_t2"],       8),

    # ── kerala ──
    ("lunch", "kerala",        "full_nv",             [],                    15),
    ("lunch", "kerala",        "pure_veg",            [],                    15),
    ("lunch", "kerala",        "pure_veg",            ["diabetes_t2"],       10),

    # ── goan ──
    ("lunch", "goan",          "full_nv",             [],                    15),
    ("lunch", "goan",          "pure_veg",            [],                    10),

    # ── sattvic ──
    ("lunch", "sattvic",       "sattvic",             [],                    15),
    ("lunch", "sattvic",       "pure_veg",            [],                    10),
    ("lunch", "sattvic",       "sattvic",             ["diabetes_t2"],       10),


    # ═══════════════════════════════════════════════════════════════
    # EVENING SNACK  — target ~500
    # ═══════════════════════════════════════════════════════════════

    ("evening_snack", "north_indian",    "pure_veg",   [],                    12),
    ("evening_snack", "north_indian",    "jain",       [],                    10),
    ("evening_snack", "north_indian",    "pure_veg",   ["diabetes_t2"],       12),
    ("evening_snack", "north_indian",    "pure_veg",   ["weight_loss"],       10),
    ("evening_snack", "andhra",          "pure_veg",   [],                    8),
    ("evening_snack", "andhra",          "pure_veg",   ["diabetes_t2"],       6),
    ("evening_snack", "tamil",           "pure_veg",   [],                    8),
    ("evening_snack", "tamil",           "pure_veg",   ["diabetes_t2"],       6),
    ("evening_snack", "karnataka",       "pure_veg",   [],                    6),
    ("evening_snack", "south_indian",    "pure_veg",   [],                    4),
    ("evening_snack", "gujarati",        "pure_veg",   [],                    10),
    ("evening_snack", "gujarati",        "jain",       [],                    10),
    ("evening_snack", "maharashtrian",   "pure_veg",   [],                    8),
    ("evening_snack", "bengali",         "pure_veg",   [],                    8),
    ("evening_snack", "punjabi",         "pure_veg",   [],                    8),
    ("evening_snack", "kerala",          "pure_veg",   [],                    8),
    ("evening_snack", "rajasthani",      "pure_veg",   [],                    8),
    ("evening_snack", "hyderabadi",      "pure_veg",   [],                    8),
    ("evening_snack", "sattvic",         "sattvic",    [],                    10),


    # ═══════════════════════════════════════════════════════════════
    # DINNER  — target ~1 700
    # 11 cuisines × 5 eating modes × 20 = 1100 base
    # + health variants                  = ~600
    # ═══════════════════════════════════════════════════════════════

    # ── north_indian ──
    ("dinner", "north_indian",  "pure_veg",       [],                    20),
    ("dinner", "north_indian",  "full_nv",         [],                    15),
    ("dinner", "north_indian",  "jain",            [],                    15),
    ("dinner", "north_indian",  "sattvic",         [],                    12),
    ("dinner", "north_indian",  "conditional_nv",  [],                    12),
    ("dinner", "north_indian",  "pure_veg",        ["diabetes_t2"],       15),
    ("dinner", "north_indian",  "pure_veg",        ["hypertension"],      12),
    ("dinner", "north_indian",  "pure_veg",        ["weight_loss"],       12),
    ("dinner", "north_indian",  "pure_veg",        ["pcos"],              10),
    ("dinner", "north_indian",  "pure_veg",        ["anemia"],            10),
    ("dinner", "north_indian",  "pure_veg",        ["high_cholesterol"],  10),
    ("dinner", "north_indian",  "full_nv",          ["diabetes_t2"],       10),

    # ── andhra (dinner: mix of rice plates, tiffin, roti-based) ──
    # Rice plate: pulusu annam, curd rice, kobbari annam, tomato pappu with rice
    # Tiffin: pesarattu, attu, upma, pesarattu-upma, ragi sangati
    # Roti-based: chapathi with dal fry, chapathi with mixed veg curry
    ("dinner", "andhra",        "pure_veg",         [],                    20),
    ("dinner", "andhra",        "full_nv",           [],                    15),
    ("dinner", "andhra",        "conditional_nv",    [],                    10),
    ("dinner", "andhra",        "pure_veg",          ["diabetes_t2"],       12),
    ("dinner", "andhra",        "pure_veg",          ["pcos"],              10),
    ("dinner", "andhra",        "pure_veg",          ["hypertension"],      10),
    ("dinner", "andhra",        "pure_veg",          ["weight_loss"],       10),

    # ── tamil (dinner: idiyappam+kurma, aappam+stew, sevai, light kuzhambu rice) ──
    ("dinner", "tamil",         "pure_veg",          [],                    20),
    ("dinner", "tamil",         "full_nv",            [],                    15),
    ("dinner", "tamil",         "sattvic",            [],                    8),
    ("dinner", "tamil",         "pure_veg",           ["diabetes_t2"],       12),
    ("dinner", "tamil",         "pure_veg",           ["pcos"],              10),
    ("dinner", "tamil",         "pure_veg",           ["hypertension"],      10),
    ("dinner", "tamil",         "pure_veg",           ["weight_loss"],       10),

    # ── karnataka (dinner: akki roti+chutney, neer dosa+coconut curry, ragi mudde+saaru) ──
    ("dinner", "karnataka",     "pure_veg",           [],                    18),
    ("dinner", "karnataka",     "full_nv",             [],                    12),
    ("dinner", "karnataka",     "sattvic",             [],                    8),
    ("dinner", "karnataka",     "pure_veg",            ["diabetes_t2"],       10),
    ("dinner", "karnataka",     "pure_veg",            ["hypertension"],      8),
    ("dinner", "karnataka",     "pure_veg",            ["weight_loss"],       8),

    # ── south_indian (legacy generic) ──
    ("dinner", "south_indian",  "pure_veg",          [],                    8),
    ("dinner", "south_indian",  "sattvic",            [],                    5),
    ("dinner", "south_indian",  "pure_veg",           ["diabetes_t2"],       5),

    # ── gujarati ──
    ("dinner", "gujarati",      "pure_veg",         [],                    15),
    ("dinner", "gujarati",      "jain",             [],                    15),
    ("dinner", "gujarati",      "sattvic",          [],                    10),
    ("dinner", "gujarati",      "pure_veg",         ["diabetes_t2"],       10),
    ("dinner", "gujarati",      "pure_veg",         ["weight_loss"],       8),

    # ── bengali ──
    ("dinner", "bengali",       "pure_veg",         [],                    12),
    ("dinner", "bengali",       "full_nv",           [],                    15),
    ("dinner", "bengali",       "pure_veg",          ["anemia"],            10),

    # ── maharashtrian ──
    ("dinner", "maharashtrian", "pure_veg",          [],                    15),
    ("dinner", "maharashtrian", "full_nv",            [],                    12),
    ("dinner", "maharashtrian", "jain",               [],                    10),
    ("dinner", "maharashtrian", "pure_veg",           ["diabetes_t2"],       8),

    # ── punjabi ──
    ("dinner", "punjabi",       "pure_veg",          [],                    15),
    ("dinner", "punjabi",       "full_nv",            [],                    15),
    ("dinner", "punjabi",       "pure_veg",           ["weight_loss"],       10),
    ("dinner", "punjabi",       "pure_veg",           ["high_cholesterol"],  8),

    # ── hyderabadi ──
    ("dinner", "hyderabadi",    "full_nv",             [],                    15),
    ("dinner", "hyderabadi",    "pure_veg",            [],                    12),
    ("dinner", "hyderabadi",    "pure_veg",            ["hypertension"],      8),

    # ── rajasthani ──
    ("dinner", "rajasthani",    "pure_veg",            [],                    15),
    ("dinner", "rajasthani",    "jain",                [],                    12),
    ("dinner", "rajasthani",    "pure_veg",            ["diabetes_t2"],       8),

    # ── kerala ──
    ("dinner", "kerala",        "full_nv",             [],                    15),
    ("dinner", "kerala",        "pure_veg",            [],                    15),
    ("dinner", "kerala",        "pure_veg",            ["diabetes_t2"],       10),

    # ── goan ──
    ("dinner", "goan",          "full_nv",             [],                    15),
    ("dinner", "goan",          "pure_veg",            [],                    10),

    # ── sattvic ──
    ("dinner", "sattvic",       "sattvic",             [],                    15),
    ("dinner", "sattvic",       "pure_veg",            [],                    10),
    ("dinner", "sattvic",       "sattvic",             ["diabetes_t2"],       10),
]

# Target recipe counts by slot
SLOT_TARGETS = {
    "breakfast":     1400,
    "morning_snack":  500,
    "lunch":         1700,
    "evening_snack":  500,
    "dinner":        1700,
}
TOTAL_TARGET = sum(SLOT_TARGETS.values())  # 5800
