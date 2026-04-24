# models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# =========================================================
# Common Enums (MVP)
# =========================================================

class LogLevel(str, Enum):
    INFO = "INFO"
    DEBUG = "DEBUG"
    TRACE = "TRACE"


class TargetType(str, Enum):
    """
    技能或卡牌的目標類型
    """
    EnemySingle = "EnemySingle"  # 敵方單體
    EnemyAll = "EnemyAll"        # 敵方全體
    Self = "Self"                # 自身
    AllySingle = "AllySingle"    # 我方單體
    AllyAll = "AllyAll"          # 我方全體

    # Monster side (current MVP)
    Player = "Player"            # 玩家 (怪物攻擊目標)


class EffectType(str, Enum):
    """
    卡牌效果類型
    """
    Damage = "Damage"
    Shield = "Shield"
    Heal = "Heal"
    Buff = "Buff"
    Debuff = "Debuff"


class ScaleStat(str, Enum):
    """
    數值加成的參照屬性
    """
    ATK = "ATK"
    DEF = "DEF"
    HP = "HP"
    None_ = "None"


class CardLifecycle(str, Enum):
    Normal = "Normal"
    Exhaust = "Exhaust"
    Ethereal = "Ethereal"


class AfterPlayMove(str, Enum):
    None_ = "None"
    Discard = "Discard"
    Remove = "Remove"


class OnEndTurnAction(str, Enum):
    None_ = "None"
    Remove = "Remove"


# ---- Monster skill system (MVP) ----

class MonsterSkillType(str, Enum):
    Attack = "Attack"
    AddShield = "AddShield"
    Buff = "Buff"
    Debuff = "Debuff"


class ReloadTiming(str, Enum):
    AfterEnemyAttackPhase = "AfterEnemyAttackPhase"


class CounterMode(str, Enum):
    Disabled = "Disabled"
    Enabled = "Enabled"
    Conditional = "Conditional"


class CounterStartTrigger(str, Enum):
    OnPlayerPlayCard = "OnPlayerPlayCard"
    OnPlayerAttackCard = "OnPlayerAttackCard"
    OnPlayerTurnStart = "OnPlayerTurnStart"


class EnemyPhaseActionRule(str, Enum):
    None_ = "None"
    ActOnce = "ActOnce"
    ActIfNotActedThisTurn = "ActIfNotActedThisTurn"


# =========================================================
# Ability / Condition / Effect System (MVP)
# (留著給 ability_system 用；battle_simulator 的 TriggerEvent 來自 ability_models.py)
# =========================================================

class TriggerEvent(str, Enum):
    BattleStart = "BattleStart"
    FirstTurnStart = "FirstTurnStart"
    TurnStart = "TurnStart"
    TurnEnd = "TurnEnd"
    OnPlayerPlayCard = "OnPlayerPlayCard"


class ConditionLogic(str, Enum):
    AND = "AND"
    OR = "OR"


class ConditionType(str, Enum):
    OwnerClassEqualsPartnerClass = "OwnerClassEqualsPartnerClass"


class ExecMode(str, Enum):
    Sequential = "Sequential"


class ValueRefType(str, Enum):
    None_ = "None"
    PartnerStack = "PartnerStack"


class AbilityEffectType(str, Enum):
    AddStatus = "AddStatus"
    SetStatusParam = "SetStatusParam"


class StatusType(str, Enum):
    AttackUp = "AttackUp"


class StatusParamKey(str, Enum):
    increase = "increase"


@dataclass
class AbilityDef:
    ability_id: str
    trigger_event: TriggerEvent
    condition_group_id: Optional[str]
    effect_group_id: str
    priority: int = 0
    note: str = ""


@dataclass
class ConditionGroupDef:
    condition_group_id: str
    logic: ConditionLogic = ConditionLogic.AND


@dataclass
class ConditionRowDef:
    condition_group_id: str
    condition_type: ConditionType
    value1: Optional[str] = None
    value2: Optional[str] = None


@dataclass
class EffectGroupDef:
    effect_group_id: str
    exec_mode: ExecMode = ExecMode.Sequential


@dataclass
class EffectRowDef:
    effect_group_id: str
    effect_type: AbilityEffectType
    value1: str = ""
    value2: float = 0.0
    value_ref_type: ValueRefType = ValueRefType.None_
    value_ref_id: Optional[str] = None


@dataclass
class StatusInstance:
    status_type: StatusType
    remaining_turns: int = 0
    params: Dict[str, float] = field(default_factory=dict)
    source_ability_id: str = ""


