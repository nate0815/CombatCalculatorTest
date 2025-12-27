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
        if s in ("false", "f", "no", "n", "0", "", "none", "null"):
            return False

    try:
        return bool(value)
    except Exception:
        return False


def clamp_int(x: Any, lo: int, hi: int, default: int = 0) -> int:
    try:
        v = int(float(x))
    except Exception:
        v = default
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def norm_level_to_half(x: Any) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    return round(v * 2) / 2


def clean_id(x: Any) -> str:
    """Normalize id strings: strip, remove NBSP/zero-width, handle NaN / 'None'."""
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass

    s = str(x).replace("\u00A0", "").replace("\u200b", "").strip()
    if s.lower() in ("nan", "none", "null", ""):
        return ""
    return s


def parse_csv_str_list(x: Any) -> List[str]:
    """
    Accept: 'A,B,C' or 'None' or '' or NaN.
    Also supports cells that were numeric 0.
    """
    if x is None:
        return []
    try:
        if pd.isna(x):
            return []
    except Exception:
        pass

    s = str(x).strip()
    if s == "" or s.lower() in ("none", "null", "nan", "0"):
        return []

    parts = [p.strip() for p in s.split(",")]
    parts = [clean_id(p) for p in parts]
    return [p for p in parts if p != ""]


def parse_csv_num_list(x: Any) -> List[float]:
    if x is None:
        return []
    try:
        if pd.isna(x):
            return []
    except Exception:
        pass

    s = str(x).strip()
    if s == "" or s.lower() in ("none", "null", "nan", "0"):
        return []

    out: List[float] = []
    for p in s.split(","):
        p = p.strip()
        if p == "":
            continue
        try:
            out.append(float(p))
        except Exception:
            out.append(0.0)
    return out


def stat_target_from_stat_type_id(stat_type_id: str) -> Optional[str]:
    """
    Map your StatTypeId naming to target core stat.
    You are using: AttackFlat / DefenseFlat / HealthPointFlat / AttackIncrease ...
    """
    s = clean_id(stat_type_id)
    if s == "":
        return None
    s_low = s.lower()
    if s_low.startswith("attack"):
        return "Attack"
    if s_low.startswith("defense"):
        return "Defense"
    if s_low.startswith("health") or s_low.startswith("healthpoint"):
        return "Health"
    return None


# =========================================================
# Load required tables
# =========================================================

# Character
character_index_df = load_sheet("Character.xlsx", "CharacterIndex")
base_stat_df = load_sheet("Character.xlsx", "CharacterBaseStatByLevel")

# Input
combat_input_df = load_sheet("CombatInputPanel.xlsx", "CombatInputPanel")

# Equipment
equipment_df = load_sheet("Equipment.xlsx", "Equipment")
equipment_stat_type_df = load_sheet("Equipment.xlsx", "EquipmentStatType") if (DATA_DIR / "Equipment.xlsx").exists() else pd.DataFrame()

# Partner
partner_level_df = load_sheet("Partner.xlsx", "PartnerLevelStat")
partner_stack_df = load_sheet("Partner.xlsx", "PartnerStatStack")
partner_type_df = load_sheet("Partner.xlsx", "PartnerStatType")

# Affection
affection_df = load_sheet("Affection.xlsx", "AffectionByLevel")

# Memory Fragment
mf_base_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentBase")
mf_level_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentLevelStats")
mf_set_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentSet")
mf_stat_type_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentStatType")


# =========================================================
# Normalize dtypes + key fields
# =========================================================

