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

def is_empty_cell(x: Any) -> bool:
    if x is None:
        return True
    try:
        if pd.isna(x):
            return True
    except Exception:
        pass
    s = str(x).strip()
    if s == "":
        return True
    if s.lower() in ("none", "nan"):
        return True
    return False


def clean_id(x: Any) -> str:
    if is_empty_cell(x):
        return ""
    s = str(x)
    s = s.replace("\u00A0", "").replace("\u200b", "").strip()
    if s.lower() in ("none", "nan", ""):
        return ""
    return s


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


def to_float(x: Any, default: float = 0.0) -> float:
    if is_empty_cell(x):
        return default
    try:
        return float(x)
    except Exception:
        return default


def infer_affect_stat(stat_type_id: str) -> str:
    """
    依 StatTypeId 推測影響哪個主屬性。
    你目前命名像 AttackFlat / DefenseFlat / HealthPointFlat / AttackIncrease...
    """
    s = stat_type_id.lower()
    if "attack" in s:
        return "Attack"
    if "defense" in s or "def" in s:
        return "Defense"
    if "health" in s or "hp" in s:
        return "Health"
    return ""


# =========================================================
# CombatInputPanel grouping (一個角色多行)
# =========================================================

def group_combat_input_blocks(df: pd.DataFrame) -> List[List[pd.Series]]:
    """
    將 CombatInputPanel 依 CharacterId 分段：
    - 有 CharacterId 的行 = 新角色開始
    - CharacterId 空白/None 的行 = 附加到上一個角色
    """
    blocks: List[List[pd.Series]] = []
    current: List[pd.Series] = []

    for _, row in df.iterrows():
        cid = clean_id(row.get("CharacterId", ""))
        if cid != "":
            if current:
                blocks.append(current)
            current = [row]
        else:
            # 附加到上一個角色
            if current:
                current.append(row)
            else:
                # 檔案最前面如果就是空行，忽略
                continue

    if current:
        blocks.append(current)
    return blocks


# =========================================================
# Load tables
# =========================================================

character_index_df = load_sheet("Character.xlsx", "CharacterIndex")
base_stat_df = load_sheet("Character.xlsx", "CharacterBaseStatByLevel")
combat_input_df = load_sheet("CombatInputPanel.xlsx", "CombatInputPanel")

equipment_df = load_sheet("Equipment.xlsx", "Equipment")
equipment_stat_type_df = load_sheet("Equipment.xlsx", "EquipmentStatType")

partner_level_df = load_sheet("Partner.xlsx", "PartnerLevelStat")
partner_stack_df = load_sheet("Partner.xlsx", "PartnerStatStack")
partner_type_df = load_sheet("Partner.xlsx", "PartnerStatType")

affection_df = load_sheet("Affection.xlsx", "AffectionByLevel")

mf_level_stats_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentLevelStats")
mf_stat_type_df = load_sheet("MemoryFragment.xlsx", "MemoryFragmentStatType")


# =========================================================
# Normalize dtypes
# =========================================================

# Base stats
if "Level" in base_stat_df.columns:
    base_stat_df["Level"] = pd.to_numeric(base_stat_df["Level"], errors="coerce").fillna(0.0).astype(float)
    base_stat_df["Level"] = base_stat_df["Level"].map(norm_level_to_half)
if "CharacterId" in base_stat_df.columns:
    base_stat_df["CharacterId"] = base_stat_df["CharacterId"].map(clean_id)

# Partner level stat
if "PartnerId" in partner_level_df.columns:
    partner_level_df["PartnerId"] = partner_level_df["PartnerId"].map(clean_id)
if "Level" in partner_level_df.columns:
    partner_level_df["Level"] = pd.to_numeric(partner_level_df["Level"], errors="coerce").fillna(0.0).astype(float)
    partner_level_df["Level"] = partner_level_df["Level"].map(norm_level_to_half)

# Partner stack
if "PartnerId" in partner_stack_df.columns:
    partner_stack_df["PartnerId"] = partner_stack_df["PartnerId"].map(clean_id)
if "StatTypeId" in partner_stack_df.columns:
    partner_stack_df["StatTypeId"] = partner_stack_df["StatTypeId"].map(clean_id)
for col in ["Stack0Value", "Stack1Value", "Stack2Value", "Stack3Value", "Stack4Value"]:
    if col in partner_stack_df.columns:
        partner_stack_df[col] = pd.to_numeric(partner_stack_df[col], errors="coerce").fillna(0.0).astype(float)

