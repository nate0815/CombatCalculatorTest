# CombatCalculatorTest.py
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any

# =========================================================
# Path & Loader 檢查路徑跟載入表格
# =========================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


def load_sheet(excel_name: str, sheet_name: str) -> pd.DataFrame:
    """
    Load a specific sheet from an Excel file inside Data folder.
    """
    path = DATA_DIR / excel_name
    if not path.exists():
        raise FileNotFoundError(f"❌ Excel file not found: {path}")

    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except ValueError:
        raise ValueError(f"❌ Sheet '{sheet_name}' not found in {excel_name}")

    # print(f"📄 Reading file: {path.resolve()}")
    # print(f"✅ Loaded {excel_name} / {sheet_name} ({len(df)} rows)")
    
    
    # Strip whitespace from column headers to prevent "PartnerId " errors
    df.columns = df.columns.astype(str).str.strip()
    return df


# 類別檢查，防呆處理
def to_bool(value: Any) -> bool:
    """
    Convert Excel/Sheet boolean-like value to Python bool.
    Accepts: TRUE/FALSE, True/False, 1/0, 'true'/'false', empty.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "t", "yes", "y", "1"):
            return True
        if s in ("false", "f", "no", "n", "0", ""):
            return False
    return False


def clamp_int(x: Any, lo: int, hi: int, default: int = 0) -> int:
    try:
        v = int(x)
    except Exception:
        v = default
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def norm_level_to_half(x: Any) -> float:
    """
    Normalize level to nearest 0.5 step.
    Examples: 5 -> 5.0, 10.5 -> 10.5, 10.499999 -> 10.5
    """
    try:
        v = float(x)
    except Exception:
        return 0.0
    return round(v * 2) / 2


def clean_id(x: Any) -> str:
    """
    Normalize id strings: strip, remove NBSP, handle NaN.
    """
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    s = str(x)
    s = s.replace("\u00A0", "").replace("\u200b", "").strip()
    if s.lower() == "nan":
        return ""
    return s


# =========================================================
# Load required tables 讀取表格
# =========================================================

# Character tables
character_index_df = load_sheet("Character.xlsx", "CharacterIndex")
base_stat_df = load_sheet("Character.xlsx", "CharacterBaseStatByLevel")

# InputPanel
combat_input_df = load_sheet("CombatInputPanel.xlsx", "CombatInputPanel")

# Equipment table
equipment_df = load_sheet("Equipment.xlsx", "Equipment")

# Partner tables (split load)
partner_level_df = load_sheet("Partner.xlsx", "PartnerLevelStat")
partner_stack_df = load_sheet("Partner.xlsx", "PartnerStatStack")
partner_type_df = load_sheet("Partner.xlsx", "PartnerStatType")

# Affection table
affection_df = load_sheet("Affection.xlsx", "AffectionByLevel")


# =========================================================
# Normalize dtypes + key fields (IMPORTANT)
# =========================================================

# --- Base stats ---
if "Level" in base_stat_df.columns:
    base_stat_df["Level"] = pd.to_numeric(base_stat_df["Level"], errors="coerce").fillna(0.0).astype(float)
    base_stat_df["Level"] = base_stat_df["Level"].map(norm_level_to_half)
if "CharacterId" in base_stat_df.columns:
    base_stat_df["CharacterId"] = base_stat_df["CharacterId"].map(clean_id)

# --- Combat input ---
if "CharacterId" in combat_input_df.columns:
    combat_input_df["CharacterId"] = combat_input_df["CharacterId"].map(clean_id)
if "Level" in combat_input_df.columns:
    combat_input_df["Level"] = pd.to_numeric(combat_input_df["Level"], errors="coerce").fillna(0.0).astype(float)
    combat_input_df["Level"] = combat_input_df["Level"].map(norm_level_to_half)

if "PartnerId" in combat_input_df.columns:
    combat_input_df["PartnerId"] = combat_input_df["PartnerId"].map(clean_id)
if "PartnerLevel" in combat_input_df.columns:
    combat_input_df["PartnerLevel"] = pd.to_numeric(combat_input_df["PartnerLevel"], errors="coerce").fillna(0.0).astype(float)
    combat_input_df["PartnerLevel"] = combat_input_df["PartnerLevel"].map(norm_level_to_half)

if "PartnerStackCount" in combat_input_df.columns:
    combat_input_df["PartnerStackCount"] = pd.to_numeric(combat_input_df["PartnerStackCount"], errors="coerce").fillna(0).astype(int)

# --- Partner level stat ---
if "PartnerId" in partner_level_df.columns:
    partner_level_df["PartnerId"] = partner_level_df["PartnerId"].map(clean_id)
if "Level" in partner_level_df.columns:
    partner_level_df["Level"] = pd.to_numeric(partner_level_df["Level"], errors="coerce").fillna(0.0).astype(float)
    partner_level_df["Level"] = partner_level_df["Level"].map(norm_level_to_half)

# --- Partner stack ---
if "PartnerId" in partner_stack_df.columns:
    partner_stack_df["PartnerId"] = partner_stack_df["PartnerId"].map(clean_id)
if "StatTypeId" in partner_stack_df.columns:
    partner_stack_df["StatTypeId"] = partner_stack_df["StatTypeId"].map(clean_id)

for col in ["Stack0Value", "Stack1Value", "Stack2Value", "Stack3Value", "Stack4Value"]:
    if col in partner_stack_df.columns:
        partner_stack_df[col] = pd.to_numeric(partner_stack_df[col], errors="coerce").fillna(0.0).astype(float)

# --- Partner type ---
if "StatTypeId" in partner_type_df.columns:
    partner_type_df["StatTypeId"] = partner_type_df["StatTypeId"].map(clean_id)
if "AffectStat" in partner_type_df.columns:
    partner_type_df["AffectStat"] = partner_type_df["AffectStat"].map(clean_id)

# --- Affection ---
if "AffectionLevel" in affection_df.columns:
    affection_df["AffectionLevel"] = pd.to_numeric(affection_df["AffectionLevel"], errors="coerce").fillna(0).astype(int)
for col in ["AttackTotal", "DefenseTotal", "HealthTotal"]:
    if col in affection_df.columns:
        affection_df[col] = pd.to_numeric(affection_df[col], errors="coerce").fillna(0.0).astype(float)
if "ApplyStage" in affection_df.columns:
    affection_df["ApplyStage"] = affection_df["ApplyStage"].map(clean_id)

# =========================================================
# Partner Lookup Helpers 夥伴數值輔助函式
# =========================================================

def get_partner_flat(partner_id: Any, partner_level: Any) -> Tuple[float, float, float]:
    """
    PARTNER FLAT from PartnerLevelStat by (PartnerId, Level).
    Returns (atk_flat, def_flat, hp_flat).
    """
    pid = clean_id(partner_id)
    if pid == "":
        return 0.0, 0.0, 0.0

    lvl = norm_level_to_half(partner_level)
    if lvl <= 0:
        return 0.0, 0.0, 0.0

    rows = partner_level_df[
        (partner_level_df["PartnerId"] == pid) &
        (partner_level_df["Level"] == lvl)
    ]
    if rows.empty:
        # Debug: Check if ID exists at all to give better feedback
        check_id = partner_level_df[partner_level_df["PartnerId"] == pid]
        if check_id.empty:
            print(f"⚠️ PartnerLevelStat not found: PartnerId='{pid}' (ID not in table). Sample IDs: {partner_level_df['PartnerId'].head(5).tolist()}")
        else:
            avail = sorted(check_id["Level"].unique())
            print(f"⚠️ PartnerLevelStat found '{pid}' but Level={lvl} missing. Available Levels: {avail}")
        return 0.0, 0.0, 0.0

    r = rows.iloc[0]
    return float(r.get("Attack", 0.0)), float(r.get("Defense", 0.0)), float(r.get("Health", 0.0))


def get_partner_pct(partner_id: Any, stack_count: int, is_bonus_applied: bool) -> Tuple[float, float, float]:
    """
    PARTNER % INCREASE from PartnerStatStack + PartnerStatType
    - If is_bonus_applied is False: returns (0,0,0)
    - Assumes StaticBase has only ONE stat type per partner (as per your rule).
    Returns (atk_pct, def_pct, hp_pct) with unit like 0.12 = +12%
    """
    if not is_bonus_applied:
        return 0.0, 0.0, 0.0

    pid = clean_id(partner_id)
    if pid == "":
        return 0.0, 0.0, 0.0

    idx = clamp_int(stack_count, 0, 4, default=0)
    value_col = f"Stack{idx}Value"

    stack_rows = partner_stack_df[partner_stack_df["PartnerId"] == pid]
    if stack_rows.empty:
        print(f"⚠️ PartnerStatStack not found: PartnerId={pid}")
        return 0.0, 0.0, 0.0

    if len(stack_rows) > 1:
        print(f"⚠️ PartnerStatStack has multiple rows for PartnerId={pid}. Using first row only (StaticBase rule).")

    sr = stack_rows.iloc[0]
    stat_type_id = clean_id(sr.get("StatTypeId", ""))
    pct_value = float(sr.get(value_col, 0.0))

    if stat_type_id == "":
        print(f"⚠️ PartnerStatStack missing StatTypeId: PartnerId={pid}")
        return 0.0, 0.0, 0.0

    type_rows = partner_type_df[partner_type_df["StatTypeId"] == stat_type_id]
    if type_rows.empty:
        print(f"⚠️ PartnerStatType not found: StatTypeId={stat_type_id}")
        return 0.0, 0.0, 0.0

    tr = type_rows.iloc[0]

    apply_stage = clean_id(tr.get("ApplyStage", ""))
    value_type = clean_id(tr.get("ValueType", ""))
    is_percent_bool = to_bool(tr.get("IsPercent", False))

    if apply_stage != "StaticBase":
        return 0.0, 0.0, 0.0
    if value_type != "Increase" or not is_percent_bool:
        return 0.0, 0.0, 0.0

    affect_stat = clean_id(tr.get("AffectStat", ""))  # Attack/Defense/Health
    atk_pct = def_pct = hp_pct = 0.0

    if affect_stat == "Attack":
        atk_pct = pct_value
    elif affect_stat == "Defense":
        def_pct = pct_value
    elif affect_stat == "Health":
        hp_pct = pct_value
    else:
        print(f"⚠️ Unknown AffectStat='{affect_stat}' in PartnerStatType: StatTypeId={stat_type_id}")

    return atk_pct, def_pct, hp_pct


# =========================================================
# Affection Lookup Helper
# =========================================================

def get_affection_flat(affection_level: Any) -> Tuple[float, float, float]:
    """
    AFFECTION FLAT from AffectionByLevel (StaticBase).
    Returns (atk_flat, def_flat, hp_flat) where each is Total value for that level.
    """
    if affection_level is None or (isinstance(affection_level, float) and pd.isna(affection_level)):
        lvl = 1
    else:
        try:
            lvl = int(float(affection_level))
        except Exception:
            lvl = 1

    rows = affection_df[
        (affection_df["AffectionLevel"] == lvl) &
        (affection_df["ApplyStage"] == "StaticBase")
    ]

    if rows.empty:
        print(f"⚠️ AffectionByLevel not found: AffectionLevel={lvl} (use 0)")
        return 0.0, 0.0, 0.0

    r = rows.iloc[0]
    atk = float(r.get("AttackTotal", 0.0))
    defense = float(r.get("DefenseTotal", 0.0))
    hp = float(r.get("HealthTotal", 0.0))
    return atk, defense, hp


# =========================================================
# Core Calculation (Current Phase: Base + Partner + Affection + EquipmentFlat)
# =========================================================

def calc_final_base_stats(input_row: pd.Series) -> Dict[str, Any] | None:
    """
    Current calculation:
    Final = (BASE * (1 + %Inc) + PARTNER_FLAT + GEAR_FLAT + AFFECTION_FLAT)
            * (1 + PARTNER_% + EQUIPMENT_%)
            + EQUIPMENT_FLAT

    Implemented now:
    - BASE from CharacterBaseStatByLevel
    - PARTNER_FLAT from PartnerLevelStat
    - PARTNER_% from PartnerStatStack/Type (when IsPartnerBonusApplied)
    - AFFECTION_FLAT from AffectionByLevel
    - EQUIPMENT_FLAT from Equipment MainStat (Flat only)

    Not yet (set to 0):
    - ATK/DEF/HP %Increase (potential nodes)
    - GEAR FLAT (memory fragments)
    - EQUIPMENT % (other equip increases)
    """
    # -----------------------------------------------------
    # 1. Unpack combat input
    # -----------------------------------------------------
    character_id = clean_id(input_row.get("CharacterId", ""))
    level = norm_level_to_half(input_row.get("Level", 0.0))

    equipment_id = input_row.get("EquipmentIdList[]", 0)

    partner_id = input_row.get("PartnerId", "")
    partner_level = input_row.get("PartnerLevel", None)
    partner_stack_count = input_row.get("PartnerStackCount", 0)
    is_partner_bonus_applied = to_bool(input_row.get("IsPartnerBonusApplied", False))

    affection_level = input_row.get("AffectionLevel", 1)

    # -----------------------------------------------------
    # 2. Base stat lookup
    # -----------------------------------------------------
    base_rows = base_stat_df[
        (base_stat_df["CharacterId"] == character_id) &
        (base_stat_df["Level"] == level)
    ]

    if base_rows.empty:
        print(f"❌ Base stat not found: {character_id} Lv{level}")
        return None

    base_row = base_rows.iloc[0]
    base_atk = float(base_row.get("Attack", 0.0))
    base_def = float(base_row.get("Defense", 0.0))
    base_hp = float(base_row.get("Health", 0.0))

    # -----------------------------------------------------
    # 3. Not implemented yet -> 0
    # -----------------------------------------------------
    atk_pct_increase = 0.0
    def_pct_increase = 0.0
    hp_pct_increase = 0.0

    gear_flat_atk = 0.0
    gear_flat_def = 0.0
    gear_flat_hp = 0.0

    equipment_atk_pct = 0.0
    equipment_def_pct = 0.0
    equipment_hp_pct = 0.0

    # -----------------------------------------------------
    # 4. Partner buckets
    # -----------------------------------------------------
    partner_atk_flat, partner_def_flat, partner_hp_flat = get_partner_flat(partner_id, partner_level)
    partner_atk_pct, partner_def_pct, partner_hp_pct = get_partner_pct(
        partner_id=partner_id,
        stack_count=partner_stack_count,
        is_bonus_applied=is_partner_bonus_applied
    )

    # -----------------------------------------------------
    # 5. Affection buckets
    # -----------------------------------------------------
    affection_flat_atk, affection_flat_def, affection_flat_hp = get_affection_flat(affection_level)

    # -----------------------------------------------------
    # 6. Equipment main stat -> EQUIPMENT_FLAT bucket
    # -----------------------------------------------------
    equipment_atk_flat = 0.0
    equipment_def_flat = 0.0
    equipment_hp_flat = 0.0

    if equipment_id not in (0, None, "") and not (isinstance(equipment_id, float) and pd.isna(equipment_id)):
        equip_rows = equipment_df[equipment_df["EquipmentId"] == equipment_id]
        if equip_rows.empty:
            print(f"⚠️ Equipment not found: {equipment_id}")
        else:
            equip_row = equip_rows.iloc[0]
            stat_type = clean_id(equip_row.get("MainStatType", ""))
            value = float(equip_row.get("MainStatValue", 0.0))

            if stat_type == "ATK_FLAT":
                equipment_atk_flat += value
            elif stat_type == "DEF_FLAT":
                equipment_def_flat += value
            elif stat_type == "HP_FLAT":
                equipment_hp_flat += value
            else:
                print(f"⚠️ Unknown Equipment MainStatType='{stat_type}' for EquipmentId={equipment_id}")

    # -----------------------------------------------------
    # 7. Apply formulas
    # -----------------------------------------------------
    atk_base_block = base_atk * (1.0 + atk_pct_increase) + partner_atk_flat + gear_flat_atk + affection_flat_atk
    atk_multiplier = 1.0 + partner_atk_pct + equipment_atk_pct
    final_atk = atk_base_block * atk_multiplier + equipment_atk_flat

    def_base_block = base_def * (1.0 + def_pct_increase) + partner_def_flat + gear_flat_def + affection_flat_def
    def_multiplier = 1.0 + partner_def_pct + equipment_def_pct
    final_def = def_base_block * def_multiplier + equipment_def_flat

    hp_base_block = base_hp * (1.0 + hp_pct_increase) + partner_hp_flat + gear_flat_hp + affection_flat_hp
    hp_multiplier = 1.0 + partner_hp_pct + equipment_hp_pct
    final_hp = hp_base_block * hp_multiplier + equipment_hp_flat

    # -----------------------------------------------------
    # 8. Logs
    # -----------------------------------------------------
    print("\n------------------------------------------")
    print(f"Character: {character_id}")
    print(f"Level: {level}")
    print(f"[Base] ATK={base_atk}, DEF={base_def}, HP={base_hp}")

    print(f"[Affection] Level={affection_level} -> Flat: ATK={affection_flat_atk}, DEF={affection_flat_def}, HP={affection_flat_hp}")

    pid_str = clean_id(partner_id)
    if pid_str != "":
        sc = clamp_int(partner_stack_count, 0, 4, default=0)
        pl = norm_level_to_half(partner_level)
        print(f"[Partner] PartnerId={pid_str}, PartnerLevel={pl}, StackCount={sc}, BonusApplied={is_partner_bonus_applied}")
        print(f"         Flat: ATK={partner_atk_flat}, DEF={partner_def_flat}, HP={partner_hp_flat}")
        print(f"         Pct : ATK%={partner_atk_pct}, DEF%={partner_def_pct}, HP%={partner_hp_pct}")
    else:
        print("[Partner] None")

    if equipment_atk_flat or equipment_def_flat or equipment_hp_flat:
        print(f"[EquipmentFlat] ATK={equipment_atk_flat}, DEF={equipment_def_flat}, HP={equipment_hp_flat}")
    else:
        print("[EquipmentFlat] None/0")

    print(f"[Final] ATK={final_atk:.4f}, DEF={final_def:.4f}, HP={final_hp:.4f}")

    return {
        "CharacterId": character_id,
        "Level": level,
        "FinalATK": final_atk,
        "FinalDEF": final_def,
        "FinalHP": final_hp,
    }


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":
    print("\n========== Current Phase: Base + Partner + Affection + EquipmentFlat ==========")

    results = []
    for _, row in combat_input_df.iterrows():
        result = calc_final_base_stats(row)
        if result:
            results.append(result)

    print("\n========== All Calculations Done ==========")

    out_df = pd.DataFrame(results)
    print("\n=== Summary ===")
    if not out_df.empty:
        print(out_df.to_string(index=False))
    else:
        print("(no results)")
