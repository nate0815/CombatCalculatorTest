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
    - RUNTIME: applied during battle by triggers (e.g., BattleStart, OnEnemyAttack).
    """
    PRE_BATTLE = "PRE_BATTLE"
    RUNTIME = "RUNTIME"


class SourceType(str, Enum):
    """Where the ability comes from."""
    Partner = "Partner"
    Character = "Character"
    Equipment = "Equipment"
    Card = "Card"
    Monster = "Monster"


class TargetScope(str, Enum):
    """Target scope for effects. (Optional; future-proofing)"""
    Owner = "Owner"
    Party = "Party"
    Enemy = "Enemy"
    AllEnemies = "AllEnemies"


class DurationType(str, Enum):
    """Optional duration semantics for effects/status."""
    Instant = "Instant"
    TurnCount = "TurnCount"
    Permanent = "Permanent"


class TriggerEvent(str, Enum):
    BattleStart = "BattleStart"
    FirstTurnStart = "FirstTurnStart"
    TurnStart = "TurnStart"
    OnPlayCard = "OnPlayCard"
    TurnEnd = "TurnEnd"

    # NEW: needed for Arwen (consume points on being attacked)
    OnEnemyAttack = "OnEnemyAttack"


class ConditionLogic(str, Enum):
    AND = "AND"
    OR = "OR"


class ConditionType(str, Enum):
    # MVP for Douglas / Partner bonus
    OwnerClassEqualsPartnerClass = "OwnerClassEqualsPartnerClass"


class ExecMode(str, Enum):
    Sequential = "Sequential"
    Parallel = "Parallel"  # reserved / future


class AbilityEffectType(str, Enum):
    # MVP
    AddStatus = "AddStatus"
    SetStatusParam = "SetStatusParam"

    # NEW: generic state edits for data-driven runtime effects
    # - extra_ctx: persistent battle context (cross-turn)
    SetExtraValue = "SetExtraValue"
    AddExtraValue = "AddExtraValue"

    # - runtime_mod: per-trigger / per-step runtime modifiers
    SetRuntimeMod = "SetRuntimeMod"

    # NEW: convenience effect for Arwen:
    # If extra_ctx[points_key] > 0:
    #   extra_ctx[points_key] -= 1
    #   runtime_mod[incoming_damage_key] = damage_mul
    # else:
    #   runtime_mod[incoming_damage_key] = 1.0 (or keep default)
    ConsumeExtraPointAndSetIncomingDamageMul = "ConsumeExtraPointAndSetIncomingDamageMul"


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

    # From your updated sheets
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

    # Support Param1~Param4 (future-proof)
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

    """
    EffectRowDef.value* usage (by effect_type):

    - AddStatus:
        value1 = StatusType (string)
        value2 = duration_turn (float/int)

    - SetStatusParam:
        value1 = StatusParamKey (string)
        value2 = const_value (float) if ValueRefType.None_
                 (if using ValueRefType, value2 can be None)

    - SetExtraValue / AddExtraValue:
        value1 = key (string) to extra_ctx
        value2 = number to set/add (float)

    - SetRuntimeMod:
        value1 = key (string) to runtime_mod
        value2 = number to set (float)

    - ConsumeExtraPointAndSetIncomingDamageMul:
        value1 = points_key in extra_ctx (string), e.g. "arwen_points"
        value2 = damage_mul (float), e.g. 0.9
        value_ref_id (optional) can be used as incoming_damage_key in runtime_mod
          - if None, default incoming key is "incoming_damage_multiplier"
    """

    value1: Optional[str] = None
    value2: Optional[float] = None

    # Dynamic value reference
    value_ref_type: ValueRefType = ValueRefType.None_
    value_ref_id: Optional[str] = None

    # Optional target/duration metadata (can be ignored by runtime for now)
    target_scope: Optional[TargetScope] = None
    duration_type: Optional[DurationType] = None
    duration_value: Optional[int] = None


@dataclass
class StatusInstance:
    status_type: StatusType
    remaining_turns: int
    params: Dict[str, float]
    source_ability_id: Optional[str] = None