# Partner type
for c in ["StatTypeId", "AffectStat", "ApplyStage", "ValueType"]:
    if c in partner_type_df.columns:
        partner_type_df[c] = partner_type_df[c].map(clean_id)

# Affection
if "AffectionLevel" in affection_df.columns:
    affection_df["AffectionLevel"] = pd.to_numeric(affection_df["AffectionLevel"], errors="coerce").fillna(1).astype(int)
for col in ["AttackTotal", "DefenseTotal", "HealthTotal"]:
    if col in affection_df.columns:
        affection_df[col] = pd.to_numeric(affection_df[col], errors="coerce").fillna(0.0).astype(float)
if "ApplyStage" in affection_df.columns:
    affection_df["ApplyStage"] = affection_df["ApplyStage"].map(clean_id)

# Equipment
if "EquipmentId" in equipment_df.columns:
    equipment_df["EquipmentId"] = equipment_df["EquipmentId"].map(clean_id)
if "StatTypeId" in equipment_df.columns:
    equipment_df["StatTypeId"] = equipment_df["StatTypeId"].map(clean_id)
if "Value" in equipment_df.columns:
    equipment_df["Value"] = pd.to_numeric(equipment_df["Value"], errors="coerce").fillna(0.0).astype(float)

for c in ["StatTypeId", "ValueType", "ApplyStage"]:
    if c in equipment_stat_type_df.columns:
        equipment_stat_type_df[c] = equipment_stat_type_df[c].map(clean_id)

# MemoryFragmentLevelStats
for c in ["FragmentId", "StatTypeId", "Formula"]:
    if c in mf_level_stats_df.columns:
        mf_level_stats_df[c] = mf_level_stats_df[c].map(clean_id)

for c in ["MaxLevel", "BaseValue", "PerLevel"]:
    if c in mf_level_stats_df.columns:
        mf_level_stats_df[c] = pd.to_numeric(mf_level_stats_df[c], errors="coerce").fillna(0.0).astype(float)

# MemoryFragmentStatType
for c in ["StatTypeId", "ValueType", "ApplyStage"]:
    if c in mf_stat_type_df.columns:
        mf_stat_type_df[c] = mf_stat_type_df[c].map(clean_id)


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

    idx = clamp_int(stack_count, 0, 4, default=0)
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
    is_percent_bool = to_bool(tr.get("IsPercent", False))
    affect_stat = clean_id(tr.get("AffectStat", ""))

    if apply_stage != "StaticBase":
        return 0.0, 0.0, 0.0
    if value_type != "Increase":
        return 0.0, 0.0, 0.0
    if not is_percent_bool:
        return 0.0, 0.0, 0.0

    atk_pct = def_pct = hp_pct = 0.0
    if affect_stat == "Attack":
        atk_pct = pct_value
    elif affect_stat == "Defense":
        def_pct = pct_value
    elif affect_stat == "Health":
        hp_pct = pct_value
    return atk_pct, def_pct, hp_pct


# =========================================================
# Affection helper
# =========================================================

def get_affection_flat(affection_level: Any) -> Tuple[float, float, float]:
    lvl = 1
    if not is_empty_cell(affection_level):
        try:
            lvl = int(float(affection_level))
        except Exception:
            lvl = 1

    rows = affection_df[(affection_df["AffectionLevel"] == lvl) & (affection_df["ApplyStage"] == "StaticBase")]
    if rows.empty:
        return 0.0, 0.0, 0.0

    r = rows.iloc[0]
    return float(r.get("AttackTotal", 0.0)), float(r.get("DefenseTotal", 0.0)), float(r.get("HealthTotal", 0.0))


# =========================================================
# StatType lookup
# =========================================================

def get_stat_type_rule(stat_type_df: pd.DataFrame, stat_type_id: str) -> Dict[str, Any]:
    rows = stat_type_df[stat_type_df["StatTypeId"] == stat_type_id]
    if rows.empty:
        return {
            "found": False,
            "ValueType": "",
            "IsPercent": False,
            "ApplyStage": "",
        }
    r = rows.iloc[0]
    return {
        "found": True,
        "ValueType": clean_id(r.get("ValueType", "")),
        "IsPercent": to_bool(r.get("IsPercent", False)),
        "ApplyStage": clean_id(r.get("ApplyStage", "")),
    }


