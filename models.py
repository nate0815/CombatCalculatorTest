from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum


# =========================================================
# Phase 1 Output
# Character Static Snapshot
# =========================================================

@dataclass(frozen=True)
class CharacterSnapshot:
    """
    Result of Phase 1: Character Static Calculation

    This object represents a 'frozen' view of a character's
    final base stats after applying level, equipment, potential,
    affection, etc.

    Phase 2 (Card Calculation) should ONLY depend on this object,
    and must NOT know how these values were calculated.
    """
    character_id: str
    final_atk: float
    final_def: float
    final_hp: float

    # Optional metadata (not used in calculation, for debugging / trace)
    level: Optional[float] = None
    potential_tier: Optional[int] = None
    affection_level: Optional[int] = None


# =========================================================
# Common Enums (MVP)
# =========================================================

class LogLevel(str, Enum):
    INFO = "INFO"
    DEBUG = "DEBUG"
    TRACE = "TRACE"


class TargetType(str, Enum):
    # Card side (you already use these)
    EnemySingle = "EnemySingle"
    EnemyAll = "EnemyAll"
    Self = "Self"
    AllySingle = "AllySingle"
    AllyAll = "AllyAll"

    # Monster side (you already use these)
    Player = "Player"


class CounterMode(str, Enum):
    Enabled = "Enabled"
    Disabled = "Disabled"
    Conditional = "Conditional"


class CounterStartTrigger(str, Enum):
    None_ = "None"
    OnPlayerPlayCard = "OnPlayerPlayCard"
    OnDamaged = "OnDamaged"
    OnBattleStart = "OnBattleStart"


class EnemyPhaseActionRule(str, Enum):
    None_ = "None"
    ActIfNotActedThisTurn = "ActIfNotActedThisTurn"
    ActOnce = "ActOnce"


class ReloadTiming(str, Enum):
    AfterEnemyAttackPhase = "AfterEnemyAttackPhase"
    Immediate = "Immediate"


# =========================================================
# Phase 2 Data Models
# Card Definitions (loaded from Excel)
# =========================================================

@dataclass(frozen=True)
class CardEffectDef:
    """
    One effect row in CardEffect sheet.

    MVP supports:
    - EffectType: Damage / Shield / Heal
    - ScaleStat: ATK / DEF / HP
    - Multiplier: float (1.0 = 100%)
    - FlatValue: optional (None/blank -> treated as 0.0 in parser)

    Extra columns (for battle simulation MVP):
    - CardLifecycle: Normal / Exhaust / Ethereal (optional)
    - AfterPlayMove: Discard / None / Remove (optional)
    - OnEndTurnAction: None / Remove (optional)
    - Target: EnemySingle / EnemyAll / Self ...
    """
    card_id: str
    effect_index: int
    effect_type: str
    scale_stat: str
    multiplier: float
    flat_value: float

    card_lifecycle: str = "Normal"
    after_play_move: str = "Discard"
    on_end_turn_action: str = "None"
    target: str = "EnemySingle"


@dataclass(frozen=True)
class CardDef:
    """Card basic info + ordered effects. Loaded by repository; consumed by calculators."""
    card_id: str
    character_id: str
    group_id: str
    epiphany_tier: int
    effects: List[CardEffectDef]


# =========================================================
# Phase 2 Output Models
# Card Calculation Results (derived data)
# =========================================================

@dataclass(frozen=True)
class CardEffectResult:
    effect_index: int
    effect_type: str
    scale_stat: str
    base_stat: float
    multiplier: float
    flat_value: float
    value: float

    # pass-through (debug / battle usage)
    card_lifecycle: str
    after_play_move: str
    on_end_turn_action: str
    target: str


@dataclass(frozen=True)
class CardResult:
    card_id: str
    character_id: str
    epiphany_tier: int
    effects: List[CardEffectResult]
    totals: Dict[str, float]  # e.g. {"Damage": x, "Heal": y, "Shield": z}


# =========================================================
# Monster Data Models (loaded from Excel)
# =========================================================

@dataclass(frozen=True)
class MonsterBaseStat:
    monster_id: str
    level: int
    attack: float
    defense: float
    health: float


@dataclass(frozen=True)
class MonsterSkillDef:
    skill_id: str
    monster_id: str
    skill_type: str   # Attack / AddShield / Buff / Debuff (MVP uses Attack/AddShield)
    value: float

    counter_max: int
    reload_timing: str
    counter_mode: str
    counter_start_trigger: str
    enemy_phase_action_rule: str
    target: str


@dataclass(frozen=True)
class MonsterDef:
    monster_id: str
    monster_rank: str
    monster_weight: int
    base_stat: MonsterBaseStat
    skills: List[MonsterSkillDef]


# =========================================================
# Battle Runtime Models (MVP)
# =========================================================

@dataclass
class PlayerState:
    character_id: str
    max_hp: float
    hp: float
    atk: float
    defense: float
    shield: float = 0.0


@dataclass
class MonsterState:
    monster_id: str
    max_hp: float
    hp: float
    atk: float
    defense: float
    shield: float = 0.0

    counter: int = 0
    counter_max: int = 0
    has_acted_this_turn: bool = False

    # A monster can have multiple skills; MVP uses a simple "active skill index"
    active_skill_index: int = 0


@dataclass(frozen=True)
class BattleConfig:
    log_level: LogLevel = LogLevel.INFO
    max_turns: int = 999  # safety guard


@dataclass(frozen=True)
class BattleResult:
    battle_index: int
    turns: int
    winner: str  # "Player" or "Enemy"
    player_hp_end: float
    enemies_alive: int
