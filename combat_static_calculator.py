"""
combat_static_calculator.py

Phase: Static / Pre-combat
Responsibility:
- Calculate final base ATK / DEF / HP before battle
- Includes Character / Partner / Affection / Equipment / MemoryFragment
- No card, no turn, no enemy logic
"""


# CombatCalculatorTest.py
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional

# =========================================================
# Path & Loader
# =========================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


def load_sheet(excel_name: str, sheet_name: str) -> pd.DataFrame:
    path = DATA_DIR / excel_name
    if not path.exists():
        raise FileNotFoundError(f"❌ Excel file not found: {path}")

    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except ValueError:
        raise ValueError(f"❌ Sheet '{sheet_name}' not found in {excel_name}")

    # Strip whitespace from column headers
    df.columns = df.columns.astype(str).str.strip()
    return df


# =========================================================
# Utils
# =========================================================

def to_bool(value: Any) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

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
    try:
        return bool(value)
    except Exception:
        return False


def clean_id(x: Any) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x).replace("\u00A0", "").replace("\u200b", "").strip()
    if s.lower() in ("nan", "none", ""):
        return ""
    return s


def norm_level_to_half(x: Any) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    return round(v * 2) / 2


def to_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip().lower() in ("", "none", "nan"):
            return default
        v = int(float(x))
        return v
    except Exception:
        return default


def to_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip().lower() in ("", "none", "nan"):
            return default
        v = float(x)
        return v
    except Exception:
        return default


def clamp_int(x: int, lo: int, hi: int) -> int:
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def is_empty_cell(x: Any) -> bool:
    return clean_id(x) == ""


def stat_affect_bucket(stat_type_id: str) -> Optional[str]:
    """
    Infer which main stat this StatType affects by naming.
    - Attack* -> Attack
    - Defense* -> Defense
    - HealthPoint* -> Health
    """
    s = stat_type_id.lower()
    if "attack" in s:
        return "Attack"
    if "defense" in s or "defence" in s:
        return "Defense"
    if "healthpoint" in s or "hp" == s:
        return "Health"
    return None


def warn_percent_sanity(source: str, stat_type_id: str, is_percent: bool, value: float):
    # 你指定的防呆：IsPercent=True 但值 > 1 就警告
    if is_percent and value > 1.0:
        print(f"⚠️ [{source}] IsPercent=True but value>1: StatTypeId={stat_type_id}, value={value}. "
              f"(你規則是 0.12 = 12%)")


# =========================================================
# Load tables
# =========================================================

character_index_df = load_sheet("Character.xlsx", "CharacterIndex")
base_stat_df = load_sheet("Character.xlsx", "CharacterBaseStatByLevel")

combat_input_df = load_sheet("CombatInputPanel.xlsx", "CombatInputPanel")

partner_level_df = load_sheet("Partner.xlsx", "PartnerLevelStat")
partner_stack_df = load_sheet("Partner.xlsx", "PartnerStatStack")
partner_type_df = load_sheet("Partner.xlsx", "PartnerStatType")

affection_df = load_sheet("Affection.xlsx", "AffectionByLevel")

# Equipment
equipment_df = load_sheet("Equipment.xlsx", "Equipment")
equipment_stat_type_df = load_sheet("Equipment.xlsx", "EquipmentStatType")

# Memory Fragment
mf_base_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentBase")
mf_level_stats_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentLevelStats")
mf_stat_type_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentStatType")
mf_set_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentSet")


# =========================================================
# Normalize key dtypes
# =========================================================

