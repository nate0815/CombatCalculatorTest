# models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
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
    # Card side (you already use these)
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
    Damage = "Damage"  # 傷害
    Shield = "Shield"  # 護盾
    Heal = "Heal"      # 治療
    Buff = "Buff"      # 增益 (未實作)
    Debuff = "Debuff"  # 減益 (未實作)


class ScaleStat(str, Enum):
    """
    數值加成的參照屬性
    (例如：造成攻擊力 100% 的傷害)
    """
    ATK = "ATK"       # 攻擊力
    DEF = "DEF"       # 防禦力
    HP = "HP"         # 血量
    None_ = "None"    # 無 (使用 None_ 避免與 Python 關鍵字衝突)


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
    Attack = "Attack"       # 攻擊
    AddShield = "AddShield" # 增加護盾
    Buff = "Buff"           # 增益
    Debuff = "Debuff"       # 減益


class ReloadTiming(str, Enum):
    AfterEnemyAttackPhase = "AfterEnemyAttackPhase"  # 敵方攻擊階段結束後重置計數器 (MVP 預設)


class CounterMode(str, Enum):
    Disabled = "Disabled"
    Enabled = "Enabled"
    Conditional = "Conditional"


class CounterStartTrigger(str, Enum):
    OnPlayerPlayCard = "OnPlayerPlayCard"  # 當玩家打出任意卡牌時觸發
    OnPlayerAttackCard = "OnPlayerAttackCard"
    OnPlayerTurnStart = "OnPlayerTurnStart"


class EnemyPhaseActionRule(str, Enum):
    None_ = "None"
    ActOnce = "ActOnce"
    ActIfNotActedThisTurn = "ActIfNotActedThisTurn"


# =========================================================
# Ability / Condition / Effect System (MVP)
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
# Phase 1 Output (Character Snapshot)
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
    玩家隊伍快照 (MVP: 共用血條)

    你目前的 battle_simulator.py 會用到:
    - team_hp_now
    - team_hp_max / team_hp_max_now
    - team_shield_now (很可能下一步也會用)
    - active_character_id / active_member

    所以這裡提供相容層，避免每次改名就爆炸。
    """
    members: List[CharacterSnapshot]
    active_character_id: str = ""

    # 新版命名
    team_hp_max: float = 0.0
    team_hp: float = 0.0
    team_shield: float = 0.0

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("PlayerPartySnapshot.members cannot be empty")

        self.team_hp_max = float(sum(m.final_hp for m in self.members))
        self.team_hp = float(self.team_hp_max)

        # active id fallback
        if (not self.active_character_id) or (not any(m.character_id == self.active_character_id for m in self.members)):
            self.active_character_id = self.members[0].character_id

    # ---- helpers ----
    @property
    def members_by_id(self) -> Dict[str, CharacterSnapshot]:
        return {m.character_id: m for m in self.members}

    def get_active_member(self) -> CharacterSnapshot:
        return self.members_by_id.get(self.active_character_id, self.members[0])

    @property
    def active_member(self) -> CharacterSnapshot:
        # 일부舊版 simulator 可能用 party.active_member
        return self.get_active_member()

    # ----------------------------
    # Backward-compatible aliases
    # ----------------------------

    @property
    def team_hp_now(self) -> float:
        return float(self.team_hp)

    @team_hp_now.setter
    def team_hp_now(self, v: float) -> None:
        self.team_hp = float(v)

    @property
    def team_hp_max_now(self) -> float:
        return float(self.team_hp_max)

    @team_hp_max_now.setter
    def team_hp_max_now(self, v: float) -> None:
        self.team_hp_max = float(v)

    @property
    def team_shield_now(self) -> float:
        return float(self.team_shield)

    @team_shield_now.setter
    def team_shield_now(self, v: float) -> None:
        self.team_shield = float(v)


# =========================================================
# Card Data (MVP)
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
# Monster Data (MVP)
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
# Runtime State (MVP)
# =========================================================

from typing import Any, Dict, List, Optional  # 確保有 Any

@dataclass(init=False)
class MonsterState:
    """
    怪物戰鬥時的動態狀態 (HP, 護盾, 計數器等)

    同時支援：
    - MonsterState(hp=..., shield=...)
    - MonsterState(hp_now=..., shield_now=...)
    並提供 battle_simulator 需要的 is_dead()
    """
    monster_id: str
    hp: float
    shield: float
    counter: int
    counter_max: int
    has_acted_this_turn: bool

    def __init__(
        self,
        monster_id: str,
        hp: Optional[float] = None,
        shield: float = 0.0,
        counter: int = 0,
        counter_max: int = 0,
        has_acted_this_turn: bool = False,
        # legacy names
        hp_now: Optional[float] = None,
        shield_now: Optional[float] = None
    ) -> None:
        if hp is None and hp_now is None:
            raise TypeError("MonsterState requires hp or hp_now")

        if shield_now is not None:
            shield = float(shield_now)

        self.monster_id = monster_id
        self.hp = float(hp if hp is not None else hp_now)
        self.shield = float(shield)
        self.counter = int(counter)
        self.counter_max = int(counter_max)
        self.has_acted_this_turn = bool(has_acted_this_turn)

    @property
    def hp_now(self) -> float:
        return float(self.hp)

    @hp_now.setter
    def hp_now(self, v: float) -> None:
        self.hp = float(v)

    @property
    def shield_now(self) -> float:
        return float(self.shield)

    @shield_now.setter
    def shield_now(self, v: float) -> None:
        self.shield = float(v)

    def is_dead(self) -> bool:
        return float(self.hp) <= 0.0



from typing import Any, Dict, Optional  # 確保 models.py 有 Any/Dict/Optional

@dataclass(init=False)
class BattleResult:
    """
    戰鬥結果

    battle_simulator 可能會塞入額外欄位（例如 extra），
    這裡做成 forward-compatible，避免每次改 simulator 就爆。
    """
    battle_index: int
    winner: str
    turns: int
    player_hp_end: float
    enemies_alive: int
    extra: Optional[Dict[str, Any]]

    def __init__(
        self,
        battle_index: int,
        winner: str,
        turns: int,
        player_hp_end: float,
        enemies_alive: int,
        extra: Optional[Dict[str, Any]] = None,
        **_ignored: Any,
    ) -> None:
        self.battle_index = int(battle_index)
        self.winner = str(winner)
        self.turns = int(turns)
        self.player_hp_end = float(player_hp_end)
        self.enemies_alive = int(enemies_alive)
        self.extra = extra



# =========================================================
# Utility
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
