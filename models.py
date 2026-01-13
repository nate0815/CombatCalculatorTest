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
    數值加成的參照屬性 (例如：造成攻擊力 100% 的傷害)
    """
    ATK = "ATK"
    DEF = "DEF"
    HP = "HP"
    None_ = "None"   # use None_ to avoid python keyword conflicts


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
    # You have unified to this in sheet
    AfterEnemyAttackPhase = "AfterEnemyAttackPhase" # 敵方攻擊階段結束後重置計數器


class CounterMode(str, Enum):
    Disabled = "Disabled"       # 停用
    Enabled = "Enabled"         # 啟用
    Conditional = "Conditional" # 條件式


class CounterStartTrigger(str, Enum):
    # Your updated requirement: any card played (even non-attack) reduces counter
    OnPlayerPlayCard = "OnPlayerPlayCard" # 當玩家打出任意卡牌時觸發

    # (reserved / future)
    OnPlayerAttackCard = "OnPlayerAttackCard"
    OnPlayerTurnStart = "OnPlayerTurnStart"


class EnemyPhaseActionRule(str, Enum):
    None_ = "None"
    ActOnce = "ActOnce"                             # 每回合行動一次
    ActIfNotActedThisTurn = "ActIfNotActedThisTurn" # 若本回合尚未行動則行動 (補刀/補行動)


# =========================================================
# Phase 1 Output (Character Snapshot)
# =========================================================

@dataclass
class CharacterSnapshot:
    """
    Result of Phase 1: Character Static Calculation
    角色靜態數值快照 (Phase 1 計算結果)
    This is a frozen view of a character final base stats (ATK/DEF/HP).
    """
    character_id: str
    final_atk: float
    final_def: float
    final_hp: float

    # Optional metadata
    level: Optional[float] = None
    affection_level: Optional[int] = None


# =========================================================
# Player Party (MVP: shared HP bar)
# =========================================================

@dataclass
class PlayerPartySnapshot:
    """
    玩家隊伍快照 (MVP: 共用血條)
    MVP rule:
    - Team HP is shared (single HP bar) = sum of members' HP.
    - Damage taken reduces team_hp.
    - Shield is team-wide (single shield pool).
    - ATK/DEF used for card scaling comes from active_character.
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
    ap_cost: int = 1


@dataclass
class CardEffect:
    """
    卡牌效果定義
    """
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
    """
    怪物技能定義
    """
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

@dataclass
class MonsterState:
    """
    怪物戰鬥時的動態狀態 (HP, 護盾, 計數器等)
    """
    monster_id: str

    hp: float
    shield: float = 0.0

    counter: int = 0
    counter_max: int = 0

    # for EnemyPhaseActionRule = ActIfNotActedThisTurn
    has_acted_this_turn: bool = False


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
    """
    Safe enum parse for sheet strings.
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
