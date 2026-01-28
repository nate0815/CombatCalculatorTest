# ability_models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


# =========================================================
# Enums
# =========================================================
class ApplyPhase(str, Enum):
    """
    Where this rule is applied.

    - PRE_BATTLE: applied once when building/initializing battle context.
    - RUNTIME: applied during battle by triggers (e.g., FirstTurnStart).
    """
    PRE_BATTLE = "PRE_BATTLE"
    RUNTIME = "RUNTIME"


class SourceType(str, Enum):
    """
    Where the ability comes from. (For now you mainly use Partner.)
    """
    Partner = "Partner"
    Character = "Character"
    Equipment = "Equipment"
    Card = "Card"
    Monster = "Monster"


class TargetScope(str, Enum):
    """
    Target scope for effects. (Optional for now; future-proofing)
    """
    Owner = "Owner"
    Party = "Party"
    Enemy = "Enemy"
    AllEnemies = "AllEnemies"


class DurationType(str, Enum):
    """
    Optional duration semantics for effects/status.
    """
    Instant = "Instant"
    TurnCount = "TurnCount"
    Permanent = "Permanent"


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

    # NEW (from your updated sheets)
    apply_phase: ApplyPhase = ApplyPhase.RUNTIME
    source_type: Optional[SourceType] = None
    enabled: bool = True


@dataclass(frozen=True)
class ConditionGroupDef:
    condition_group_id: str
    logic: ConditionLogic = ConditionLogic.AND


@dataclass(frozen=True)
class ConditionRowDef:
    condition_group_id: str
    row_index: int
    condition_type: ConditionType

    # NEW: support Param1~Param4 (future-proof)
    arg1: Optional[str] = None
    arg2: Optional[str] = None
    arg3: Optional[str] = None
    arg4: Optional[str] = None


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
    # value1 = StatusType
    # value2 = duration_turn (int)
    #
    # 用於 SetStatusParam:
    # value1 = param_key
    # value2 = const_value（若使用 ValueRefType 則可為 None）
    value1: Optional[str] = None
    value2: Optional[float] = None

    # Dynamic value reference
    value_ref_type: ValueRefType = ValueRefType.None_
    value_ref_id: Optional[str] = None

    # NEW: optional target/duration metadata (can be ignored by runtime for now)
    target_scope: Optional[TargetScope] = None
    duration_type: Optional[DurationType] = None
    duration_value: Optional[int] = None


@dataclass
class StatusInstance:
    status_type: StatusType
    remaining_turns: int
    params: Dict[str, float]
    source_ability_id: Optional[str] = None
