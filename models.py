# models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

# =========================================================
# Common Enums (MVP)
# =========================================================
class LogLevel(str, Enum):
    INFO = "INFO"
    DEBUG = "DEBUG"
    TRACE = "TRACE"


class TargetType(str, Enum):
    """ 技能或卡牌的目標類型 """
    # Card side (you already use these)
    EnemySingle = "EnemySingle"  # 敵方單體
    EnemyAll = "EnemyAll"        # 敵方全體
    Self = "Self"                # 自身
    AllySingle = "AllySingle"    # 我方單體
    AllyAll = "AllyAll"          # 我方全體

    # Monster side (current MVP)
    Player = "Player"            # 玩家 (怪物攻擊目標)


class EffectType(str, Enum):
    """ 卡牌效果類型 """
    Damage = "Damage"    # 傷害
    Shield = "Shield"    # 護盾
    Heal = "Heal"        # 治療
    Buff = "Buff"        # 增益 (未實作)
    Debuff = "Debuff"    # 減益 (未實作)


class ScaleStat(str, Enum):
    """ 數值加成的參照屬性 (例如：造成攻擊力 100% 的傷害) """
    ATK = "ATK"      # 攻擊力
    DEF = "DEF"      # 防禦力
    HP = "HP"        # 血量
    None_ = "None"   # 無 (使用 None_ 避免與 Python 關鍵字衝突)


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
    Attack = "Attack"      # 攻擊
    AddShield = "AddShield"  # 增加護盾
    Buff = "Buff"          # 增益
    Debuff = "Debuff"      # 減益


class ReloadTiming(str, Enum):
    # You have unified to this in sheet
    AfterEnemyAttackPhase = "AfterEnemyAttackPhase"  # 敵方攻擊階段結束後重置計數器 (MVP 預設)


class CounterMode(str, Enum):
    Disabled = "Disabled"      # 停用
    Enabled = "Enabled"        # 啟用
    Conditional = "Conditional"  # 條件式


class CounterStartTrigger(str, Enum):
    # Your updated requirement: any card played (even non-attack) reduces counter
    OnPlayerPlayCard = "OnPlayerPlayCard"  # 當玩家打出任意卡牌時觸發

    # (reserved / future)
    OnPlayerAttackCard = "OnPlayerAttackCard"
    OnPlayerTurnStart = "OnPlayerTurnStart"


class EnemyPhaseActionRule(str, Enum):
    None_ = "None"
    ActOnce = "ActOnce"  # 每回合行動一次
    ActIfNotActedThisTurn = "ActIfNotActedThisTurn"  # 若本回合尚未行動則行動 (補刀/補行動)

# =========================================================
# Ability / Condition / Effect System (MVP)
# =========================================================

class TriggerEvent(str, Enum):
    """能力觸發事件 (MVP 先支援到夥伴道格拉斯需求)"""
    BattleStart = "BattleStart"
    FirstTurnStart = "FirstTurnStart"
    TurnStart = "TurnStart"
    TurnEnd = "TurnEnd"
    OnPlayerPlayCard = "OnPlayerPlayCard"


class ConditionLogic(str, Enum):
    AND = "AND"
    OR = "OR"


class ConditionType(str, Enum):
    """條件種類 (MVP 只做職業相符)"""
    OwnerClassEqualsPartnerClass = "OwnerClassEqualsPartnerClass"


class ExecMode(str, Enum):
    """EffectGroup 的執行模式"""
    Sequential = "Sequential"
    # future: RandomOne, Parallel, etc.


class ValueRefType(str, Enum):
    """EffectRow 的動態數值來源"""
    None_ = "None"
    PartnerStack = "PartnerStack"


class AbilityEffectType(str, Enum):
    """Ability 系統的效果類型 (避免與 Card EffectType 命名衝突)"""
    AddStatus = "AddStatus"
    SetStatusParam = "SetStatusParam"


class StatusType(str, Enum):
    """Runtime 狀態種類 (MVP 只做 AttackUp)"""
    AttackUp = "AttackUp"


class StatusParamKey(str, Enum):
    """Status 參數 key (例如 AttackUp.increase)"""
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
    # reserved for future params
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
    value1: str = ""           # e.g., "AttackUp" / "increase"
    value2: float = 0.0        # e.g., duration (for AddStatus) or numeric fallback
    value_ref_type: ValueRefType = ValueRefType.None_
    value_ref_id: Optional[str] = None  # e.g., PartnerAttackIncrease


@dataclass
class StatusInstance:
    """戰鬥中的短期狀態 (buff/debuff)"""
    status_type: StatusType
    remaining_turns: int = 0
    params: Dict[str, float] = field(default_factory=dict)
    source_ability_id: str = ""


