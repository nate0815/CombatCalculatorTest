# models.py
from dataclasses import dataclass
from typing import Optional, List


# =========================================================
# Phase 1 Output
# Character Static Snapshot
# =========================================================

@dataclass
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