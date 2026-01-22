# ability_models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


# =========================================================
# Enums
# =========================================================
class TriggerEvent(str, Enum):
    BattleStart = "BattleStart"
    FirstTurnStart = "FirstTurnStart"
    TurnStart = "TurnStart"
    OnPlayCard = "OnPlayCard"
    TurnEnd = "TurnEnd"


class ConditionLogic(str, Enum):
    AND = "AND"
    OR = "OR"


class ConditionType(str, Enum):
    # MVP for Douglas
    OwnerClassEqualsPartnerClass = "OwnerClassEqualsPartnerClass"


class ExecMode(str, Enum):
    Sequential = "Sequential"
    Parallel = "Parallel"  # reserved / future


class AbilityEffectType(str, Enum):
    # MVP
    AddStatus = "AddStatus"
    SetStatusParam = "SetStatusParam"


class ValueRefType(str, Enum):
    None_ = "None"
    PartnerStack = "PartnerStack"


class StatusType(str, Enum):
    # MVP
    AttackUp = "AttackUp"


class StatusParamKey(str, Enum):
    # MVP for AttackUp
    increase = "increase"


# =========================================================
# Dataclasses
# =========================================================
@dataclass(frozen=True)
class AbilityDef:
    ability_id: str
    trigger_event: TriggerEvent
    condition_group_id: Optional[str]
    effect_group_id: str
    priority: int = 0


@dataclass(frozen=True)
class ConditionGroupDef:
    condition_group_id: str
    logic: ConditionLogic = ConditionLogic.AND


@dataclass(frozen=True)
class ConditionRowDef:
    condition_group_id: str
    row_index: int
    condition_type: ConditionType
    # 先保留擴充欄位（之後你要做 target / compare / param 都用得到）
    arg1: Optional[str] = None
    arg2: Optional[str] = None


@dataclass(frozen=True)
class EffectGroupDef:
    effect_group_id: str
    exec_mode: ExecMode = ExecMode.Sequential


@dataclass(frozen=True)
class EffectRowDef:
    effect_group_id: str
    row_index: int
    effect_type: AbilityEffectType

    # 用於 AddStatus:
    #   value1 = StatusType
    #   value2 = duration_turn
    #
    # 用於 SetStatusParam:
    #   value1 = param_key
    #   value2 = const_value（若使用 ValueRefType 則可為 None）
    value1: Optional[str] = None
    value2: Optional[float] = None

    # Dynamic value reference
    value_ref_type: ValueRefType = ValueRefType.None_
    value_ref_id: Optional[str] = None


@dataclass
class StatusInstance:
    status_type: StatusType
    remaining_turns: int
    params: Dict[str, float]
    source_ability_id: Optional[str] = None