def apply_stat_contribution(
    stat_type_id: str,
    value: float,
    stat_type_rule: Dict[str, Any],
    pct_acc: Dict[str, float],
    flat_acc: Dict[str, float],
    debug_lines: List[str],
    source: str
) -> None:
    """
    Phase 1 只吃 ApplyStage=StaticBase
    ValueType:
      - Flat -> gear flat
      - Increase + IsPercent=True -> pct increase
    """
    if not stat_type_rule.get("found", False):
        debug_lines.append(f"⚠️ [{source}] StatTypeId not found: {stat_type_id} (skip)")
        return

    apply_stage = stat_type_rule.get("ApplyStage", "")
    value_type = stat_type_rule.get("ValueType", "")
    is_percent = stat_type_rule.get("IsPercent", False)

    if apply_stage != "StaticBase":
        debug_lines.append(f"🚫 [{source}] ApplyStage={apply_stage} != StaticBase: {stat_type_id} (skip)")
        return

    affect = infer_affect_stat(stat_type_id)
    if affect == "":
        debug_lines.append(f"⚠️ [{source}] Cannot infer AffectStat from StatTypeId: {stat_type_id} (skip)")
        return

    # 防呆：IsPercent=True 但值 > 1
    if is_percent and abs(value) > 1:
        debug_lines.append(f"⚠️ [{source}] IsPercent=True but value={value} > 1 (expect 0.05=5%) StatTypeId={stat_type_id}")

    if value_type == "Flat":
        flat_acc[affect] += value
        debug_lines.append(f"✅ [{source}] {stat_type_id} Flat +{value} -> {affect}Flat")
    elif value_type == "Increase" and is_percent:
        pct_acc[affect] += value
        debug_lines.append(f"✅ [{source}] {stat_type_id} Increase +{value} -> {affect}%")
    else:
        debug_lines.append(f"🚫 [{source}] Unsupported rule ValueType={value_type}, IsPercent={is_percent}: {stat_type_id} (skip)")


# =========================================================
# Equipment contribution
# =========================================================

def calc_equipment_contribution(equipment_ids: List[str]) -> Tuple[Dict[str, float], Dict[str, float], List[str]]:
    pct = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    flat = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    debug: List[str] = []

    for eid in equipment_ids:
        rows = equipment_df[equipment_df["EquipmentId"] == eid]
        if rows.empty:
            debug.append(f"⚠️ [EQ] EquipmentId not found: {eid} (skip)")
            continue

        r = rows.iloc[0]
        stat_type_id = clean_id(r.get("StatTypeId", ""))
        value = float(r.get("Value", 0.0))

        rule = get_stat_type_rule(equipment_stat_type_df, stat_type_id)
        apply_stat_contribution(stat_type_id, value, rule, pct, flat, debug, source=f"EQ:{eid}")

    return pct, flat, debug


# =========================================================
# MemoryFragment contribution (主詞條 + 隨機詞條)
# =========================================================

def calc_fragment_main_stat(fragment_id: str, level: int) -> Tuple[Optional[str], float, List[str]]:
    """
    回傳 (StatTypeId, value, debug)
    Linear: BaseValue + PerLevel * level
    level 允許 0
    """
    debug: List[str] = []

    rows = mf_level_stats_df[mf_level_stats_df["FragmentId"] == fragment_id]
    if rows.empty:
        debug.append(f"⚠️ [MF-Main] FragmentId not found in MemoryFragmentLevelStats: {fragment_id}")
        return None, 0.0, debug

    r = rows.iloc[0]
    max_lv = int(float(r.get("MaxLevel", 0)))
    stat_type_id = clean_id(r.get("StatTypeId", ""))
    base_value = float(r.get("BaseValue", 0.0))
    per_level = float(r.get("PerLevel", 0.0))
    formula = clean_id(r.get("Formula", "Linear"))

    lv = clamp_int(level, 0, max_lv, default=0)

    if formula.lower() == "linear":
        value = base_value + per_level * lv
    else:
        # 你未來若有其他公式再擴充
        value = base_value + per_level * lv
        debug.append(f"⚠️ [MF-Main] Unknown Formula={formula}, fallback Linear: {fragment_id}")

    debug.append(f"🧾 [MF-Main] {fragment_id} Lv={lv}/{max_lv} Stat={stat_type_id} = {base_value} + {per_level}*{lv} => {value}")
    return stat_type_id, value, debug


