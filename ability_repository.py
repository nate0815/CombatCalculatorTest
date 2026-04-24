# ability_repository.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ability_models import (
    AbilityDef,
    ApplyPhase,
    ConditionGroupDef,
    ConditionLogic,
    ConditionRowDef,
    ConditionType,
    EffectGroupDef,
    EffectRowDef,
    ExecMode,
    AbilityEffectType,
    TriggerEvent,
    SourceType,
    ValueRefType,
    TargetScope,
    DurationType,
)


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
        if s == "" or s.lower() in ("none", "nan"):
            return None
        return s
    return v


def _to_int(v: Any, default: int = 0) -> int:
    v = _norm(v)
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    v = _norm(v)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _to_bool(v: Any, default: bool = True) -> bool:
    v = _norm(v)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "t", "yes", "y", "1"):
            return True
        if s in ("false", "f", "no", "n", "0"):
            return False
    return default


def _parse_enum(enum_cls, v: Any, default=None):
    v = _norm(v)
    if v is None:
        return default
    try:
        return enum_cls(str(v))
    except Exception:
        return default


@dataclass
class AbilityLoadResult:
    ability_system_args: Optional[Tuple[List[AbilityDef], Dict[str, ConditionGroupDef], List[ConditionRowDef], Dict[str, EffectGroupDef], List[EffectRowDef]]] = None
    partner_abilities: Dict[str, List[str]] = None
    partner_stack_curves: Dict[str, Dict[str, List[float]]] = None


class AbilityRepository:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def try_load_all(
        self,
        excel_name: str = "Ability.xlsx",
        sheet_ability: str = "AbilityDef",
        sheet_condition_group: str = "ConditionGroup",
        sheet_condition_row: str = "ConditionRow",
        sheet_effect_group: str = "EffectGroup",
        sheet_effect_row: str = "EffectRow",
        sheet_partner_ability: str = "PartnerAbility",
        sheet_partner_stack_curve: str = "PartnerStackCurve",
    ) -> AbilityLoadResult:
        path = self.data_dir / excel_name
        if not path.exists():
            return AbilityLoadResult(ability_system_args=None, partner_abilities={}, partner_stack_curves={})

        def read(sheet: str) -> pd.DataFrame:
            df = pd.read_excel(path, sheet_name=sheet)
            df.columns = df.columns.astype(str).str.strip()
            return df

        # ---- core defs ----
        a_df = read(sheet_ability)
        cg_df = read(sheet_condition_group)
        cr_df = read(sheet_condition_row)
        eg_df = read(sheet_effect_group)
        er_df = read(sheet_effect_row)

        ability_defs: List[AbilityDef] = []
        for _, r in a_df.iterrows():
            ability_defs.append(
                AbilityDef(
                    ability_id=str(_norm(r.get("AbilityId"))),
                    trigger_event=_parse_enum(TriggerEvent, r.get("TriggerEvent"), TriggerEvent.BattleStart),
                    condition_group_id=_norm(r.get("ConditionGroupId")),
                    effect_group_id=str(_norm(r.get("EffectGroupId"))),
                    priority=_to_int(r.get("Priority"), 0),
                    apply_phase=_parse_enum(ApplyPhase, r.get("ApplyPhase"), ApplyPhase.RUNTIME),
                    source_type=_parse_enum(SourceType, r.get("SourceType"), None),
                    enabled=_to_bool(r.get("Enabled"), True),
                )
            )

        condition_groups: Dict[str, ConditionGroupDef] = {}
        for _, r in cg_df.iterrows():
            gid = _norm(r.get("ConditionGroupId"))
            if gid is None:
                continue
            condition_groups[str(gid)] = ConditionGroupDef(
                condition_group_id=str(gid),
                logic=_parse_enum(ConditionLogic, r.get("Logic"), ConditionLogic.AND),
            )

        condition_rows: List[ConditionRowDef] = []
        for _, r in cr_df.iterrows():
            gid = _norm(r.get("ConditionGroupId"))
            if gid is None:
                continue
            condition_rows.append(
                ConditionRowDef(
                    condition_group_id=str(gid),
                    row_index=_to_int(r.get("RowIndex"), 0),
                    condition_type=_parse_enum(ConditionType, r.get("ConditionType"), ConditionType.OwnerClassEqualsPartnerClass),
                    arg1=_norm(r.get("Arg1")),
                    arg2=_norm(r.get("Arg2")),
                    arg3=_norm(r.get("Arg3")),
                    arg4=_norm(r.get("Arg4")),
                )
            )

        effect_groups: Dict[str, EffectGroupDef] = {}
        for _, r in eg_df.iterrows():
            gid = _norm(r.get("EffectGroupId"))
            if gid is None:
                continue
            effect_groups[str(gid)] = EffectGroupDef(
                effect_group_id=str(gid),
                exec_mode=_parse_enum(ExecMode, r.get("ExecMode"), ExecMode.Sequential),
            )

        effect_rows: List[EffectRowDef] = []
        for _, r in er_df.iterrows():
            gid = _norm(r.get("EffectGroupId"))
            if gid is None:
                continue
            effect_rows.append(
                EffectRowDef(
                    effect_group_id=str(gid),
                    row_index=_to_int(r.get("RowIndex"), 0),
                    effect_type=_parse_enum(AbilityEffectType, r.get("EffectType"), AbilityEffectType.SetRuntimeMod),
                    value1=_norm(r.get("Value1")),
                    value2=_to_float(r.get("Value2"), None) if _norm(r.get("Value2")) is not None else None,
                    value_ref_type=_parse_enum(ValueRefType, r.get("ValueRefType"), ValueRefType.None_),
                    value_ref_id=_norm(r.get("ValueRefId")),
                    target_scope=_parse_enum(TargetScope, r.get("TargetScope"), None),
                    duration_type=_parse_enum(DurationType, r.get("DurationType"), None),
                    duration_value=_to_int(r.get("DurationValue"), None) if _norm(r.get("DurationValue")) is not None else None,
                )
            )

        # ---- partner binding ----
        partner_abilities: Dict[str, List[str]] = {}
        try:
            pa_df = read(sheet_partner_ability)
            for _, r in pa_df.iterrows():
                pid = _norm(r.get("PartnerId"))
                aid = _norm(r.get("AbilityId"))
                if pid is None or aid is None:
                    continue
                partner_abilities.setdefault(str(pid), []).append(str(aid))
        except Exception:
            partner_abilities = {}

        # ---- partner stack curve ----
        # Expect columns: PartnerId, StatTypeId, V0, V1, V2, ... (stack_count index)
        partner_stack_curves: Dict[str, Dict[str, List[float]]] = {}
        try:
            pc_df = read(sheet_partner_stack_curve)
            for _, r in pc_df.iterrows():
                pid = _norm(r.get("PartnerId"))
                sid = _norm(r.get("StatTypeId"))
                if pid is None or sid is None:
                    continue
                values: List[float] = []
                # collect V0..Vn
                for k in pc_df.columns:
                    ks = str(k)
                    if ks.lower().startswith("v"):
                        values.append(_to_float(r.get(k), 0.0))
                partner_stack_curves.setdefault(str(pid), {})[str(sid)] = values
        except Exception:
            partner_stack_curves = {}

        return AbilityLoadResult(
            ability_system_args=(ability_defs, condition_groups, condition_rows, effect_groups, effect_rows),
            partner_abilities=partner_abilities,
            partner_stack_curves=partner_stack_curves,
        )
