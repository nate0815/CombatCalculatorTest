# monster_repository.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from models import (
    CounterMode,
    CounterStartTrigger,
    EnemyPhaseActionRule,
    LogLevel,
    MonsterBaseStat,
    MonsterIndex,
    MonsterSkill,
    MonsterSkillType,
    ReloadTiming,
    TargetType,
    parse_enum,
)


@dataclass
class MonsterRepository:
    """
    Load MonsterIndex / MonsterBaseStat / MonsterSkill from Excel.

    Current MVP assumes:
    - MonsterIndex: MonsterId, MonsterRank, MonsterWeight
    - MonsterBaseStat: MonsterId, Level, Attack, Defense, Health
    - MonsterSkill: SkillId, MonsterId, SkillType, Value, CounterMax,
                    ReloadTiming, CounterMode, CounterStartTrigger,
                    EnemyPhaseActionRule, Target
    """
    data_dir: Path
    log_level: LogLevel = LogLevel.INFO

    def load_monsters(
        self,
        excel_name: str,
        sheet_index: str,
        sheet_base_stat: str,
        sheet_skill: str,
    ) -> Tuple[List[MonsterIndex], Dict[str, MonsterBaseStat], List[MonsterSkill]]:
        index_df = self._load_sheet(excel_name, sheet_index)
        base_df = self._load_sheet(excel_name, sheet_base_stat)
        skill_df = self._load_sheet(excel_name, sheet_skill)

        indexes = self._parse_index(index_df)
        base_stats = self._parse_base_stat(base_df)
        skills = self._parse_skills(skill_df)

        self._log_info(
            f"[Monster] Loaded {len(indexes)} monsters: {', '.join(m.monster_id for m in indexes)}"
        )
        return indexes, base_stats, skills

    # -----------------------------------------------------
    # Internal: Loaders
    # -----------------------------------------------------

    def _load_sheet(self, excel_name: str, sheet_name: str) -> pd.DataFrame:
        path = self.data_dir / excel_name
        if not path.exists():
            raise FileNotFoundError(f"❌ Excel file not found: {path}")

        try:
            df = pd.read_excel(path, sheet_name=sheet_name)
        except ValueError:
            raise ValueError(f"❌ Sheet '{sheet_name}' not found in {excel_name}")

        df.columns = df.columns.astype(str).str.strip()
        return df

    # -----------------------------------------------------
    # Internal: Parsers
    # -----------------------------------------------------

    def _parse_index(self, df: pd.DataFrame) -> List[MonsterIndex]:
        required = ["MonsterId", "MonsterRank", "MonsterWeight"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"❌ MonsterIndex missing column: {col}")

        out: List[MonsterIndex] = []
        for _, row in df.iterrows():
            mid = str(row["MonsterId"]).strip()
            rank = str(row["MonsterRank"]).strip()
            w = row.get("MonsterWeight", 1)
            weight = int(w) if (w is not None and not pd.isna(w)) else 1
            out.append(MonsterIndex(monster_id=mid, monster_rank=rank, monster_weight=weight))
        return out

    def _parse_base_stat(self, df: pd.DataFrame) -> Dict[str, MonsterBaseStat]:
        required = ["MonsterId", "Level", "Attack", "Defense", "Health"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"❌ MonsterBaseStat missing column: {col}")

        out: Dict[str, MonsterBaseStat] = {}
        for _, row in df.iterrows():
            mid = str(row["MonsterId"]).strip()
            lvl = int(row["Level"]) if not pd.isna(row["Level"]) else 1
            atk = float(row["Attack"]) if not pd.isna(row["Attack"]) else 0.0
            de = float(row["Defense"]) if not pd.isna(row["Defense"]) else 0.0
            hp = float(row["Health"]) if not pd.isna(row["Health"]) else 0.0

            out[mid] = MonsterBaseStat(
                monster_id=mid,
                level=lvl,
                attack=atk,
                defense=de,
                health=hp,
            )
        return out

    def _parse_skills(self, df: pd.DataFrame) -> List[MonsterSkill]:
        required = [
            "SkillId",
            "MonsterId",
            "SkillType",
            "Value",
            "CounterMax",
            "ReloadTiming",
            "CounterMode",
            "CounterStartTrigger",
            "EnemyPhaseActionRule",
            "Target",
        ]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"❌ MonsterSkill missing column: {col}")

        out: List[MonsterSkill] = []
        for _, row in df.iterrows():
            sid = str(row["SkillId"]).strip()
            mid = str(row["MonsterId"]).strip()

            stype = parse_enum(MonsterSkillType, row.get("SkillType", ""), MonsterSkillType.Attack)
            value = float(row["Value"]) if not pd.isna(row["Value"]) else 0.0

            cmax = int(row["CounterMax"]) if not pd.isna(row["CounterMax"]) else 0
            reload_timing = parse_enum(
                ReloadTiming, row.get("ReloadTiming", ""), ReloadTiming.AfterEnemyAttackPhase
            )
            counter_mode = parse_enum(CounterMode, row.get("CounterMode", ""), CounterMode.Enabled)
            start_trigger = parse_enum(
                CounterStartTrigger,
                row.get("CounterStartTrigger", ""),
                CounterStartTrigger.OnPlayerPlayCard,
            )
            enemy_rule = parse_enum(
                EnemyPhaseActionRule,
                row.get("EnemyPhaseActionRule", ""),
                EnemyPhaseActionRule.ActIfNotActedThisTurn,
            )
            target = parse_enum(TargetType, row.get("Target", ""), TargetType.Player)

            out.append(
                MonsterSkill(
                    skill_id=sid,
                    monster_id=mid,
                    skill_type=stype,
                    value=value,
                    counter_max=cmax,
                    reload_timing=reload_timing,
                    counter_mode=counter_mode,
                    counter_start_trigger=start_trigger,
                    enemy_phase_action_rule=enemy_rule,
                    target=target,
                )
            )
        return out

    # -----------------------------------------------------
    # Internal: Logging
    # -----------------------------------------------------

    def _log_info(self, msg: str) -> None:
        if self.log_level in (LogLevel.INFO, LogLevel.DEBUG, LogLevel.TRACE):
            print(msg)