@dataclass
class PartyRuntimeState:
    """玩家隊伍 runtime 狀態 (MVP: 只放 buff 與一些輸入參數)"""
    statuses: List[StatusInstance] = field(default_factory=list)

    # Input-driven params (from CombatInputPanel)
    partner_stack_count: int = 0

    def get_damage_multiplier(self) -> float:
        """用於套用『造成傷害量』加成。"""
        mul = 1.0
        for s in self.statuses:
            if s.status_type == StatusType.AttackUp:
                inc = float(s.params.get(StatusParamKey.increase.value, 0.0))
                mul *= (1.0 + inc)
        return mul

    def tick_turn_end(self) -> None:
        """回合結束：扣掉 duration，清除到期狀態"""
        alive: List[StatusInstance] = []
        for s in self.statuses:
            if s.remaining_turns > 0:
                s.remaining_turns -= 1
            if s.remaining_turns != 0:
                # remaining_turns == 0 代表到期 (MVP)
                alive.append(s)
        self.statuses = alive

# =========================================================
# Phase 1 Output (Character Snapshot)
# =========================================================
@dataclass
class CharacterSnapshot:
    """
    Result of Phase 1: Character Static Calculation

    角色靜態數值快照 (Phase 1 計算結果)

    這是一個凍結的角色最終基礎數值視圖 (ATK/DEF/HP)。
    """
    character_id: str
    final_atk: float
    final_def: float
    final_hp: float

    # Optional metadata
    # 選用元資料
    level: Optional[float] = None
    affection_level: Optional[int] = None


# =========================================================
# Player Party (MVP: shared HP bar)
# =========================================================
@dataclass
class PlayerPartySnapshot:
    """
    玩家隊伍快照 (MVP: 共用血條)

    MVP 規則:
    - 隊伍血量共用 (單一血條) = 成員血量總和。
    - 受到傷害時扣除 team_hp。
    - 護盾為全隊共用 (單一護盾池)。
    - 卡牌倍率計算時使用的 ATK/DEF 來自當前活動角色 (active_character)。
    """
    members: List[CharacterSnapshot]
    active_character_id: str

    team_hp_max: float = 0.0
    team_hp: float = 0.0
    team_shield: float = 0.0

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("PlayerPartySnapshot.members cannot be empty")

        self.team_hp_max = float(sum(m.final_hp for m in self.members))
        self.team_hp = float(self.team_hp_max)

        if not any(m.character_id == self.active_character_id for m in self.members):
            # fallback to first member
            self.active_character_id = self.members[0].character_id

    def get_active_member(self) -> CharacterSnapshot:
        for m in self.members:
            if m.character_id == self.active_character_id:
                return m
        return self.members[0]


# =========================================================
# Card Data (MVP)
# =========================================================
@dataclass
class Card:
    card_id: str
    character_id: str
    group_id: str
    epiphany_tier: int = 0

    # NEW: AP cost
    # 新增: AP 消耗 (預設為 1)
    ap_cost: int = 1


@dataclass
class CardEffect:
    """ 卡牌效果定義 """
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

    # reserved / future
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
    """ 怪物技能定義 """
    skill_id: str
    monster_id: str
    skill_type: MonsterSkillType
    value: float  # 技能數值 (傷害值或護盾值)
    counter_max: int  # 最大計數 (CD)
    reload_timing: ReloadTiming  # 重置時機
    counter_mode: CounterMode  # 計數器模式
    counter_start_trigger: CounterStartTrigger  # 計數器觸發條件
    enemy_phase_action_rule: EnemyPhaseActionRule  # 敵方階段行動規則
    target: TargetType  # 技能目標


# =========================================================
# Runtime State (MVP)
# =========================================================
@dataclass
class MonsterState:
    """ 怪物戰鬥時的動態狀態 (HP, 護盾, 計數器等) """
    monster_id: str
    hp: float
    shield: float = 0.0
    counter: int = 0        # 當前計數
    counter_max: int = 0    # 最大計數 (用於重置)

    # for EnemyPhaseActionRule = ActIfNotActedThisTurn
    has_acted_this_turn: bool = False  # 本回合是否已行動標記


@dataclass
class BattleResult:
    battle_index: int
    winner: str  # "Player" or "Enemy"
    turns: int
    player_hp_end: float
    enemies_alive: int


# =========================================================
# Utility: simple enum parsing helper
# =========================================================
def parse_enum(enum_cls: Enum, value: str, default):
    """ Safe enum parse for sheet strings.

    - enum_cls: Enum class
    - value: sheet string
    - default: default enum value if parsing fails
    """
    if value is None:
        return default
    v = str(value).strip()
    if v == "":
        return default
    try:
        return enum_cls(v)
    except Exception:
        return default
