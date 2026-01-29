# models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar


# =========================================================
# Helpers
# =========================================================
TEnum = TypeVar("TEnum", bound=Enum)


def parse_enum(enum_cls: Type[TEnum], raw: Any, default: TEnum) -> TEnum:
    """
    Tolerant enum parser:
    - Accept Enum instance
    - Accept exact value match
    - Accept name match (case-insensitive)
    - Accept string with whitespace
    """
    if raw is None:
        return default
    if isinstance(raw, enum_cls):
        return raw

    s = str(raw).strip()
    if s == "":
        return default

    # 1) match by value
    for e in enum_cls:
        try:
            if str(e.value) == s:
                return e
        except Exception:
            pass

    # 2) match by name (case-insensitive)
    s_upper = s.upper()
    for e in enum_cls:
        if e.name.upper() == s_upper:
            return e

    return default


# =========================================================
# Logging
# =========================================================
class LogLevel(str, Enum):
    INFO = "INFO"
    DEBUG = "DEBUG"
    TRACE = "TRACE"


# =========================================================
# Phase 1 Output - Character Snapshot
# =========================================================
@dataclass
class CharacterSnapshot:
    """
    Phase 1 output (static snapshot): final base stats after level / affection etc.
    """
    character_id: str
    final_atk: float
    final_def: float
    final_hp: float
    level: Optional[float] = None


@dataclass
class PlayerPartySnapshot:
    """
    Party shares ONE HP bar + ONE shield pool (MVP).
    team_hp_max = sum(member.final_hp)
    team_hp starts at team_hp_max unless specified otherwise.
    """
    members: List[CharacterSnapshot]
    active_character_id: str

    team_hp_max: float = 0.0
    team_hp: float = 0.0
    team_shield: float = 0.0

    def __post_init__(self) -> None:
        if self.team_hp_max <= 0:
            self.team_hp_max = float(sum(m.final_hp for m in self.members))
        if self.team_hp <= 0:
            self.team_hp = float(self.team_hp_max)

    def get_active_member(self) -> CharacterSnapshot:
        for m in self.members:
            if m.character_id == self.active_character_id:
                return m
        # fallback
        return self.members[0]


# =========================================================
# Card
# =========================================================
class EffectType(str, Enum):
    Damage = "Damage"
    Shield = "Shield"
    Heal = "Heal"


class ScaleStat(str, Enum):
    None_ = "None"
    ATK = "ATK"
    DEF = "DEF"
    HP = "HP"


class TargetType(str, Enum):
    # Player side targets
    Player = "Player"
    Self = "Self"

    # Enemy side targets
    EnemySingle = "EnemySingle"
    EnemyAll = "EnemyAll"


class CardLifecycle(str, Enum):
    Normal = "Normal"
    Exhaust = "Exhaust"
    Vanish = "Vanish"


class AfterPlayMove(str, Enum):
    Discard = "Discard"
    PutBackToDrawTop = "PutBackToDrawTop"
    PutBackToDrawBottom = "PutBackToDrawBottom"


class OnEndTurnAction(str, Enum):
    Discard = "Discard"
    KeepInHand = "KeepInHand"


@dataclass
class Card:
    card_id: str
    ap_cost: int = 1

    # Optional metadata (tolerant for your repository)
    group_id: Optional[str] = None
    epiphany_tier: Optional[int] = None
    lifecycle: CardLifecycle = CardLifecycle.Normal
    after_play_move: AfterPlayMove = AfterPlayMove.Discard
    on_end_turn_action: OnEndTurnAction = OnEndTurnAction.Discard


@dataclass
class CardEffect:
    card_id: str
    effect_index: int

    effect_type: EffectType
    target: TargetType = TargetType.EnemySingle

    scale_stat: ScaleStat = ScaleStat.None_
    multiplier: float = 0.0
    flat_value: float = 0.0

    # Optional fields (future-proof / compatible)
    note: Optional[str] = None


# =========================================================
# Monster
# =========================================================
@dataclass
class MonsterIndex:
    monster_id: str
    monster_rank: str
    monster_weight: int = 1


@dataclass
class MonsterBaseStat:
    monster_id: str
    level: int
    attack: float
    defense: float
    health: float


class MonsterSkillType(str, Enum):
    Attack = "Attack"
    AddShield = "AddShield"


class ReloadTiming(str, Enum):
    AfterEnemyAttackPhase = "AfterEnemyAttackPhase"


class CounterMode(str, Enum):
    Enabled = "Enabled"
    Disabled = "Disabled"


class CounterStartTrigger(str, Enum):
    OnPlayerPlayCard = "OnPlayerPlayCard"


class EnemyPhaseActionRule(str, Enum):
    ActIfNotActedThisTurn = "ActIfNotActedThisTurn"
    AlwaysAct = "AlwaysAct"


@dataclass
class MonsterSkill:
    skill_id: str
    monster_id: str
    skill_type: MonsterSkillType
    value: float

    counter_max: int = 0
    reload_timing: ReloadTiming = ReloadTiming.AfterEnemyAttackPhase
    counter_mode: CounterMode = CounterMode.Enabled
    counter_start_trigger: CounterStartTrigger = CounterStartTrigger.OnPlayerPlayCard
    enemy_phase_action_rule: EnemyPhaseActionRule = EnemyPhaseActionRule.ActIfNotActedThisTurn
    target: TargetType = TargetType.Player


@dataclass
class MonsterState:
    monster_id: str
    hp: float
    shield: float = 0.0

    counter: int = 0
    counter_max: int = 0
    has_acted_this_turn: bool = False


# =========================================================
# Battle Output
# =========================================================
@dataclass
class BattleResult:
    battle_index: int
    winner: str
    turns: int
    player_hp_end: float
    enemies_alive: int