# --- Base stats ---
if "Level" in base_stat_df.columns:
    base_stat_df["Level"] = pd.to_numeric(base_stat_df["Level"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)
if "CharacterId" in base_stat_df.columns:
    base_stat_df["CharacterId"] = base_stat_df["CharacterId"].map(clean_id)

# --- Combat input ---
if "CharacterId" in combat_input_df.columns:
    combat_input_df["CharacterId"] = combat_input_df["CharacterId"].map(clean_id)
if "Level" in combat_input_df.columns:
    combat_input_df["Level"] = pd.to_numeric(combat_input_df["Level"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)

for col in ["PartnerId"]:
    if col in combat_input_df.columns:
        combat_input_df[col] = combat_input_df[col].map(clean_id)

if "PartnerLevel" in combat_input_df.columns:
    combat_input_df["PartnerLevel"] = pd.to_numeric(combat_input_df["PartnerLevel"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)

if "PartnerStackCount" in combat_input_df.columns:
    combat_input_df["PartnerStackCount"] = pd.to_numeric(combat_input_df["PartnerStackCount"], errors="coerce").fillna(0).astype(int)

# --- Partner level stat ---
if "PartnerId" in partner_level_df.columns:
    partner_level_df["PartnerId"] = partner_level_df["PartnerId"].map(clean_id)
if "Level" in partner_level_df.columns:
    partner_level_df["Level"] = pd.to_numeric(partner_level_df["Level"], errors="coerce").fillna(0.0).astype(float).map(norm_level_to_half)

# --- Partner stack ---
if "PartnerId" in partner_stack_df.columns:
    partner_stack_df["PartnerId"] = partner_stack_df["PartnerId"].map(clean_id)
if "StatTypeId" in partner_stack_df.columns:
    partner_stack_df["StatTypeId"] = partner_stack_df["StatTypeId"].map(clean_id)

for col in ["Stack0Value", "Stack1Value", "Stack2Value", "Stack3Value", "Stack4Value"]:
    if col in partner_stack_df.columns:
        partner_stack_df[col] = pd.to_numeric(partner_stack_df[col], errors="coerce").fillna(0.0).astype(float)

# --- Partner type ---
for col in ["StatTypeId", "AffectStat", "ApplyStage", "ValueType"]:
    if col in partner_type_df.columns:
        partner_type_df[col] = partner_type_df[col].map(clean_id)

# --- Affection ---
if "AffectionLevel" in affection_df.columns:
    affection_df["AffectionLevel"] = pd.to_numeric(affection_df["AffectionLevel"], errors="coerce").fillna(0).astype(int)
for col in ["AttackTotal", "DefenseTotal", "HealthTotal"]:
    if col in affection_df.columns:
        affection_df[col] = pd.to_numeric(affection_df[col], errors="coerce").fillna(0.0).astype(float)
if "ApplyStage" in affection_df.columns:
    affection_df["ApplyStage"] = affection_df["ApplyStage"].map(clean_id)

# --- Equipment ---
for col in ["EquipmentId", "SlotType", "StatTypeId"]:
    if col in equipment_df.columns:
        equipment_df[col] = equipment_df[col].map(clean_id)
if "Value" in equipment_df.columns:
    equipment_df["Value"] = pd.to_numeric(equipment_df["Value"], errors="coerce").fillna(0.0).astype(float)

for col in ["StatTypeId", "ValueType", "ApplyStage"]:
    if col in equipment_stat_type_df.columns:
        equipment_stat_type_df[col] = equipment_stat_type_df[col].map(clean_id)

# --- Memory Fragment Base ---
for col in ["FragmentId", "Rarity", "SetTypeId"]:
    if col in mf_base_df.columns:
        mf_base_df[col] = mf_base_df[col].map(clean_id)

# --- Memory Fragment LevelStats ---
for col in ["FragmentId", "StatTypeId", "Formula"]:
    if col in mf_level_df.columns:
        mf_level_df[col] = mf_level_df[col].map(clean_id)
for col in ["MaxLevel", "BaseValue", "PerLevel"]:
    if col in mf_level_df.columns:
        mf_level_df[col] = pd.to_numeric(mf_level_df[col], errors="coerce").fillna(0.0)

# --- Memory Fragment Set ---
for col in ["SetTypeId", "StatTypeId", "ApplyStage"]:
    if col in mf_set_df.columns:
        mf_set_df[col] = mf_set_df[col].map(clean_id)
for col in ["RequiredPieces", "Value", "ConditionType", "ConditionTarg", "ConditionValu"]:
    if col in mf_set_df.columns:
        mf_set_df[col] = pd.to_numeric(mf_set_df[col], errors="coerce").fillna(0.0)

# --- Memory Fragment StatType ---
for col in ["StatTypeId", "ValueType", "ApplyStage"]:
    if col in mf_stat_type_df.columns:
        mf_stat_type_df[col] = mf_stat_type_df[col].map(clean_id)


# =========================================================
# Lookup helpers
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


def get_partner_pct_with_debug(partner_id: Any, stack_count: int, is_bonus_applied: bool) -> Tuple[Tuple[float, float, float], List[str]]:
    debug: List[str] = []
    if not is_bonus_applied:
        return (0.0, 0.0, 0.0), debug

    pid = clean_id(partner_id)
    if pid == "":
        return (0.0, 0.0, 0.0), debug

    idx = clamp_int(stack_count, 0, 4, default=0)
    value_col = f"Stack{idx}Value"

    stack_rows = partner_stack_df[partner_stack_df["PartnerId"] == pid]
    if stack_rows.empty:
        debug.append(f"⚠️ PartnerStatStack not found: PartnerId={pid}")
        return (0.0, 0.0, 0.0), debug

    sr = stack_rows.iloc[0]
    stat_type_id = clean_id(sr.get("StatTypeId", ""))
    pct_value = float(sr.get(value_col, 0.0))

    type_rows = partner_type_df[partner_type_df["StatTypeId"] == stat_type_id]
    if type_rows.empty:
        debug.append(f"⚠️ PartnerStatType not found: StatTypeId={stat_type_id}")
        return (0.0, 0.0, 0.0), debug

    tr = type_rows.iloc[0]
    apply_stage = clean_id(tr.get("ApplyStage", ""))
    value_type = clean_id(tr.get("ValueType", ""))
    is_percent_bool = to_bool(tr.get("IsPercent", False))
    affect_stat = clean_id(tr.get("AffectStat", ""))

    if apply_stage != "StaticBase" or value_type != "Increase" or not is_percent_bool:
        return (0.0, 0.0, 0.0), debug

    atk_pct = def_pct = hp_pct = 0.0
    if affect_stat == "Attack":
        atk_pct = pct_value
    elif affect_stat == "Defense":
        def_pct = pct_value
    elif affect_stat == "Health":
        hp_pct = pct_value
    else:
        debug.append(f"⚠️ Unknown AffectStat='{affect_stat}' for PartnerStatTypeId={stat_type_id}")

    return (atk_pct, def_pct, hp_pct), debug


def get_affection_flat(affection_level: Any) -> Tuple[float, float, float]:
    try:
        lvl = int(float(affection_level)) if clean_id(affection_level) != "" else 1
    except Exception:
        lvl = 1

    rows = affection_df[(affection_df["AffectionLevel"] == lvl) & (affection_df["ApplyStage"] == "StaticBase")]
    if rows.empty:
        return 0.0, 0.0, 0.0

    r = rows.iloc[0]
    return float(r.get("AttackTotal", 0.0)), float(r.get("DefenseTotal", 0.0)), float(r.get("HealthTotal", 0.0))


# =========================================================
# Equipment (Phase 1)
# =========================================================

def lookup_stat_type_meta(stat_type_df: pd.DataFrame, stat_type_id: str) -> Optional[pd.Series]:
    sid = clean_id(stat_type_id)
    if sid == "":
        return None
    rows = stat_type_df[stat_type_df["StatTypeId"] == sid] if "StatTypeId" in stat_type_df.columns else pd.DataFrame()
    if rows.empty:
        return None
    return rows.iloc[0]


def apply_stat_value_to_buckets(
    stat_type_id: str,
    value: float,
    meta: pd.Series,
    flat_bucket: Dict[str, float],
    inc_bucket: Dict[str, float],
    debug_lines: List[str],
    source: str
) -> None:
    """
    flat_bucket keys: Attack/Defense/Health
    inc_bucket keys : Attack/Defense/Health
    """
    apply_stage = clean_id(meta.get("ApplyStage", ""))
    value_type = clean_id(meta.get("ValueType", ""))
    is_percent = to_bool(meta.get("IsPercent", False))

    # Phase1 only
    if apply_stage != "StaticBase":
        debug_lines.append(f"⏭️ [{source}] StatTypeId={stat_type_id} apply_stage={apply_stage} (skip Phase1)")
        return

    # Percent sanity
    if is_percent and abs(value) > 1.0:
        debug_lines.append(f"⚠️ [{source}] IsPercent=True but value={value} > 1.0 (expect 0.05=5%)")

    target = stat_target_from_stat_type_id(stat_type_id)
    if target is None:
        debug_lines.append(f"⚠️ [{source}] Unknown target stat for StatTypeId={stat_type_id} (skip)")
        return

    if value_type.lower() == "flat":
        flat_bucket[target] += float(value)
    elif value_type.lower() == "increase":
        inc_bucket[target] += float(value)
    else:
        debug_lines.append(f"⚠️ [{source}] Unknown ValueType={value_type} for StatTypeId={stat_type_id} (skip)")


def calc_equipment_from_list(equipment_ids: List[str]) -> Tuple[float, float, float, float, float, float, List[str]]:
    """
    Returns:
      equipment_flat_atk/def/hp,
      equipment_pct_atk/def/hp,
      debug_lines
    """
    flat_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    inc_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    debug: List[str] = []

    if not equipment_ids:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, debug

    for eid in equipment_ids:
        if clean_id(eid) == "":
            continue
        rows = equipment_df[equipment_df["EquipmentId"] == eid]
        if rows.empty:
            debug.append(f"⚠️ [Equipment] EquipmentId not found: {eid}")
            continue

        r = rows.iloc[0]
        stat_type_id = clean_id(r.get("StatTypeId", ""))
        val = float(r.get("Value", 0.0))

        meta = lookup_stat_type_meta(equipment_stat_type_df, stat_type_id)
        if meta is None:
            debug.append(f"⚠️ [Equipment] StatTypeId not found in EquipmentStatType: {stat_type_id} (skip)")
            continue

        apply_stat_value_to_buckets(
            stat_type_id=stat_type_id,
            value=val,
            meta=meta,
            flat_bucket=flat_bucket,
            inc_bucket=inc_bucket,
            debug_lines=debug,
            source=f"Equipment:{eid}"
        )

    return (
        flat_bucket["Attack"], flat_bucket["Defense"], flat_bucket["Health"],
        inc_bucket["Attack"], inc_bucket["Defense"], inc_bucket["Health"],
        debug
    )


# =========================================================
# Memory Fragment (Phase 1)
# =========================================================

def calc_mf_main_stat(fragment_id: str, strengthen_level: int, debug: List[str]) -> Tuple[Dict[str, float], Dict[str, float]]:
    """
    returns (flat_bucket, inc_bucket)
    """
    flat_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    inc_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}

    fid = clean_id(fragment_id)
    if fid == "":
        return flat_bucket, inc_bucket

    rows = mf_level_df[mf_level_df["FragmentId"] == fid]
    if rows.empty:
        debug.append(f"⚠️ [MF-Main] FragmentId not found in MemoryFragmentLevelStats: {fid} (skip)")
        return flat_bucket, inc_bucket

    r = rows.iloc[0]
    max_level = int(float(r.get("MaxLevel", 0)))
    lvl = clamp_int(strengthen_level, 0, max_level, default=0)

    stat_type_id = clean_id(r.get("StatTypeId", ""))
    base_val = float(r.get("BaseValue", 0.0))
    per_lvl = float(r.get("PerLevel", 0.0))
    formula = clean_id(r.get("Formula", "Linear"))

    if formula.lower() == "linear":
        val = base_val + per_lvl * lvl
    else:
        # fallback
        val = base_val + per_lvl * lvl
        debug.append(f"⚠️ [MF-Main] Unknown Formula={formula}, fallback to Linear. FragmentId={fid}")

    meta = lookup_stat_type_meta(mf_stat_type_df, stat_type_id)
    if meta is None:
        debug.append(f"⚠️ [MF-Main] StatTypeId not found in MemoryFragmentStatType: {stat_type_id} (skip)")
        return flat_bucket, inc_bucket

    apply_stat_value_to_buckets(
        stat_type_id=stat_type_id,
        value=val,
        meta=meta,
        flat_bucket=flat_bucket,
        inc_bucket=inc_bucket,
        debug_lines=debug,
        source=f"MF-Main:{fid} Lv={lvl}/{max_level}"
    )

    debug.append(f"✅ [MF-Main] {fid} Lv={lvl}/{max_level} Stat={stat_type_id} Value={val}")
    return flat_bucket, inc_bucket


def calc_mf_random_stats(random_stat_ids: List[str], random_values: List[float], debug: List[str]) -> Tuple[Dict[str, float], Dict[str, float]]:
    flat_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    inc_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}

    n = min(len(random_stat_ids), len(random_values))
    for i in range(n):
        sid = clean_id(random_stat_ids[i])
        if sid == "":
            continue
        val = float(random_values[i])

        meta = lookup_stat_type_meta(mf_stat_type_df, sid)
        if meta is None:
            debug.append(f"⚠️ [MF-Random] StatTypeId not found in MemoryFragmentStatType: {sid} (skip)")
            continue

        apply_stat_value_to_buckets(
            stat_type_id=sid,
            value=val,
            meta=meta,
            flat_bucket=flat_bucket,
            inc_bucket=inc_bucket,
            debug_lines=debug,
            source=f"MF-Random:{i}"
        )

    return flat_bucket, inc_bucket


def calc_mf_set_bonus(fragment_ids: List[str], debug: List[str]) -> Tuple[Dict[str, float], Dict[str, float]]:
    flat_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    inc_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}

    if not fragment_ids:
        return flat_bucket, inc_bucket

    # count SetTypeId
    set_counts: Dict[str, int] = {}
    for fid in fragment_ids:
        fid = clean_id(fid)
        if fid == "":
            continue
        rows = mf_base_df[mf_base_df["FragmentId"] == fid]
        if rows.empty:
            continue
        set_type = clean_id(rows.iloc[0].get("SetTypeId", ""))
        if set_type == "":
            continue
        set_counts[set_type] = set_counts.get(set_type, 0) + 1

    if not set_counts:
        return flat_bucket, inc_bucket

    # apply set rules
    for set_type, cnt in set_counts.items():
        rows = mf_set_df[mf_set_df["SetTypeId"] == set_type]
        if rows.empty:
            continue

        for _, r in rows.iterrows():
            required = int(float(r.get("RequiredPieces", 0)))
            if required <= 0 or cnt < required:
                continue

            apply_stage = clean_id(r.get("ApplyStage", ""))
            condition_type = int(float(r.get("ConditionType", 0))) if "ConditionType" in r.index else 0

            # Phase1: only unconditional + StaticBase
            if apply_stage != "StaticBase" or condition_type != 0:
                continue

            stat_type_id = clean_id(r.get("StatTypeId", ""))
            value = float(r.get("Value", 0.0))

            meta = lookup_stat_type_meta(mf_stat_type_df, stat_type_id)
            if meta is None:
                debug.append(f"⚠️ [MF-Set] StatTypeId not found in MemoryFragmentStatType: {stat_type_id} (skip)")
                continue

            apply_stat_value_to_buckets(
                stat_type_id=stat_type_id,
                value=value,
                meta=meta,
                flat_bucket=flat_bucket,
                inc_bucket=inc_bucket,
                debug_lines=debug,
                source=f"MF-Set:{set_type} ({cnt}/{required})"
            )
            debug.append(f"✅ [MF-Set] Set={set_type} pieces={cnt} req={required} Stat={stat_type_id} Value={value}")

    return flat_bucket, inc_bucket