def calc_memory_fragment_contribution(fragments: List[Dict[str, Any]]) -> Tuple[Dict[str, float], Dict[str, float], List[str]]:
    """
    fragments: [
      {
        "FragmentId": "...",
        "Level": int (允許0),
        "RandomStats": [StatTypeId...],
        "RandomValues": [float...]
      }
    ]
    """
    pct = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    flat = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    debug: List[str] = []

    for frag in fragments:
        fid = frag["FragmentId"]
        lv = int(frag.get("Level", 0))

        # ---- Main stat (from MemoryFragmentLevelStats)
        main_stat_type_id, main_value, main_dbg = calc_fragment_main_stat(fid, lv)
        debug.extend(main_dbg)
        if main_stat_type_id:
            rule = get_stat_type_rule(mf_stat_type_df, main_stat_type_id)
            apply_stat_contribution(main_stat_type_id, main_value, rule, pct, flat, debug, source=f"MF-Main:{fid}")

        # ---- Random stats (manual input)
        rs: List[str] = frag.get("RandomStats", [])
        rv: List[float] = frag.get("RandomValues", [])

        # 對齊長度（避免填錯）
        n = min(len(rs), len(rv))
        if n > 0:
            debug.append(f"🧩 [MF-Rand] {fid} RandomCount={n}")
        for i in range(n):
            st = clean_id(rs[i])
            val = float(rv[i])
            if st == "":
                continue
            rule = get_stat_type_rule(mf_stat_type_df, st)
            apply_stat_contribution(st, val, rule, pct, flat, debug, source=f"MF-Rand:{fid}")

    return pct, flat, debug


# =========================================================
# Parse CombatInputPanel block -> structured data
# =========================================================

def build_character_payload(block_rows: List[pd.Series]) -> Dict[str, Any]:
    """
    block_rows[0] = 角色主資料行
    block_rows[1..] = 同角色的碎片/隨機詞條/裝備延伸行
    """
    head = block_rows[0]

    payload: Dict[str, Any] = {
        "CharacterId": clean_id(head.get("CharacterId", "")),
        "Level": norm_level_to_half(head.get("Level", 0.0)),
        "PartnerId": clean_id(head.get("PartnerId", "")),
        "PartnerLevel": norm_level_to_half(head.get("PartnerLevel", 0.0)),
        "PartnerStackCount": clamp_int(head.get("PartnerStackCount", 0), 0, 4, default=0),
        "IsPartnerBonusApplied": to_bool(head.get("IsPartnerBonusApplied", False)),
        "AffectionLevel": int(to_float(head.get("AffectionLevel", 1), 1)),
        "EquipmentIds": [],
        "Fragments": [],
    }

    # equipment ids：整個 block 收集
    equipment_ids: List[str] = []

    # fragments：在 block 內，依 FragmentIdList[] 出現時開新 fragment
    current_fragment: Optional[Dict[str, Any]] = None

    for row in block_rows:
        # --- equipment
        eid = clean_id(row.get("EquipmentIdList[]", ""))
        if eid != "":
            equipment_ids.append(eid)

        # --- fragment id
        fid = clean_id(row.get("FragmentIdList[]", ""))
        if fid != "":
            # 開新 fragment
            lvl_cell = row.get("FragmentLevelList[]", None)
            # ✅ 0 是合法值：只有空白才預設 0
            if is_empty_cell(lvl_cell):
                frag_lv = 0
            else:
                frag_lv = clamp_int(lvl_cell, 0, 999, default=0)

            current_fragment = {
                "FragmentId": fid,
                "Level": frag_lv,
                "RandomStats": [],
                "RandomValues": [],
            }
            payload["Fragments"].append(current_fragment)

        # --- random stat/value：必須附加到 current_fragment
        st = clean_id(row.get("FragmentRandomStatList[]", ""))
        val_cell = row.get("FragmentRandomValueList[]", None)

        if st != "" and current_fragment is not None:
            # value 允許 0（0也代表合法）
            val = 0.0 if is_empty_cell(val_cell) else to_float(val_cell, 0.0)
            current_fragment["RandomStats"].append(st)
            current_fragment["RandomValues"].append(val)

    # 去重 equipment（保留順序）
    seen = set()
    uniq_eq: List[str] = []
    for e in equipment_ids:
        if e not in seen:
            uniq_eq.append(e)
            seen.add(e)

    payload["EquipmentIds"] = uniq_eq
    return payload


# =========================================================
# Core Calculation
# =========================================================

