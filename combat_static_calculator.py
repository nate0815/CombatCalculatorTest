# combat_static_calculator.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from models import CharacterSnapshot
from runtime_input_repository import RuntimeInputRepository


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


# =========================================================
# Excel Loader
# =========================================================

def load_sheet(excel_name: str, sheet_name: str) -> pd.DataFrame:
    path = DATA_DIR / excel_name
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")

    df = pd.read_excel(path, sheet_name=sheet_name)
    df.columns = df.columns.astype(str).str.strip()
    return df


def try_load_sheet(excel_name: str, sheet_name: str) -> Optional[pd.DataFrame]:
    try:
        return load_sheet(excel_name, sheet_name)
    except Exception:
        return None


def _norm(v: Any) -> Optional[Any]:
    if v is None:
        return None
    try:
        if isinstance(v, float) and pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() == "none":
            return None
        return s
    return v


def _to_float(v: Any, default: float = 0.0) -> float:
    v = _norm(v)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    v = _norm(v)
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default


# =========================================================
# Base Stat By Level helper
# =========================================================

@dataclass
class BaseStatRow:
    level: float
    atk: float
    defense: float
    hp: float


class CharacterBaseStatByLevelTable:
    """
    Expect columns:
        CharacterId, Level, Attack, Defense, Health
    or tolerant variants.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df.columns = self.df.columns.astype(str).str.strip()

        self.col_character_id = self._pick(("CharacterId", "CharacterID", "character_id"))
        self.col_level = self._pick(("Level", "level"))
        self.col_atk = self._pick(("Attack", "Atk", "ATK", "final_atk", "BaseATK", "BaseAtk"))
        self.col_def = self._pick(("Defense", "Def", "DEF", "final_def", "BaseDEF", "BaseDef"))
        self.col_hp = self._pick(("Health", "HP", "Hp", "final_hp", "BaseHP", "BaseHp"))

        # index: char_id -> sorted rows by level
        self._rows_by_char: Dict[str, List[BaseStatRow]] = {}
        for _, r in self.df.iterrows():
            cid = _norm(r.get(self.col_character_id))
            lv = _norm(r.get(self.col_level))
            if cid is None or lv is None:
                continue

            cid_s = str(cid).strip()
            row = BaseStatRow(
                level=_to_float(lv, 1.0),
                atk=_to_float(r.get(self.col_atk), 0.0),
                defense=_to_float(r.get(self.col_def), 0.0),
                hp=_to_float(r.get(self.col_hp), 0.0),
            )
            self._rows_by_char.setdefault(cid_s, []).append(row)

        for cid in self._rows_by_char:
            self._rows_by_char[cid].sort(key=lambda x: x.level)

    def _pick(self, candidates: Tuple[str, ...]) -> str:
        for c in candidates:
            if c in self.df.columns:
                return c
        raise ValueError(f"CharacterBaseStatByLevel missing required columns: {candidates}. Existing={list(self.df.columns)}")

    def get(self, character_id: str, level: float) -> BaseStatRow:
        rows = self._rows_by_char.get(character_id)
        if not rows:
            raise KeyError(f"CharacterBaseStatByLevel has no rows for CharacterId={character_id}")

        # 1) exact match
        for r in rows:
            if abs(r.level - level) < 1e-6:
                return r

        # 2) interpolate between nearest levels
        # find rightmost <= level and leftmost >= level
        lower = None
        upper = None
        for r in rows:
            if r.level <= level:
                lower = r
            if r.level >= level:
                upper = r
                break

        if lower is None:
            return rows[0]
        if upper is None:
            return rows[-1]
        if abs(upper.level - lower.level) < 1e-6:
            return lower

        t = (level - lower.level) / (upper.level - lower.level)
        return BaseStatRow(
            level=level,
            atk=lower.atk + (upper.atk - lower.atk) * t,
            defense=lower.defense + (upper.defense - lower.defense) * t,
            hp=lower.hp + (upper.hp - lower.hp) * t,
        )


# =========================================================
# Optional: Affection flat bonus
# =========================================================

class AffectionByLevelTable:
    """
    Expect columns:
        AffectionLevel, Attack, Defense, Health
    """
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df.columns = self.df.columns.astype(str).str.strip()
        self.col_lv = self._pick(("AffectionLevel", "AffectionLv", "Level"))
        self.col_atk = self._pick(("AttackTotal", "Attack", "Atk", "ATK"))
        self.col_def = self._pick(("DefenseTotal", "Defense", "Def", "DEF"))
        self.col_hp = self._pick(("HealthTotal", "Health", "HP", "Hp"))


        self._map: Dict[int, Tuple[float, float, float]] = {}
        for _, r in self.df.iterrows():
            lv = _to_int(r.get(self.col_lv), 0)
            self._map[lv] = (
                _to_float(r.get(self.col_atk), 0.0),
                _to_float(r.get(self.col_def), 0.0),
                _to_float(r.get(self.col_hp), 0.0),
            )

    def _pick(self, candidates: Tuple[str, ...]) -> str:
        for c in candidates:
            if c in self.df.columns:
                return c
        raise ValueError(f"AffectionByLevel missing required columns: {candidates}. Existing={list(self.df.columns)}")

    def get_bonus(self, affection_level: int) -> Tuple[float, float, float]:
        return self._map.get(int(affection_level), (0.0, 0.0, 0.0))


# =========================================================
# Phase 1 Calculator
# =========================================================

@dataclass
class CombatStaticCalcConfig:
    character_excel: str = "Character.xlsx"
    sheet_character_index: str = "CharacterIndex"
    sheet_base_stat_by_level: str = "CharacterBaseStatByLevel"

    # optional
    affection_excel: str = "Affection.xlsx"
    sheet_affection_by_level: str = "AffectionByLevel"


class CombatStaticCalculator:
    def __init__(self, config: CombatStaticCalcConfig, verbose: bool = False) -> None:
        self.config = config
        self.verbose = verbose

        # Required tables
        base_df = load_sheet(config.character_excel, config.sheet_base_stat_by_level)
        self.base_by_level = CharacterBaseStatByLevelTable(base_df)

        # Optional tables
        aff_df = try_load_sheet(config.affection_excel, config.sheet_affection_by_level)
        self.affection = AffectionByLevelTable(aff_df) if aff_df is not None else None

    def calc_character_snapshot(
        self,
        character_id: str,
        level: float,
        affection_level: int = 0,
    ) -> CharacterSnapshot:
        base = self.base_by_level.get(character_id, level)

        atk = float(base.atk)
        defense = float(base.defense)
        hp = float(base.hp)

        # Optional affection flat (your memory: Affection flat only)
        if self.affection is not None and affection_level > 0:
            b_atk, b_def, b_hp = self.affection.get_bonus(affection_level)
            atk += b_atk
            defense += b_def
            hp += b_hp

        snap = CharacterSnapshot(
            character_id=character_id,
            final_atk=atk,
            final_def=defense,
            final_hp=hp,
            level=level,
        )
        return snap


# =========================================================
# Public function for main.py
# =========================================================

def calc_all_character_snapshots(verbose: bool = False) -> List[CharacterSnapshot]:
    """
    Used by main.py to produce party snapshots.

    Data source:
        CombatInputPanel.xlsx / CombatInputPanel
            - CharacterId, Level, AffectionLevel ...
    """
    # Read input panel (which characters to calculate)
    input_repo = RuntimeInputRepository(data_dir=DATA_DIR, log=verbose)
    inputs_by_character = input_repo.load_combat_input_panel(
        excel_name="CombatInputPanel.xlsx",
        sheet_name="CombatInputPanel",
    )

    # Build calculator
    calc = CombatStaticCalculator(config=CombatStaticCalcConfig(), verbose=verbose)

    out: List[CharacterSnapshot] = []
    for cid, inp in inputs_by_character.items():
        snap = calc.calc_character_snapshot(
            character_id=cid,
            level=float(inp.level),
            affection_level=int(inp.affection_level),
        )
        out.append(snap)

        if verbose:
            print(
                f"[Phase1] {cid} Lv={inp.level} "
                f"ATK={snap.final_atk:.1f} DEF={snap.final_def:.1f} HP={snap.final_hp:.1f} "
                f"(Affection={inp.affection_level})"
            )

    # Keep stable ordering by CharacterId (deterministic)
    out.sort(key=lambda s: s.character_id)
    return out