def calc_memory_fragment_contribution(input_row: pd.Series) -> Tuple[float, float, float, float, float, float, List[str]]:
    """
    Returns:
      mf_pct_atk/def/hp,
      mf_flat_atk/def/hp,
      debug_lines
    """
    debug: List[str] = []

    frag_ids = parse_csv_str_list(input_row.get("FragmentIdList[]", ""))
    frag_lvls = parse_csv_num_list(input_row.get("FragmentLevelList[]", ""))
    rand_stat_ids = parse_csv_str_list(input_row.get("FragmentRandomStatList[]", ""))
    rand_vals = parse_csv_num_list(input_row.get("FragmentRandomValueList[]", ""))

    # Ensure levels aligned with fragments
    if len(frag_lvls) < len(frag_ids):
        frag_lvls += [0.0] * (len(frag_ids) - len(frag_lvls))

    flat_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    inc_bucket = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}

    # Main stats
    for i, fid in enumerate(frag_ids):
        lvl = int(float(frag_lvls[i])) if i < len(frag_lvls) else 0
        f_flat, f_inc = calc_mf_main_stat(fid, lvl, debug)
        for k in flat_bucket:
            flat_bucket[k] += f_flat[k]
            inc_bucket[k] += f_inc[k]

    # Random stats (manual injection for Phase1)
    r_flat, r_inc = calc_mf_random_stats(rand_stat_ids, rand_vals, debug)
    for k in flat_bucket:
        flat_bucket[k] += r_flat[k]
        inc_bucket[k] += r_inc[k]

    # Set bonus
    s_flat, s_inc = calc_mf_set_bonus(frag_ids, debug)
    for k in flat_bucket:
        flat_bucket[k] += s_flat[k]
        inc_bucket[k] += s_inc[k]

    return (
        inc_bucket["Attack"], inc_bucket["Defense"], inc_bucket["Health"],
        flat_bucket["Attack"], flat_bucket["Defense"], flat_bucket["Health"],
        debug
    )


