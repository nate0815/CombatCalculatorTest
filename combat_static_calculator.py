# combat_static_calculator.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from models import CharacterSnapshot


# =========================================================
# Paths
# =========================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


# =========================================================
# Excel Loader
# =========================================================
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


def _pick_first_existing_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = set(df.columns.astype(str))
    for c in candidates:
        if c in cols:
            return c
    return None


# =========================================================
# Phase 1 (MVP static snapshot)
# =========================================================
def calc_all_character_snapshots(verbose: bool = False) -> List[CharacterSnapshot]:
    """
    MVP Phase1 calculator to keep battle simulator runnable.

    Reads:
    - Character.xlsx / CharacterIndex
    - Character.xlsx / CharacterBaseStatByLevel  (or your renamed sheet)

    Output:
    - List[CharacterSnapshot] with final_atk/final_def/final_hp

    Notes
    - This is intentionally "minimal" and robust to column naming differences.
    - If your project already has a richer Phase1 pipeline (equipment/fragment/partner),
      you can later replace this file with your full version, as long as you keep
      calc_all_character_snapshots(verbose=False) -> List[CharacterSnapshot].
    """

    # ---- Load CharacterIndex ----
    # Common sheet name you used earlier: "CharacterIndex"
    index_df = load_sheet("Character.xlsx", "CharacterIndex")

    # Try common column names
    col_id = _pick_first_existing_col(index_df, ["CharacterId", "character_id", "Id", "ID"])
    if col_id is None:
        raise ValueError("❌ CharacterIndex missing CharacterId column (tried: CharacterId/Id/ID)")

    col_level = _pick_first_existing_col(index_df, ["Level", "level"])
    # If no level column, default to 1

    # ---- Load BaseStatByLevel ----
    # You renamed to CharacterBaseStatByLevel in memory; accept both
    try:
        level_df = load_sheet("Character.xlsx", "CharacterBaseStatByLevel")
    except Exception:
        # fallback name
        level_df = load_sheet("Character.xlsx", "CharacterLevelStat")

    lvl_col_char = _pick_first_existing_col(level_df, ["CharacterId", "character_id", "Id", "ID"])
    lvl_col_level = _pick_first_existing_col(level_df, ["Level", "level"])

    col_atk = _pick_first_existing_col(level_df, ["Attack", "ATK", "Atk", "BaseATK", "final_atk"])
    col_def = _pick_first_existing_col(level_df, ["Defense", "DEF", "Def", "BaseDEF", "final_def"])
    col_hp = _pick_first_existing_col(level_df, ["Health", "HP", "Hp", "BaseHP", "final_hp"])

    if lvl_col_char is None or lvl_col_level is None:
        raise ValueError("❌ CharacterBaseStatByLevel missing CharacterId/Level columns")

    if col_atk is None or col_def is None or col_hp is None:
        raise ValueError("❌ CharacterBaseStatByLevel missing base stat columns (Attack/Defense/Health)")

    # Normalize
    level_df2 = level_df.copy()
    level_df2[lvl_col_char] = level_df2[lvl_col_char].astype(str).str.strip()

    snapshots: List[CharacterSnapshot] = []

    for _, row in index_df.iterrows():
        cid = str(row[col_id]).strip()
        lvl = 1
        if col_level is not None and not pd.isna(row[col_level]):
            try:
                lvl = int(float(row[col_level]))
            except Exception:
                lvl = 1

        # find matching base stat row
        match = level_df2[
            (level_df2[lvl_col_char] == cid) & (level_df2[lvl_col_level].astype(float) == float(lvl))
        ]

        if match.empty:
            # fallback: use the first row for that character (lowest level)
            match = level_df2[level_df2[lvl_col_char] == cid].sort_values(by=lvl_col_level).head(1)

        if match.empty:
            raise ValueError(f"❌ No base stat row found for CharacterId={cid}")

        r = match.iloc[0]
        atk = float(r[col_atk]) if not pd.isna(r[col_atk]) else 0.0
        de = float(r[col_def]) if not pd.isna(r[col_def]) else 0.0
        hp = float(r[col_hp]) if not pd.isna(r[col_hp]) else 0.0

        snap = CharacterSnapshot(
            character_id=cid,
            final_atk=atk,
            final_def=de,
            final_hp=hp,
            level=float(lvl),
        )
        snapshots.append(snap)

        if verbose:
            print(f"[Phase1] {cid} L{lvl} ATK={atk} DEF={de} HP={hp}")

    return snapshots
