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
# CharacterIndex (Class lookup)
# =========================================================

class CharacterIndexTable:
    """
    Expect columns:
        CharacterId, Class
    """
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df.columns = self.df.columns.astype(str).str.strip()

        self.col_id = self._pick(("CharacterId", "CharacterID", "character_id"))
        self.col_class = self._pick(("Class", "class"))

        self._class_by_id: Dict[str, str] = {}
        for _, r in self.df.iterrows():
            cid = _norm(r.get(self.col_id))
            c = _norm(r.get(self.col_class))
            if cid is None or c is None:
                continue
            self._class_by_id[str(cid).strip()] = str(c).strip()

    def _pick(self, candidates: Tuple[str, ...]) -> str:
        for c in candidates:
            if c in self.df.columns:
                return c
        raise ValueError(f"CharacterIndex missing required columns: {candidates}. Existing={list(self.df.columns)}")

    def get_class(self, character_id: str) -> Optional[str]:
        return self._class_by_id.get(character_id)


# =========================================================
# PartnerLevelStat (Class + Stack bonus)
# =========================================================

@dataclass(frozen=True)
class PartnerBonusRow:
    partner_id: str
    partner_class: str
    stat_type_id: str
    stack_vals: List[float]  # index = stack_count (0..N)


class PartnerLevelStatTable:
    """
    Your sheet columns (based on screenshot):
        PartnerId, Class, StatTypeId,
        Stack0Val, Stack1Val, Stack2Val, Stack3Val, Stack4Value
    """
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df.columns = self.df.columns.astype(str).str.strip()

        self.col_partner_id = self._pick(("PartnerId", "PartnerID"))
        self.col_class = self._pick(("Class",))
        self.col_stat_type = self._pick(("StatTypeId", "StatTypeID"))

        self.col_s0 = self._pick(("Stack0Val", "Stack0Value"))
        self.col_s1 = self._pick(("Stack1Val", "Stack1Value"))
        self.col_s2 = self._pick(("Stack2Val", "Stack2Value"))
        self.col_s3 = self._pick(("Stack3Val", "Stack3Value"))
        self.col_s4 = self._pick(("Stack4Value", "Stack4Val", "Stack4Value "))

        self._rows_by_partner: Dict[str, PartnerBonusRow] = {}
        for _, r in self.df.iterrows():
            pid = _norm(r.get(self.col_partner_id))
            pclass = _norm(r.get(self.col_class))
            st = _norm(r.get(self.col_stat_type))
            if pid is None or pclass is None or st is None:
                continue

            row = PartnerBonusRow(
                partner_id=str(pid).strip(),
                partner_class=str(pclass).strip(),
                stat_type_id=str(st).strip(),
                stack_vals=[
                    _to_float(r.get(self.col_s0), 0.0),
                    _to_float(r.get(self.col_s1), 0.0),
                    _to_float(r.get(self.col_s2), 0.0),
                    _to_float(r.get(self.col_s3), 0.0),
                    _to_float(r.get(self.col_s4), 0.0),
                ],
            )
            self._rows_by_partner[row.partner_id] = row

    def _pick(self, candidates: Tuple[str, ...]) -> str:
        for c in candidates:
            if c in self.df.columns:
                return c
        raise ValueError(f"PartnerLevelStat missing required columns: {candidates}. Existing={list(self.df.columns)}")

    def get_row(self, partner_id: str) -> Optional[PartnerBonusRow]:
        return self._rows_by_partner.get(partner_id)

    def get_partner_class(self, partner_id: str) -> Optional[str]:
        r = self.get_row(partner_id)
        return r.partner_class if r else None

    def get_stack_bonus(self, partner_id: str, stack_count: int) -> Tuple[Optional[str], float]:
        r = self.get_row(partner_id)
        if r is None:
            return None, 0.0
        idx = max(0, min(int(stack_count), len(r.stack_vals) - 1))
        return r.stat_type_id, float(r.stack_vals[idx])


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

        for r in rows:
            if abs(r.level - level) < 1e-6:
                return r

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

    partner_excel: str = "Partner.xlsx"
    sheet_partner_level_stat: str = "PartnerStatStack"

    affection_excel: str = "Affection.xlsx"
    sheet_affection_by_level: str = "AffectionByLevel"