def calc_final_base_stats_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    character_id = payload["CharacterId"]
    level = payload["Level"]

    base_rows = base_stat_df[(base_stat_df["CharacterId"] == character_id) & (base_stat_df["Level"] == level)]
    if base_rows.empty:
        print(f"❌ Base stat not found: {character_id} Lv{level}")
        return None

    base_row = base_rows.iloc[0]
    base_atk = float(base_row.get("Attack", 0.0))
    base_def = float(base_row.get("Defense", 0.0))
    base_hp = float(base_row.get("Health", 0.0))

    # accumulators
    pct_increase = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}
    gear_flat = {"Attack": 0.0, "Defense": 0.0, "Health": 0.0}

    # partner
    partner_atk_flat, partner_def_flat, partner_hp_flat = get_partner_flat(payload["PartnerId"], payload["PartnerLevel"])
    partner_atk_pct, partner_def_pct, partner_hp_pct = get_partner_pct(
        payload["PartnerId"],
        payload["PartnerStackCount"],
        payload["IsPartnerBonusApplied"]
    )

    # affection
    aff_atk, aff_def, aff_hp = get_affection_flat(payload["AffectionLevel"])

    # equipment
    eq_pct, eq_flat, eq_debug = calc_equipment_contribution(payload["EquipmentIds"])
    # Phase1 公式：equipment flat 在最後 +，equipment % 在 multiplier
    # 你目前只做 phase1 靜態，所以照這套

    # memory fragment
    mf_pct, mf_flat, mf_debug = calc_memory_fragment_contribution(payload["Fragments"])

    # merge mf into accumulators
    for k in pct_increase.keys():
        pct_increase[k] += mf_pct[k]
        gear_flat[k] += mf_flat[k]

    # -----------------------------------------------------
    # Final formulas (Phase 1)
    # -----------------------------------------------------
    atk_base_block = base_atk * (1.0 + pct_increase["Attack"]) + partner_atk_flat + gear_flat["Attack"] + aff_atk
    atk_multiplier = 1.0 + partner_atk_pct + eq_pct["Attack"]
    final_atk = atk_base_block * atk_multiplier + eq_flat["Attack"]

    def_base_block = base_def * (1.0 + pct_increase["Defense"]) + partner_def_flat + gear_flat["Defense"] + aff_def
    def_multiplier = 1.0 + partner_def_pct + eq_pct["Defense"]
    final_def = def_base_block * def_multiplier + eq_flat["Defense"]

    hp_base_block = base_hp * (1.0 + pct_increase["Health"]) + partner_hp_flat + gear_flat["Health"] + aff_hp
    hp_multiplier = 1.0 + partner_hp_pct + eq_pct["Health"]
    final_hp = hp_base_block * hp_multiplier + eq_flat["Health"]

    # ---------------- Logs ----------------
    print("\n------------------------------------------")
    print(f"Character: {character_id}")
    print(f"Level: {level}")
    print(f"[Base] ATK={base_atk}, DEF={base_def}, HP={base_hp}")

    print(f"[Affection] Level={payload['AffectionLevel']} -> Flat: ATK={aff_atk}, DEF={aff_def}, HP={aff_hp}")

    if payload["PartnerId"] != "":
        print(f"[Partner] PartnerId={payload['PartnerId']}, PartnerLevel={payload['PartnerLevel']}, "
              f"StackCount={payload['PartnerStackCount']}, BonusApplied={payload['IsPartnerBonusApplied']}")
        print(f"         Flat: ATK={partner_atk_flat}, DEF={partner_def_flat}, HP={partner_hp_flat}")
        print(f"         Pct : ATK%={partner_atk_pct}, DEF%={partner_def_pct}, HP%={partner_hp_pct}")
    else:
        print("[Partner] None")

    print(f"[EquipmentIds] {payload['EquipmentIds'] if payload['EquipmentIds'] else 'None'}")
    for line in eq_debug:
        print(line)

    print("[MemoryFragment]")
    # 讓你看得出每顆碎片到底有沒有主詞條+隨機詞條加進去
    for f in payload["Fragments"]:
        print(f"  - {f['FragmentId']} Lv={f['Level']} RandomCount={min(len(f['RandomStats']), len(f['RandomValues']))}")
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

    blocks = group_combat_input_blocks(combat_input_df)

    results: List[Dict[str, Any]] = []
    for block in blocks:
        payload = build_character_payload(block)
        # 角色 id 空就跳過
        if payload["CharacterId"] == "":
            continue
        result = calc_final_base_stats_from_payload(payload)
        if result:
            results.append(result)

    print("\n========== All Calculations Done ==========")

    out_df = pd.DataFrame(results)
    print("\n=== Summary ===")
    if not out_df.empty:
        print(out_df.to_string(index=False))
    else:
        print("(no results)")
