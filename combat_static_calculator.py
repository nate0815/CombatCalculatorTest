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
# Helpers
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
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in ("none", "nan"):
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
# Character Base Stat
# =========================================================

@dataclass(frozen=True)
class BaseStatRow:
    level: float
    atk: float
    defense: float
    hp: float


class CharacterBaseStatByLevelTable:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df.columns = self.df.columns.astype(str).str.strip()

        self.col_cid = self._pick(("CharacterId",))
        self.col_lv = self._pick(("Level",))
        self.col_atk = self._pick(("Attack", "Atk"))
        self.col_def = self._pick(("Defense", "Def"))
        self.col_hp = self._pick(("Health", "HP"))

        self._rows: Dict[str, List[BaseStatRow]] = {}
        for _, r in self.df.iterrows():
            cid = _norm(r.get(self.col_cid))
            lv = _norm(r.get(self.col_lv))
            if cid is None or lv is None:
                continue
            row = BaseStatRow(
                level=_to_float(lv),
                atk=_to_float(r.get(self.col_atk)),
                defense=_to_float(r.get(self.col_def)),
                hp=_to_float(r.get(self.col_hp)),
            )
            self._rows.setdefault(str(cid), []).append(row)

        for cid in self._rows:
            self._rows[cid].sort(key=lambda r: r.level)

    def _pick(self, candidates: Tuple[str, ...]) -> str:
        for c in candidates:
            if c in self.df.columns:
                return c
        raise ValueError(f"Missing column: {candidates}")

    def get(self, cid: str, level: float) -> BaseStatRow:
        rows = self._rows[cid]

        for r in rows:
            if abs(r.level - level) < 1e-6:
                return r

        lower, upper = None, None
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
        if abs(lower.level - upper.level) < 1e-6:
            return lower

        t = (level - lower.level) / (upper.level - lower.level)
        return BaseStatRow(
            level=level,
            atk=lower.atk + (upper.atk - lower.atk) * t,
            defense=lower.defense + (upper.defense - lower.defense) * t,
            hp=lower.hp + (upper.hp - lower.hp) * t,
        )


# =========================================================
# Partner Base Stat (ALWAYS APPLY)
# =========================================================

@dataclass(frozen=True)
class PartnerBaseRow:
    level: float
    atk: float
    defense: float
    hp: float


class PartnerBaseByLevelTable:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df.columns = self.df.columns.astype(str).str.strip()

        self.col_pid = self._pick(("PartnerId",))
        self.col_lv = self._pick(("Level",))
        self.col_atk = self._pick(("Attack",))
        self.col_def = self._pick(("Defense",))
        self.col_hp = self._pick(("Health",))

        self._rows: Dict[str, List[PartnerBaseRow]] = {}
        for _, r in self.df.iterrows():
            pid = _norm(r.get(self.col_pid))
            lv = _norm(r.get(self.col_lv))
            if pid is None or lv is None:
                continue
            row = PartnerBaseRow(
                level=_to_float(lv),
                atk=_to_float(r.get(self.col_atk)),
                defense=_to_float(r.get(self.col_def)),
                hp=_to_float(r.get(self.col_hp)),
            )
            self._rows.setdefault(str(pid), []).append(row)

        for pid in self._rows:
            self._rows[pid].sort(key=lambda r: r.level)

    def _pick(self, candidates: Tuple[str, ...]) -> str:
        for c in candidates:
            if c in self.df.columns:
                return c
        raise ValueError(f"PartnerLevelStat missing {candidates}")

    def get(self, pid: str, level: float) -> PartnerBaseRow:
        rows = self._rows[pid]

        for r in rows:
            if abs(r.level - level) < 1e-6:
                return r

        lower, upper = None, None
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
        if abs(lower.level - upper.level) < 1e-6:
            return lower

        t = (level - lower.level) / (upper.level - lower.level)
        return PartnerBaseRow(
            level=level,
            atk=lower.atk + (upper.atk - lower.atk) * t,
            defense=lower.defense + (upper.defense - lower.defense) * t,
            hp=lower.hp + (upper.hp - lower.hp) * t,
        )


# =========================================================
# Calculator
# =========================================================

class CombatStaticCalculator:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose

        self.char_base = CharacterBaseStatByLevelTable(
            load_sheet("Character.xlsx", "CharacterBaseStatByLevel")
        )
        self.partner_base = PartnerBaseByLevelTable(
            load_sheet("Partner.xlsx", "PartnerLevelStat")
        )

    def calc(
        self,
        character_id: str,
        level: float,
        partner_id: Optional[str],
        partner_level: float,
        # ❌ 以下參數尚未接入計算：
        #   - affection_level: AffectionLevel 讀取並儲存，但 Affection.xlsx 尚未接入
        #   - is_partner_bonus_applied: CombatInputPanel 的旗標讀取後未控制此處，目前固定套用夥伴加成
        #   - partner_stack_count: PartnerStack 加成由 Ability 系統處理，Phase 1 不套用
    ) -> CharacterSnapshot:
        base = self.char_base.get(character_id, level)
        atk, defense, hp = base.atk, base.defense, base.hp

        if partner_id:
            p = self.partner_base.get(partner_id, partner_level)
            atk += p.atk
            defense += p.defense
            hp += p.hp

            if self.verbose:
                print(
                    f"[PartnerBase] {character_id} +ATK={p.atk} +DEF={p.defense} +HP={p.hp}"
                )

        return CharacterSnapshot(
            character_id=character_id,
            final_atk=atk,
            final_def=defense,
            final_hp=hp,
            level=level,
        )


# =========================================================
# Public API
# =========================================================

def calc_all_character_snapshots(verbose: bool = False) -> List[CharacterSnapshot]:
    repo = RuntimeInputRepository(DATA_DIR, log=verbose)
    inputs = repo.load_combat_input_panel(
        excel_name="CombatInputPanel.xlsx",
        sheet_name="CombatInputPanel",
    )

    calc = CombatStaticCalculator(verbose=verbose)
    out: List[CharacterSnapshot] = []

    for cid, inp in inputs.items():
        snap = calc.calc(
            character_id=cid,
            level=inp.level,
            partner_id=inp.partner_id,
            partner_level=inp.partner_level,
        )
        out.append(snap)

        if verbose:
            print(
                f"[Phase1] {cid} Lv={inp.level} "
                f"ATK={snap.final_atk:.1f} DEF={snap.final_def:.1f} HP={snap.final_hp:.1f}"
            )

    return out
