from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar


# =========================================================
# Logging
# =========================================================

class LogLevel(str, Enum):
    NONE = "NONE"
    INFO = "INFO"
    DEBUG = "DEBUG"
    TRACE = "TRACE"


# =========================================================
# Enemy Counter / Phase Rules (battle_simulator dependency)
# =========================================================

class CounterMode(str, Enum):
    None_ = "None"
    CountDown = "CountDown"
    CountUp = "CountUp"
    Fixed = "Fixed"


class CounterStartTrigger(str, Enum):
    None_ = "None"
    OnBattleStart = "OnBattleStart"
    OnEnemyPhaseStart = "OnEnemyPhaseStart"
    OnPlayerPhaseStart = "OnPlayerPhaseStart"
    OnFirstAction = "OnFirstAction"


class EnemyPhaseActionRule(str, Enum):
    """
    How enemy action + counter reload/tick is handled in enemy phase.
    (給 battle_simulator 做流程判斷用)
    """
    Default = "Default"
    ExecuteThenReload = "ExecuteThenReload"
    ReloadThenExecute = "ReloadThenExecute"
    ExecuteOnly = "ExecuteOnly"
    ReloadOnly = "ReloadOnly"


class ReloadTiming(str, Enum):
    """
    When to reload next action/counter.
    """
    AfterExecute = "AfterExecute"
    BeforeExecute = "BeforeExecute"
    Never = "Never"


# =========================================================
# Phase 1 Output (Static snapshot)
# =========================================================

@dataclass
class CharacterSnapshot:
    character_id: str
    final_atk: float
    final_def: float
    final_hp: float
    level: Optional[float] = None


@dataclass
class PlayerPartySnapshot:
    members: List[CharacterSnapshot]
    active_character_id: str
    team_hp_max: float = 0.0
    team_hp: float = 0.0

    def __post_init__(self) -> None:
        self.team_hp_max = float(sum(m.final_hp for m in self.members))
        self.team_hp = float(self.team_hp_max)


# =========================================================
# Card System
# =========================================================

class EffectType(str, Enum):
    Damage = "Damage"
    Heal = "Heal"
    Shield = "Shield"
    Buff = "Buff"
    Debuff = "Debuff"


class ScaleStat(str, Enum):
    None_ = "None"
    ATK = "ATK"
    DEF = "DEF"
    HP = "HP"


class TargetType(str, Enum):
    EnemySingle = "EnemySingle"
    EnemyAll = "EnemyAll"
    Self = "Self"
    AllySingle = "AllySingle"
    AllyAll = "AllyAll"


class CardLifecycle(str, Enum):
    Normal = "Normal"
    Exhaust = "Exhaust"
    Persist = "Persist"


class AfterPlayMove(str, Enum):
    Discard = "Discard"
    Exhaust = "Exhaust"
    KeepInHand = "KeepInHand"


class OnEndTurnAction(str, Enum):
    None_ = "None"
    Discard = "Discard"
    Exhaust = "Exhaust"


@dataclass
class Card:
    card_id: str
    character_id: str
    group_id: str
    epiphany_tier: int = 0
    ap_cost: int = 1


@dataclass
class CardEffect:
    card_id: str
    effect_index: int
    effect_type: EffectType
    scale_stat: ScaleStat
    multiplier: float
    flat_value: float
    card_lifecycle: CardLifecycle
    after_play_move: AfterPlayMove
    on_end_turn_action: OnEndTurnAction
    target: TargetType


# =========================================================
# Monster (battle_simulator dependency)
# =========================================================

@dataclass
class MonsterIndex:
    """
    Minimal monster index info for simulator.
    Extend as needed (rarity, tags, etc.)
    """
    monster_id: str
    name: Optional[str] = None


@dataclass
class MonsterBaseStat:
    monster_id: str
    atk: float
    defense: float
    hp: float


class MonsterSkillType(str, Enum):
    """
    Enemy skill types referenced by battle_simulator.
    """
    Attack = "Attack"
    Heal = "Heal"
    Buff = "Buff"
    Debuff = "Debuff"
    Guard = "Guard"
    Special = "Special"


@dataclass
class MonsterSkill:
    monster_id: str
    skill_id: str
    skill_type: MonsterSkillType

    # Core numeric params (optional / depends on sheet design)
    multiplier: float = 1.0
    flat_value: float = 0.0

    # Counter-related fields (optional)
    counter_mode: CounterMode = CounterMode.None_
    counter_start_trigger: CounterStartTrigger = CounterStartTrigger.None_
    counter_value: int = 0
    reload_timing: ReloadTiming = ReloadTiming.AfterExecute


@dataclass
class MonsterState:
    """
    Runtime monster state in battle simulation.
    """
    monster_id: str
    hp: float
    alive: bool = True

    # current counter & action pointers (if your sim uses them)
    counter: int = 0
    current_skill_id: Optional[str] = None


# =========================================================
# Ability / Status (used by ability_system)
# =========================================================

class StatusType(str, Enum):
    AttackUp = "AttackUp"
    DefenseUp = "DefenseUp"
    HealingUp = "HealingUp"
    IncomingDamageDown = "IncomingDamageDown"


@dataclass
class StatusInstance:
    status_type: StatusType
    remaining_turns: int
    params: Dict[str, Any] = field(default_factory=dict)
    source_ability_id: Optional[str] = None


# =========================================================
# Battle Result
# =========================================================

@dataclass
class BattleResult:
    battle_index: int
    winner: str
    turns: int
    player_hp_end: float
    enemies_alive: int


# =========================================================
# Utils
# =========================================================

TEnum = TypeVar("TEnum", bound=Enum)


def parse_enum(enum_type: Type[TEnum], raw: Any, default: TEnum) -> TEnum:
    """
    Safe enum parser for Excel / string input.
    """
    if raw is None:
        return default

    if isinstance(raw, enum_type):
        return raw

    s = str(raw).strip()
    if s == "":
        return default

    # by value
    try:
        return enum_type(s)  # type: ignore
    except Exception:
        pass

    # by name
    for e in enum_type:  # type: ignore
        if e.name.lower() == s.lower():
            return e

    return default
