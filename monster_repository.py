"""
monster_repository.py
Phase: Monster Data (Repository)

Responsibility:
- Load Monster.xlsx sheets: MonsterIndex / MonsterBaseStat / MonsterSkill
- Build in-memory MonsterDef objects (index + base + skill list)
- Provide query APIs for battle simulator

Expected columns:
- MonsterIndex: MonsterId, MonsterRank, MonsterWeight
- MonsterBaseStat: MonsterId, Level, Attack, Defense, Health
- MonsterSkill:
    SkillId, MonsterId, SkillType, Value,
    CounterMax, ReloadTiming, CounterMode, CounterStartTrigger, EnemyPhaseActionRule, Target
"""

import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional
from models import MonsterBaseStat, MonsterSkillDef, MonsterDef

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


def load_sheet(excel_name: str, sheet_name: str) -> pd.DataFrame:
    path = DATA_DIR / excel_name
    if not path.exists():
        raise FileNotFoundError(f"❌ Excel file not found: {path}")
    df = pd.read_excel(path, sheet_name=sheet_name)
    df.columns = df.columns.astype(str).str.strip()
    return df


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
        if x is None:
            return default
        s = str(x).strip()
        if s == "" or s.lower() in ("none", "nan"):
            return default
        return float(x)
    except Exception:
        return default


def to_str(x: Any, default: str = "") -> str:
    s = clean_id(x)
    return s if s else default


class MonsterRepository:
    def __init__(self, excel_name: str = "Monster.xlsx"):
        self.excel_name = excel_name
        self._monsters_by_id: Dict[str, MonsterDef] = {}

    def load(self) -> None:
        idx_df = load_sheet(self.excel_name, "MonsterIndex")
        base_df = load_sheet(self.excel_name, "MonsterBaseStat")
        skill_df = load_sheet(self.excel_name, "MonsterSkill")

        # Base stats by monster id (MVP: Level=1 single row per monster)
        base_by_id: Dict[str, MonsterBaseStat] = {}
        for _, row in base_df.iterrows():
            mid = clean_id(row.get("MonsterId"))
            if not mid:
                continue
            base_by_id[mid] = MonsterBaseStat(
                monster_id=mid,
                level=to_int(row.get("Level"), 1),
                attack=to_float(row.get("Attack"), 0.0),
                defense=to_float(row.get("Defense"), 0.0),
                health=to_float(row.get("Health"), 0.0),
            )

        # Skills grouped by monster id
        skills_by_id: Dict[str, List[MonsterSkillDef]] = {}
        for _, row in skill_df.iterrows():
            skill_id = clean_id(row.get("SkillId"))
            mid = clean_id(row.get("MonsterId"))
            if not skill_id or not mid:
                continue

            sk = MonsterSkillDef(
                skill_id=skill_id,
                monster_id=mid,
                skill_type=to_str(row.get("SkillType"), "Attack"),
                value=to_float(row.get("Value"), 0.0),
                counter_max=to_int(row.get("CounterMax"), 0),
                reload_timing=to_str(row.get("ReloadTiming"), "AfterEnemyAttackPhase"),
                counter_mode=to_str(row.get("CounterMode"), "Enabled"),
                counter_start_trigger=to_str(row.get("CounterStartTrigger"), "OnPlayerPlayCard"),
                enemy_phase_action_rule=to_str(row.get("EnemyPhaseActionRule"), "ActIfNotActedThisTurn"),
                target=to_str(row.get("Target"), "Player"),
            )
            skills_by_id.setdefault(mid, []).append(sk)

        # Sort skills for stability (by skill_id)
        for mid in list(skills_by_id.keys()):
            skills_by_id[mid] = sorted(skills_by_id[mid], key=lambda s: s.skill_id)

        # Build MonsterDef from index
        self._monsters_by_id.clear()
        for _, row in idx_df.iterrows():
            mid = clean_id(row.get("MonsterId"))
            if not mid:
                continue
            base = base_by_id.get(mid)
            if base is None:
                raise ValueError(f"❌ MonsterBaseStat missing for MonsterId={mid}")

            m = MonsterDef(
                monster_id=mid,
                monster_rank=to_str(row.get("MonsterRank"), "Normal"),
                monster_weight=to_int(row.get("MonsterWeight"), 1),
                base_stat=base,
                skills=skills_by_id.get(mid, []),
            )
            self._monsters_by_id[mid] = m

    def get_monster(self, monster_id: str) -> Optional[MonsterDef]:
        return self._monsters_by_id.get(monster_id)

    def get_all_monsters(self) -> List[MonsterDef]:
        return list(self._monsters_by_id.values())