class CombatStaticCalculator:
    def __init__(self, config: CombatStaticCalcConfig, verbose: bool = False) -> None:
        self.config = config
        self.verbose = verbose

        base_df = load_sheet(config.character_excel, config.sheet_base_stat_by_level)
        self.base_by_level = CharacterBaseStatByLevelTable(base_df)

        char_index_df = try_load_sheet(config.character_excel, config.sheet_character_index)
        self.character_index = CharacterIndexTable(char_index_df) if char_index_df is not None else None

        partner_df = try_load_sheet(config.partner_excel, config.sheet_partner_level_stat)
        self.partner_level_stat = PartnerLevelStatTable(partner_df) if partner_df is not None else None

        aff_df = try_load_sheet(config.affection_excel, config.sheet_affection_by_level)
        self.affection = AffectionByLevelTable(aff_df) if aff_df is not None else None

    def calc_character_snapshot(
        self,
        character_id: str,
        level: float,
        affection_level: int = 0,
        partner_id: Optional[str] = None,
        partner_stack_count: int = 0,
    ) -> CharacterSnapshot:
        base = self.base_by_level.get(character_id, level)

        atk = float(base.atk)
        defense = float(base.defense)
        hp = float(base.hp)

        # Affection (flat)
        if self.affection is not None and affection_level > 0:
            b_atk, b_def, b_hp = self.affection.get_bonus(affection_level)
            atk += b_atk
            defense += b_def
            hp += b_hp

        # Partner bonus (only if class matches)
        if (
            partner_id is not None
            and self.character_index is not None
            and self.partner_level_stat is not None
        ):
            owner_class = self.character_index.get_class(character_id)
            pclass = self.partner_level_stat.get_partner_class(partner_id)
            is_match = (owner_class is not None and pclass is not None and owner_class == pclass)

            if is_match:
                stat_type_id, bonus = self.partner_level_stat.get_stack_bonus(partner_id, partner_stack_count)

                # 你的 PartnerLevelStat 表目前是「百分比」增益（0.08~0.16）
                # Attack/Health 直接在 Phase1 套入 snapshot
                if stat_type_id == "PartnerAttackIncrease":
                    atk *= (1.0 + bonus)
                elif stat_type_id == "PartnerHealthIncrease":
                    hp *= (1.0 + bonus)
                elif stat_type_id == "PartnerHealingIncrease":
                    # 治療乘區不適合進 snapshot，留給 AbilitySystem / runtime_mod
                    # 這裡不動 atk/def/hp
                    pass

                if self.verbose:
                    print(
                        f"[PartnerBonus] char={character_id} class={owner_class} "
                        f"partner={partner_id} pclass={pclass} match={is_match} "
                        f"stack={partner_stack_count} stat={stat_type_id} bonus={bonus}"
                    )
            else:
                if self.verbose:
                    print(
                        f"[PartnerBonus] char={character_id} class={owner_class} "
                        f"partner={partner_id} pclass={pclass} match={is_match} (skip)"
                    )

        snap = CharacterSnapshot(
            character_id=character_id,
            final_atk=float(atk),
            final_def=float(defense),
            final_hp=float(hp),
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
            - CharacterId, Level, PartnerId, PartnerStackCount, AffectionLevel ...
    """
    input_repo = RuntimeInputRepository(data_dir=DATA_DIR, log=verbose)
    inputs_by_character = input_repo.load_combat_input_panel(
        excel_name="CombatInputPanel.xlsx",
        sheet_name="CombatInputPanel",
    )

    calc = CombatStaticCalculator(config=CombatStaticCalcConfig(), verbose=verbose)

    out: List[CharacterSnapshot] = []
    for cid, inp in inputs_by_character.items():
        snap = calc.calc_character_snapshot(
            character_id=cid,
            level=float(inp.level),
            affection_level=int(inp.affection_level),
            partner_id=inp.partner_id,
            partner_stack_count=int(inp.partner_stack_count),
        )
        out.append(snap)

        if verbose:
            print(
                f"[Phase1] {cid} Lv={inp.level} "
                f"ATK={snap.final_atk:.1f} DEF={snap.final_def:.1f} HP={snap.final_hp:.1f} "
                f"(Affection={inp.affection_level}, PartnerId={inp.partner_id}, Stack={inp.partner_stack_count})"
            )

    out.sort(key=lambda s: s.character_id)
    return out
