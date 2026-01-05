from dataclasses import dataclass
from typing import Optional, List, Dict


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
    """
    card_id: str
    effect_index: int
    effect_type: str
    scale_stat: str
    multiplier: float
    flat_value: float


@dataclass(frozen=True)
class CardDef:
    """
    Card basic info + ordered effects.
    Loaded by repository; consumed by calculators.
    """
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


@dataclass(frozen=True)
class CardResult:
    card_id: str
    character_id: str
    epiphany_tier: int
    effects: List[CardEffectResult]
    totals: Dict[str, float]  # e.g. {"Damage": x, "Heal": y, "Shield": z}