# --- Base stats ---
if "Level" in base_stat_df.columns:
    base_stat_df["Level"] = pd.to_numeric(base_stat_df["Level"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)
if "CharacterId" in base_stat_df.columns:
    base_stat_df["CharacterId"] = base_stat_df["CharacterId"].map(clean_id)

# --- Combat input ---
for c in ["CharacterId", "PartnerId", "IsPartnerBonusApplied", "EquipmentIdList[]",
          "FragmentIdList[]", "FragmentLevelList[]", "FragmentRandomStatList[]", "FragmentRandomValueList[]"]:
    if c in combat_input_df.columns and combat_input_df[c].dtype != object:
        combat_input_df[c] = combat_input_df[c].astype(object)

if "CharacterId" in combat_input_df.columns:
    combat_input_df["CharacterId"] = combat_input_df["CharacterId"].map(clean_id)

if "Level" in combat_input_df.columns:
    combat_input_df["Level"] = pd.to_numeric(combat_input_df["Level"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)

if "PartnerLevel" in combat_input_df.columns:
    combat_input_df["PartnerLevel"] = pd.to_numeric(combat_input_df["PartnerLevel"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)

if "PartnerStackCount" in combat_input_df.columns:
    combat_input_df["PartnerStackCount"] = pd.to_numeric(combat_input_df["PartnerStackCount"], errors="coerce").fillna(0).astype(int)

if "AffectionLevel" in combat_input_df.columns:
    combat_input_df["AffectionLevel"] = pd.to_numeric(combat_input_df["AffectionLevel"], errors="coerce").fillna(1).astype(int)

# --- Partner tables ---
if "PartnerId" in partner_level_df.columns:
    partner_level_df["PartnerId"] = partner_level_df["PartnerId"].map(clean_id)
if "Level" in partner_level_df.columns:
    partner_level_df["Level"] = pd.to_numeric(partner_level_df["Level"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)

if "PartnerId" in partner_stack_df.columns:
    partner_stack_df["PartnerId"] = partner_stack_df["PartnerId"].map(clean_id)
if "StatTypeId" in partner_stack_df.columns:
    partner_stack_df["StatTypeId"] = partner_stack_df["StatTypeId"].map(clean_id)
for col in ["Stack0Value", "Stack1Value", "Stack2Value", "Stack3Value", "Stack4Value"]:
    if col in partner_stack_df.columns:
        partner_stack_df[col] = pd.to_numeric(partner_stack_df[col], errors="coerce").fillna(0.0).astype(float)

if "StatTypeId" in partner_type_df.columns:
    partner_type_df["StatTypeId"] = partner_type_df["StatTypeId"].map(clean_id)
for col in ["AffectStat", "ApplyStage", "ValueType"]:
    if col in partner_type_df.columns:
        partner_type_df[col] = partner_type_df[col].map(clean_id)

# --- Affection ---
if "ApplyStage" in affection_df.columns:
    affection_df["ApplyStage"] = affection_df["ApplyStage"].map(clean_id)
if "AffectionLevel" in affection_df.columns:
    affection_df["AffectionLevel"] = pd.to_numeric(affection_df["AffectionLevel"], errors="coerce").fillna(1).astype(int)
for col in ["AttackTotal", "DefenseTotal", "HealthTotal"]:
    if col in affection_df.columns:
        affection_df[col] = pd.to_numeric(affection_df[col], errors="coerce").fillna(0.0).astype(float)

# --- Equipment ---
if "EquipmentId" in equipment_df.columns:
    equipment_df["EquipmentId"] = equipment_df["EquipmentId"].map(clean_id)
if "StatTypeId" in equipment_df.columns:
    equipment_df["StatTypeId"] = equipment_df["StatTypeId"].map(clean_id)
if "Value" in equipment_df.columns:
    equipment_df["Value"] = pd.to_numeric(equipment_df["Value"], errors="coerce").fillna(0.0).astype(float)

if "StatTypeId" in equipment_stat_type_df.columns:
    equipment_stat_type_df["StatTypeId"] = equipment_stat_type_df["StatTypeId"].map(clean_id)
for col in ["ValueType", "ApplyStage"]:
    if col in equipment_stat_type_df.columns:
        equipment_stat_type_df[col] = equipment_stat_type_df[col].map(clean_id)

# --- Memory Fragment ---
if "FragmentId" in mf_base_df.columns:
    mf_base_df["FragmentId"] = mf_base_df["FragmentId"].map(clean_id)
if "SetTypeId" in mf_base_df.columns:
    mf_base_df["SetTypeId"] = mf_base_df["SetTypeId"].map(clean_id)

if "FragmentId" in mf_level_stats_df.columns:
    mf_level_stats_df["FragmentId"] = mf_level_stats_df["FragmentId"].map(clean_id)
if "StatTypeId" in mf_level_stats_df.columns:
    mf_level_stats_df["StatTypeId"] = mf_level_stats_df["StatTypeId"].map(clean_id)
for col in ["MaxLevel", "BaseValue", "PerLevel"]:
    if col in mf_level_stats_df.columns:
        mf_level_stats_df[col] = pd.to_numeric(mf_level_stats_df[col], errors="coerce").fillna(0.0)

if "StatTypeId" in mf_stat_type_df.columns:
    mf_stat_type_df["StatTypeId"] = mf_stat_type_df["StatTypeId"].map(clean_id)
for col in ["ValueType", "ApplyStage"]:
    if col in mf_stat_type_df.columns:
        mf_stat_type_df[col] = mf_stat_type_df[col].map(clean_id)

if "SetTypeId" in mf_set_df.columns:
    mf_set_df["SetTypeId"] = mf_set_df["SetTypeId"].map(clean_id)
if "StatTypeId" in mf_set_df.columns:
    mf_set_df["StatTypeId"] = mf_set_df["StatTypeId"].map(clean_id)
if "RequiredPiece" in mf_set_df.columns:
    mf_set_df["RequiredPiece"] = pd.to_numeric(mf_set_df["RequiredPiece"], errors="coerce").fillna(0).astype(int)
if "Value" in mf_set_df.columns:
    mf_set_df["Value"] = pd.to_numeric(mf_set_df["Value"], errors="coerce").fillna(0.0).astype(float)
if "ApplyStage" in mf_set_df.columns:
    mf_set_df["ApplyStage"] = mf_set_df["ApplyStage"].map(clean_id)


# =========================================================
# Input Panel Parsing: one character occupies multiple rows
# =========================================================

def iter_character_blocks(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Parse CombatInputPanel where one character can occupy multiple rows.
    Rule:
    - A row with non-empty CharacterId starts a new block.
    - Subsequent rows until next CharacterId belong to that block.
    """
    blocks: List[Dict[str, Any]] = []
    current = None

    for _, row in df.iterrows():
        cid = clean_id(row.get("CharacterId", ""))
        if cid != "":
            # start new
            if current is not None:
                blocks.append(current)
            current = {"base_row": row, "rows": [row]}
        else:
            if current is not None:
                current["rows"].append(row)
            # if current is None and cid empty: ignore stray lines

    if current is not None:
        blocks.append(current)
    return blocks


# =========================================================
# Partner helpers
# =========================================================

def get_partner_flat(partner_id: Any, partner_level: Any) -> Tuple[float, float, float]:
    pid = clean_id(partner_id)
    if pid == "":
        return 0.0, 0.0, 0.0
    lvl = norm_level_to_half(partner_level)
    if lvl <= 0:
        return 0.0, 0.0, 0.0

    rows = partner_level_df[(partner_level_df["PartnerId"] == pid) & (partner_level_df["Level"] == lvl)]
    if rows.empty:
        return 0.0, 0.0, 0.0
    r = rows.iloc[0]
    return float(r.get("Attack", 0.0)), float(r.get("Defense", 0.0)), float(r.get("Health", 0.0))


def get_partner_pct(partner_id: Any, stack_count: int, is_bonus_applied: bool) -> Tuple[float, float, float]:
    if not is_bonus_applied:
        return 0.0, 0.0, 0.0

    pid = clean_id(partner_id)
    if pid == "":
        return 0.0, 0.0, 0.0

    idx = clamp_int(int(stack_count), 0, 4)
    value_col = f"Stack{idx}Value"

    stack_rows = partner_stack_df[partner_stack_df["PartnerId"] == pid]
    if stack_rows.empty:
        return 0.0, 0.0, 0.0

    sr = stack_rows.iloc[0]
    stat_type_id = clean_id(sr.get("StatTypeId", ""))
    pct_value = float(sr.get(value_col, 0.0))

    type_rows = partner_type_df[partner_type_df["StatTypeId"] == stat_type_id]
    if type_rows.empty:
        return 0.0, 0.0, 0.0
    tr = type_rows.iloc[0]

    apply_stage = clean_id(tr.get("ApplyStage", ""))
    value_type = clean_id(tr.get("ValueType", ""))
    is_percent = to_bool(tr.get("IsPercent", False))
    affect_stat = clean_id(tr.get("AffectStat", ""))

    if apply_stage != "StaticBase":
        return 0.0, 0.0, 0.0
    if value_type != "Increase":
        return 0.0, 0.0, 0.0
    if not is_percent:
        return 0.0, 0.0, 0.0

    warn_percent_sanity("Partner", stat_type_id, is_percent, pct_value)

    atk = defv = hp = 0.0
    if affect_stat == "Attack":
        atk = pct_value
    elif affect_stat == "Defense":
        defv = pct_value
    elif affect_stat == "Health":
        hp = pct_value
    return atk, defv, hp


# =========================================================
# Affection helper
# =========================================================

def get_affection_flat(affection_level: Any) -> Tuple[float, float, float]:
    lvl = to_int(affection_level, default=1)
    rows = affection_df[(affection_df["AffectionLevel"] == lvl) & (affection_df["ApplyStage"] == "StaticBase")]
    if rows.empty:
        return 0.0, 0.0, 0.0
    r = rows.iloc[0]
    return float(r.get("AttackTotal", 0.0)), float(r.get("DefenseTotal", 0.0)), float(r.get("HealthTotal", 0.0))


# =========================================================
# Equipment calc (Flat + Increase)
# =========================================================

def apply_stat_by_type(source: str,
                       stat_type_df: pd.DataFrame,
                       stat_type_id: str,
                       value: float,
                       atk_pct_ref: Dict[str, float],
                       def_pct_ref: Dict[str, float],
                       hp_pct_ref: Dict[str, float],
                       atk_flat_ref: Dict[str, float],
                       def_flat_ref: Dict[str, float],
                       hp_flat_ref: Dict[str, float]):
    """
    Use StatType table to decide:
    - ApplyStage must be StaticBase
    - ValueType: Flat / Increase
    - IsPercent is only sanity check
    """
    stid = clean_id(stat_type_id)
    if stid == "":
        return

    rows = stat_type_df[stat_type_df["StatTypeId"] == stid]
    if rows.empty:
        print(f"⚠️ [{source}] StatTypeId not found in StatType table: {stid} (skip)")
        return

    r = rows.iloc[0]
    apply_stage = clean_id(r.get("ApplyStage", ""))
    value_type = clean_id(r.get("ValueType", ""))
    is_percent = to_bool(r.get("IsPercent", False))

    if apply_stage != "StaticBase":
        return

    warn_percent_sanity(source, stid, is_percent, value)

    affect = stat_affect_bucket(stid)
    if affect is None:
        print(f"⚠️ [{source}] Cannot infer affect stat from StatTypeId={stid} (skip)")
        return

    if value_type == "Increase":
        if affect == "Attack":
            atk_pct_ref["v"] += value
        elif affect == "Defense":
            def_pct_ref["v"] += value
        elif affect == "Health":
            hp_pct_ref["v"] += value
    else:
        # treat everything else as Flat
        if affect == "Attack":
            atk_flat_ref["v"] += value
        elif affect == "Defense":
            def_flat_ref["v"] += value
        elif affect == "Health":
            hp_flat_ref["v"] += value


def calc_equipment_contribution(rows: List[pd.Series]) -> Tuple[float, float, float, float, float, float]:
    """
    EquipmentIdList[] is a column, but in your multi-row panel style:
    equipment id usually sits on the same row as other info.
    We'll gather all non-None equipment ids from all rows in the character block.
    """
    equipment_ids: List[str] = []
    for r in rows:
        eid = clean_id(r.get("EquipmentIdList[]", ""))
        if eid != "":
            equipment_ids.append(eid)

    # remove duplicates but keep order
    seen = set()
    equipment_ids = [x for x in equipment_ids if not (x in seen or seen.add(x))]

    atk_pct = {"v": 0.0}
    def_pct = {"v": 0.0}
    hp_pct = {"v": 0.0}
    atk_flat = {"v": 0.0}
    def_flat = {"v": 0.0}
    hp_flat = {"v": 0.0}

    if equipment_ids:
        print(f"[EquipmentIds] {equipment_ids}")

    for eid in equipment_ids:
        eq_rows = equipment_df[equipment_df["EquipmentId"] == eid]
        if eq_rows.empty:
            print(f"⚠️ [Equipment] EquipmentId not found: {eid}")
            continue

        for _, eqr in eq_rows.iterrows():
            stid = clean_id(eqr.get("StatTypeId", ""))
            val = float(eqr.get("Value", 0.0))
            apply_stat_by_type(
                source="Equipment",
                stat_type_df=equipment_stat_type_df,
                stat_type_id=stid,
                value=val,
                atk_pct_ref=atk_pct, def_pct_ref=def_pct, hp_pct_ref=hp_pct,
                atk_flat_ref=atk_flat, def_flat_ref=def_flat, hp_flat_ref=hp_flat
            )

    return atk_pct["v"], def_pct["v"], hp_pct["v"], atk_flat["v"], def_flat["v"], hp_flat["v"]


# =========================================================
# Memory Fragment parsing + contribution (Main + Random + Set)
# =========================================================

def calc_fragment_main_stat(fragment_id: str, enhance_level: int) -> Tuple[str, float]:
    """
    Read MemoryFragmentLevelStats to compute main stat value.
    value = BaseValue + PerLevel * enhance_level
    enhance_level allows 0 (no enhancement).
    """
    fid = clean_id(fragment_id)
    rows = mf_level_stats_df[mf_level_stats_df["FragmentId"] == fid]
    if rows.empty:
        return "", 0.0

    r = rows.iloc[0]
    max_level = to_int(r.get("MaxLevel", 0), default=0)
    stid = clean_id(r.get("StatTypeId", ""))
    base_value = to_float(r.get("BaseValue", 0.0), default=0.0)
    per_level = to_float(r.get("PerLevel", 0.0), default=0.0)

    lv = clamp_int(to_int(enhance_level, 0), 0, max_level)
    value = base_value + per_level * lv
    return stid, value


def calc_memory_fragment_contribution(block_rows: List[pd.Series]) -> Tuple[float, float, float, float, float, float]:
    """
    Returns:
    (atk_pct, def_pct, hp_pct, gear_flat_atk, gear_flat_def, gear_flat_hp)
    """
    atk_pct = {"v": 0.0}
    def_pct = {"v": 0.0}
    hp_pct = {"v": 0.0}
    atk_flat = {"v": 0.0}  # Phase1 的 GEAR FLAT（碎片來源）
    def_flat = {"v": 0.0}
    hp_flat = {"v": 0.0}

    # --- Parse fragments in multi-line style ---
    fragments: List[Dict[str, Any]] = []
    current_frag = None

    for r in block_rows:
        fid = clean_id(r.get("FragmentIdList[]", ""))
        if fid != "":
            # start new fragment
            enhance_lv = to_int(r.get("FragmentLevelList[]", 0), default=0)  # allow 0
            current_frag = {
                "FragmentId": fid,
                "EnhanceLevel": enhance_lv,
                "RandomStats": []  # list of (statTypeId, value)
            }
            fragments.append(current_frag)

        # random stat lines (may be listed vertically)
        rs = clean_id(r.get("FragmentRandomStatList[]", ""))
        rv_raw = r.get("FragmentRandomValueList[]", None)
        rv = to_float(rv_raw, default=0.0)

        if current_frag is not None:
            # Accept random stat lines only if stat is not None/empty
            if rs != "":
                current_frag["RandomStats"].append((rs, rv))

    if fragments:
        print("[MemoryFragment]")

    # --- Apply main + random stats ---
    all_fragment_ids: List[str] = []
    for frag in fragments:
        fid = frag["FragmentId"]
        all_fragment_ids.append(fid)

        enhance_lv = frag["EnhanceLevel"]
        stid, main_val = calc_fragment_main_stat(fid, enhance_lv)
        if stid != "":
            apply_stat_by_type(
                source="MF-Main",
                stat_type_df=mf_stat_type_df,
                stat_type_id=stid,
                value=main_val,
                atk_pct_ref=atk_pct, def_pct_ref=def_pct, hp_pct_ref=hp_pct,
                atk_flat_ref=atk_flat, def_flat_ref=def_flat, hp_flat_ref=hp_flat
            )
            print(f"✅ [MF-Main] {fid} Lv={enhance_lv} Stat={stid} Value={main_val}")

        # random stats
        for (rsid, rvalue) in frag["RandomStats"]:
            # 你目前用手填：rvalue 就視為最後值（可為 flat 或 increase）
            apply_stat_by_type(
                source="MF-Random",
                stat_type_df=mf_stat_type_df,
                stat_type_id=rsid,
                value=rvalue,
                atk_pct_ref=atk_pct, def_pct_ref=def_pct, hp_pct_ref=hp_pct,
                atk_flat_ref=atk_flat, def_flat_ref=def_flat, hp_flat_ref=hp_flat
            )

    # --- Set bonus (NEW) ---
    # Map FragmentId -> SetTypeId from MemoryFragmentBase
    set_counts: Dict[str, int] = {}
    for fid in all_fragment_ids:
        rows = mf_base_df[mf_base_df["FragmentId"] == clean_id(fid)]
        if rows.empty:
            continue
        set_id = clean_id(rows.iloc[0].get("SetTypeId", ""))
        if set_id == "":
            continue
        set_counts[set_id] = set_counts.get(set_id, 0) + 1

    # Apply MemoryFragmentSet bonuses
    for set_id, cnt in set_counts.items():
        bonus_rows = mf_set_df[(mf_set_df["SetTypeId"] == set_id) & (mf_set_df["ApplyStage"] == "StaticBase")]
        if bonus_rows.empty:
            continue

        for _, br in bonus_rows.iterrows():
            need = int(br.get("RequiredPiece", 0))
            if cnt < need:
                continue
            stid = clean_id(br.get("StatTypeId", ""))
            val = float(br.get("Value", 0.0))
            apply_stat_by_type(
                source="MF-Set",
                stat_type_df=mf_stat_type_df,
                stat_type_id=stid,
                value=val,
                atk_pct_ref=atk_pct, def_pct_ref=def_pct, hp_pct_ref=hp_pct,
                atk_flat_ref=atk_flat, def_flat_ref=def_flat, hp_flat_ref=hp_flat
            )
            print(f"🎁 [MF-Set] SetTypeId={set_id} pieces={cnt} (need {need}) -> {stid} +{val}")

    return atk_pct["v"], def_pct["v"], hp_pct["v"], atk_flat["v"], def_flat["v"], hp_flat["v"]


# =========================================================
# Core Calculation per character block
# =========================================================

def calc_final_base_stats_for_block(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    base_row: pd.Series = block["base_row"]
    rows: List[pd.Series] = block["rows"]

    character_id = clean_id(base_row.get("CharacterId", ""))
    level = norm_level_to_half(base_row.get("Level", 0.0))

    partner_id = clean_id(base_row.get("PartnerId", ""))
    partner_level = base_row.get("PartnerLevel", 0.0)
    partner_stack_count = to_int(base_row.get("PartnerStackCount", 0), default=0)
    is_partner_bonus_applied = to_bool(base_row.get("IsPartnerBonusApplied", False))

    affection_level = to_int(base_row.get("AffectionLevel", 1), default=1)

    base_rows = base_stat_df[(base_stat_df["CharacterId"] == character_id) & (base_stat_df["Level"] == level)]
    if base_rows.empty:
        print(f"❌ Base stat not found: {character_id} Lv{level}")
        return None

    br = base_rows.iloc[0]
    base_atk = float(br.get("Attack", 0.0))
    base_def = float(br.get("Defense", 0.0))
    base_hp = float(br.get("Health", 0.0))

    # Phase 1 buckets
    atk_pct_increase = 0.0
    def_pct_increase = 0.0
    hp_pct_increase = 0.0

    gear_flat_atk = 0.0
    gear_flat_def = 0.0
    gear_flat_hp = 0.0

    equipment_atk_pct = 0.0
    equipment_def_pct = 0.0
    equipment_hp_pct = 0.0

    equipment_atk_flat = 0.0
    equipment_def_flat = 0.0
    equipment_hp_flat = 0.0

    # Partner
    partner_atk_flat, partner_def_flat, partner_hp_flat = get_partner_flat(partner_id, partner_level)
    partner_atk_pct, partner_def_pct, partner_hp_pct = get_partner_pct(partner_id, partner_stack_count, is_partner_bonus_applied)

    # Affection (Flat only in your current rules)
    affection_flat_atk, affection_flat_def, affection_flat_hp = get_affection_flat(affection_level)

    # Equipment (Flat + Increase)
    e_atk_pct, e_def_pct, e_hp_pct, e_atk_flat, e_def_flat, e_hp_flat = calc_equipment_contribution(rows)
    equipment_atk_pct += e_atk_pct
    equipment_def_pct += e_def_pct
    equipment_hp_pct += e_hp_pct
    equipment_atk_flat += e_atk_flat
    equipment_def_flat += e_def_flat
    equipment_hp_flat += e_hp_flat

    # MemoryFragment (Main + Random + Set)
    mf_atk_pct, mf_def_pct, mf_hp_pct, mf_atk_flat, mf_def_flat, mf_hp_flat = calc_memory_fragment_contribution(rows)
    atk_pct_increase += mf_atk_pct
    def_pct_increase += mf_def_pct
    hp_pct_increase += mf_hp_pct

    gear_flat_atk += mf_atk_flat
    gear_flat_def += mf_def_flat
    gear_flat_hp += mf_hp_flat

    # =====================================================
    # Final formulas (Phase 1)
    # =====================================================

    atk_base_block = base_atk * (1.0 + atk_pct_increase) + partner_atk_flat + gear_flat_atk + affection_flat_atk
    atk_multiplier = 1.0 + partner_atk_pct + equipment_atk_pct
    final_atk = atk_base_block * atk_multiplier + equipment_atk_flat

    def_base_block = base_def * (1.0 + def_pct_increase) + partner_def_flat + gear_flat_def + affection_flat_def
    def_multiplier = 1.0 + partner_def_pct + equipment_def_pct
    final_def = def_base_block * def_multiplier + equipment_def_flat

    hp_base_block = base_hp * (1.0 + hp_pct_increase) + partner_hp_flat + gear_flat_hp + affection_flat_hp
    hp_multiplier = 1.0 + partner_hp_pct + equipment_hp_pct
    final_hp = hp_base_block * hp_multiplier + equipment_hp_flat

    # Logs
    print("\n------------------------------------------")
    print(f"Character: {character_id}")
    print(f"Level: {level}")
    print(f"[Base] ATK={base_atk}, DEF={base_def}, HP={base_hp}")

    print(f"[Affection] Level={affection_level} -> Flat: ATK={affection_flat_atk}, DEF={affection_flat_def}, HP={affection_flat_hp}")

    if partner_id != "":
        print(f"[Partner] PartnerId={partner_id}, PartnerLevel={norm_level_to_half(partner_level)}, "
              f"StackCount={partner_stack_count}, BonusApplied={is_partner_bonus_applied}")
        print(f"         Flat: ATK={partner_atk_flat}, DEF={partner_def_flat}, HP={partner_hp_flat}")
        print(f"         Pct : ATK%={partner_atk_pct}, DEF%={partner_def_pct}, HP%={partner_hp_pct}")
    else:
        print("[Partner] None")

    print(f"[Phase1 Accum] Increase: ATK%={atk_pct_increase}, DEF%={def_pct_increase}, HP%={hp_pct_increase}")
    print(f"[Phase1 Accum] GearFlat(from MF): ATK={gear_flat_atk}, DEF={gear_flat_def}, HP={gear_flat_hp}")
    print(f"[Phase1 Accum] EquipPct: ATK%={equipment_atk_pct}, DEF%={equipment_def_pct}, HP%={equipment_hp_pct}")
    print(f"[Phase1 Accum] EquipFlat: ATK={equipment_atk_flat}, DEF={equipment_def_flat}, HP={equipment_hp_flat}")

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
    print("\n========== Phase 1: Base + Partner + Affection + Equipment + MemoryFragment ==========")

    blocks = iter_character_blocks(combat_input_df)

    results = []
    for b in blocks:
        r = calc_final_base_stats_for_block(b)
        if r:
            results.append(r)

    print("\n========== All Calculations Done ==========")
    out_df = pd.DataFrame(results)
    print("\n=== Summary ===")
    if not out_df.empty:
        print(out_df.to_string(index=False))
    else:
        print("(no results)")

print("計算完成！")

input("按 Enter 鍵結束程式...")
