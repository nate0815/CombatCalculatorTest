"""
combat_static_calculator.py

Phase: Static / Pre-combat
Responsibility:
- Calculate final base ATK / DEF / HP before battle
- Includes Character / Partner / Affection / Equipment / MemoryFragment
- No card, no turn, no enemy logic
"""

import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional

from models import CharacterSnapshot

# =========================================================
# Path & Loader
# =========================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


def load_sheet(excel_name: str, sheet_name: str) -> pd.DataFrame:
    path = DATA_DIR / excel_name
    if not path.exists():
        raise FileNotFoundError(f"❌ Excel file not found: {path}")

    df = pd.read_excel(path, sheet_name=sheet_name)
    df.columns = df.columns.astype(str).str.strip()
    return df


# =========================================================
# Utils
# =========================================================

def debug_print(verbose: bool, *args, **kwargs):
    if verbose:
        print(*args, **kwargs)


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


def to_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def norm_level_to_half(x: Any) -> float:
    try:
        return round(float(x) * 2) / 2
    except Exception:
        return 0.0


def warn_percent_sanity(source: str, stat_type_id: str, value: float, verbose: bool):
    if value > 1.0:
        debug_print(
            verbose,
            f"⚠️ [{source}] Percent value > 1.0: {stat_type_id} = {value} (expect 0.12 = 12%)"
        )


# =========================================================
# Load tables
# =========================================================

character_index_df = load_sheet("Character.xlsx", "CharacterIndex")
base_stat_df = load_sheet("Character.xlsx", "CharacterBaseStatByLevel")
combat_input_df = load_sheet("CombatInputPanel.xlsx", "CombatInputPanel")

partner_level_df = load_sheet("Partner.xlsx", "PartnerLevelStat")
affection_df = load_sheet("Affection.xlsx", "AffectionByLevel")


# =========================================================
# Input Panel Parsing
# =========================================================

def iter_character_blocks(df: pd.DataFrame) -> List[Dict[str, Any]]:
    blocks = []
    current = None

    for _, row in df.iterrows():
        cid = clean_id(row.get("CharacterId", ""))
        if cid:
            if current:
                blocks.append(current)
            current = {"base": row, "rows": [row]}
        else:
            if current:
                current["rows"].append(row)

    if current:
        blocks.append(current)
    return blocks


# =========================================================
# Partner / Affection
# =========================================================

def get_partner_flat(partner_id: str, level: float) -> Tuple[float, float, float]:
    rows = partner_level_df[
        (partner_level_df["PartnerId"] == partner_id) &
        (partner_level_df["Level"] == level)
    ]
    if rows.empty:
        return 0.0, 0.0, 0.0

    r = rows.iloc[0]
    return float(r["Attack"]), float(r["Defense"]), float(r["Health"])


def get_affection_flat(level: int) -> Tuple[float, float, float]:
    rows = affection_df[
        (affection_df["AffectionLevel"] == level) &
        (affection_df["ApplyStage"] == "StaticBase")
    ]
    if rows.empty:
        return 0.0, 0.0, 0.0

    r = rows.iloc[0]
    return float(r["AttackTotal"]), float(r["DefenseTotal"]), float(r["HealthTotal"])


# =========================================================
# Core Calculation
# =========================================================

def calc_final_base_stats_for_block(
    block: Dict[str, Any],
    verbose: bool
) -> Optional[CharacterSnapshot]:

    base = block["base"]

    character_id = clean_id(base.get("CharacterId"))
    level = norm_level_to_half(base.get("Level"))
    affection_level = to_int(base.get("AffectionLevel", 1), 1)

    base_rows = base_stat_df[
        (base_stat_df["CharacterId"] == character_id) &
        (base_stat_df["Level"] == level)
    ]
    if base_rows.empty:
        debug_print(verbose, f"❌ Base stat not found: {character_id} Lv{level}")
        return None

    br = base_rows.iloc[0]
    base_atk = float(br["Attack"])
    base_def = float(br["Defense"])
    base_hp = float(br["Health"])

    # Partner
    partner_id = clean_id(base.get("PartnerId"))
    partner_level = norm_level_to_half(base.get("PartnerLevel", 0))
    p_atk, p_def, p_hp = get_partner_flat(partner_id, partner_level)

    # Affection
    a_atk, a_def, a_hp = get_affection_flat(affection_level)

    final_atk = base_atk + p_atk + a_atk
    final_def = base_def + p_def + a_def
    final_hp = base_hp + p_hp + a_hp

    debug_print(verbose, "----------------------------------")
    debug_print(verbose, f"Character: {character_id}")
    debug_print(verbose, f"Level: {level}")
    debug_print(verbose, f"Base ATK={base_atk}, DEF={base_def}, HP={base_hp}")
    debug_print(verbose, f"Partner Flat ATK={p_atk}, DEF={p_def}, HP={p_hp}")
    debug_print(verbose, f"Affection Flat ATK={a_atk}, DEF={a_def}, HP={a_hp}")
    debug_print(verbose, f"Final ATK={final_atk}, DEF={final_def}, HP={final_hp}")

    return CharacterSnapshot(
        character_id=character_id,
        final_atk=final_atk,
        final_def=final_def,
        final_hp=final_hp,
        level=level,
        affection_level=affection_level
    )


# =========================================================
# Public API
# =========================================================

def calc_all_character_snapshots(verbose: bool = False) -> List[CharacterSnapshot]:
    blocks = iter_character_blocks(combat_input_df)
    results: List[CharacterSnapshot] = []

    for b in blocks:
        snap = calc_final_base_stats_for_block(b, verbose=verbose)
        if snap:
            results.append(snap)

    return results


# =========================================================
# Standalone Execution (Debug Mode)
# =========================================================

if __name__ == "__main__":
    print("=== Phase 1: Static Base Calculation ===")

    snaps = calc_all_character_snapshots(verbose=True)

    print("\n=== Summary ===")
    if snaps:
        df = pd.DataFrame([{
            "CharacterId": s.character_id,
            "Level": s.level,
            "FinalATK": s.final_atk,
            "FinalDEF": s.final_def,
            "FinalHP": s.final_hp,
        } for s in snaps])
        print(df.to_string(index=False))
    else:
        print("(no results)")

    print("\n計算完成！")
    input("按 Enter 鍵結束程式...")