@dataclass
class PartyRuntimeState:
    statuses: List[StatusInstance] = field(default_factory=list)
    partner_stack_count: int = 0

    def get_damage_multiplier(self) -> float:
        mul = 1.0
        for s in self.statuses:
            if s.status_type == StatusType.AttackUp:
                inc = float(s.params.get(StatusParamKey.increase.value, 0.0))
                mul *= (1.0 + inc)
        return mul

    def tick_turn_end(self) -> None:
        alive: List[StatusInstance] = []
        for s in self.statuses:
            if s.remaining_turns > 0:
                s.remaining_turns -= 1
            if s.remaining_turns != 0:
                alive.append(s)
        self.statuses = alive


# =========================================================
# Phase 1 Output
# =========================================================

@dataclass
class CharacterSnapshot:
    character_id: str
    final_atk: float
    final_def: float
    final_hp: float
    level: Optional[float] = None
    affection_level: Optional[int] = None


# =========================================================
# Player Party (MVP: shared HP bar)
# =========================================================

@dataclass
class PlayerPartySnapshot:
    """
    battle_simulator 會使用：
    - team_hp_max
    - team_hp_now
    - members
    """
    members: List[CharacterSnapshot]
    active_character_id: str = ""

    team_hp_max: float = 0.0
    team_hp: float = 0.0
    team_shield: float = 0.0

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("PlayerPartySnapshot.members cannot be empty")

        self.team_hp_max = float(sum(m.final_hp for m in self.members))
        self.team_hp = float(self.team_hp_max)

        if (not self.active_character_id) or (not any(m.character_id == self.active_character_id for m in self.members)):
            self.active_character_id = self.members[0].character_id

    def get_active_member(self) -> CharacterSnapshot:
        for m in self.members:
            if m.character_id == self.active_character_id:
                return m
        return self.members[0]

    @property
    def team_hp_now(self) -> float:
        return float(self.team_hp)

    @team_hp_now.setter
    def team_hp_now(self, v: float) -> None:
        self.team_hp = float(v)

    @property
    def team_shield_now(self) -> float:
        return float(self.team_shield)

    @team_shield_now.setter
    def team_shield_now(self, v: float) -> None:
        self.team_shield = float(v)


# =========================================================
# Card Data
# =========================================================

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
    multiplier: float = 0.0
    flat_value: float = 0.0

    card_lifecycle: CardLifecycle = CardLifecycle.Normal
    after_play_move: AfterPlayMove = AfterPlayMove.Discard
    on_end_turn_action: OnEndTurnAction = OnEndTurnAction.None_
    target: TargetType = TargetType.EnemySingle

    duration_turn: int = 0
    stackable: bool = False
    max_stack: int = 0
    condition: Optional[str] = None


# =========================================================
# Monster Data
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


@dataclass
class MonsterSkill:
    skill_id: str
    monster_id: str
    skill_type: MonsterSkillType
    value: float

    counter_max: int
    reload_timing: ReloadTiming
    counter_mode: CounterMode
    counter_start_trigger: CounterStartTrigger
    enemy_phase_action_rule: EnemyPhaseActionRule
    target: TargetType


# =========================================================
# Runtime State (battle_simulator 依賴這裡的命名)
# =========================================================

@dataclass
class MonsterState:
    """
    battle_simulator 會用：
    - hp_now
    - acted_this_turn
    - is_dead()
    """
    monster_id: str
    hp_now: float
    shield: float = 0.0

    counter: int = 0
    counter_max: int = 0

    acted_this_turn: bool = False

    def is_dead(self) -> bool:
        return float(self.hp_now) <= 0.0

    # ---- backward compat aliases ----
    @property
    def hp(self) -> float:
        return float(self.hp_now)

    @hp.setter
    def hp(self, v: float) -> None:
        self.hp_now = float(v)

    @property
    def has_acted_this_turn(self) -> bool:
        return bool(self.acted_this_turn)

    @has_acted_this_turn.setter
    def has_acted_this_turn(self, v: bool) -> None:
        self.acted_this_turn = bool(v)


# =========================================================
# Battle Result (battle_simulator 會塞 extra)
# =========================================================

@dataclass
class BattleResult:
    battle_index: int
    winner: str
    turns: int
    player_hp_end: float
    enemies_alive: int
    extra: Dict[str, Any] = field(default_factory=dict)


# =========================================================
# Utility: simple enum parsing helper
# =========================================================

def parse_enum(enum_cls: Enum, value: str, default):
    if value is None:
        return default
    v = str(value).strip()
    if v == "":
        return default
    try:
        return enum_cls(v)
    except Exception:
        return default