# =========================================================
# Core Calculation
# =========================================================

def calc_final_base_stats(input_row: pd.Series) -> Optional[Dict[str, Any]]:
    character_id = clean_id(input_row.get("CharacterId", ""))
    level = norm_level_to_half(input_row.get("Level", 0.0))

    if character_id == "" or level <= 0:
        return None

    partner_id = clean_id(input_row.get("PartnerId", ""))
    partner_level = input_row.get("PartnerLevel", None)
    partner_stack_count = input_row.get("PartnerStackCount", 0)
    is_partner_bonus_applied = to_bool(input_row.get("IsPartnerBonusApplied", False))
    affection_level = input_row.get("AffectionLevel", 1)

    base_rows = base_stat_df[(base_stat_df["CharacterId"] == character_id) & (base_stat_df["Level"] == level)]
    if base_rows.empty:
        print(f"❌ Base stat not found: {character_id} Lv{level}")
        return None

    base_row = base_rows.iloc[0]
    base_atk = float(base_row.get("Attack", 0.0))
    base_def = float(base_row.get("Defense", 0.0))
    base_hp = float(base_row.get("Health", 0.0))

    # Partner
    partner_atk_flat, partner_def_flat, partner_hp_flat = get_partner_flat(partner_id, partner_level)
    (partner_atk_pct, partner_def_pct, partner_hp_pct), partner_pct_debug = get_partner_pct_with_debug(
        partner_id=partner_id,
        stack_count=int(partner_stack_count),
        is_bonus_applied=is_partner_bonus_applied
    )

    # Affection
    affection_flat_atk, affection_flat_def, affection_flat_hp = get_affection_flat(affection_level)

    # Equipment
    equipment_ids = parse_csv_str_list(input_row.get("EquipmentIdList[]", ""))
    eq_flat_atk, eq_flat_def, eq_flat_hp, eq_pct_atk, eq_pct_def, eq_pct_hp, eq_debug = calc_equipment_from_list(equipment_ids)

    # Memory Fragment
    mf_pct_atk, mf_pct_def, mf_pct_hp, mf_flat_atk, mf_flat_def, mf_flat_hp, mf_debug = calc_memory_fragment_contribution(input_row)

    # Compose Phase1 variables
    atk_pct_increase = mf_pct_atk
    def_pct_increase = mf_pct_def
    hp_pct_increase = mf_pct_hp

    gear_flat_atk = mf_flat_atk
    gear_flat_def = mf_flat_def
    gear_flat_hp = mf_flat_hp

    # -----------------------------------------------------
    # Final formulas (Phase 1)
    # -----------------------------------------------------
    atk_base_block = base_atk * (1.0 + atk_pct_increase) + partner_atk_flat + gear_flat_atk + affection_flat_atk
    atk_multiplier = 1.0 + partner_atk_pct + eq_pct_atk
    final_atk = atk_base_block * atk_multiplier + eq_flat_atk

    def_base_block = base_def * (1.0 + def_pct_increase) + partner_def_flat + gear_flat_def + affection_flat_def
    def_multiplier = 1.0 + partner_def_pct + eq_pct_def
    final_def = def_base_block * def_multiplier + eq_flat_def

    hp_base_block = base_hp * (1.0 + hp_pct_increase) + partner_hp_flat + gear_flat_hp + affection_flat_hp
    hp_multiplier = 1.0 + partner_hp_pct + eq_pct_hp
    final_hp = hp_base_block * hp_multiplier + eq_flat_hp

    # ---------------- Logs ----------------
    print("\n------------------------------------------")
    print(f"Character: {character_id}")
    print(f"Level: {level}")
    print(f"[Base] ATK={base_atk}, DEF={base_def}, HP={base_hp}")

    print(f"[Affection] Level={affection_level} -> Flat: ATK={affection_flat_atk}, DEF={affection_flat_def}, HP={affection_flat_hp}")

    if partner_id != "":
        sc = clamp_int(partner_stack_count, 0, 4, default=0)
        pl = norm_level_to_half(partner_level)
        print(f"[Partner] PartnerId={partner_id}, PartnerLevel={pl}, StackCount={sc}, BonusApplied={is_partner_bonus_applied}")
        print(f"         Flat: ATK={partner_atk_flat}, DEF={partner_def_flat}, HP={partner_hp_flat}")
        print(f"         Pct : ATK%={partner_atk_pct}, DEF%={partner_def_pct}, HP%={partner_hp_pct}")
        for line in partner_pct_debug:
            print(line)
    else:
        print("[Partner] None")

    if equipment_ids:
        print(f"[EquipmentIds] {equipment_ids}")
    if eq_debug:
        for line in eq_debug:
            print(line)

    if mf_debug:
        print("[MemoryFragment]")
        for line in mf_debug:
            print(line)

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

    results: List[Dict[str, Any]] = []
    for _, row in combat_input_df.iterrows():
        r = calc_final_base_stats(row)
        if r:
            results.append(r)

    print("\n========== All Calculations Done ==========")
    out_df = pd.DataFrame(results)
    print("\n=== Summary ===")
    if not out_df.empty:
        print(out_df.to_string(index=False))
    else:
        print("(no results)")
