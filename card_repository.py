"""
card_repository.py
Phase: Static Card Data (Repository)

Responsibility:
- Load Card.xlsx sheets: Card / CardEffect
- Build in-memory CardDef objects (Card + ordered effects)
- Provide query APIs for calculator / main

Notes:
- FlatValue supports None / empty / "None" -> treated as 0.0
"""

import pandas as pd
from pathlib import Path
from typing import Any, Dict, List, Optional
from models import CardDef, CardEffectDef

# =========================================================
# Path & Loader
# =========================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


def load_sheet(excel_name: str, sheet_name: str) -> pd.DataFrame:
    path = DATA_DIR / excel_name
    if not path.exists():
        raise FileNotFoundError(f"❌ Excel file not found: {path}")
    df = pd.read_excel(path, sheet_name=sheet_name)
    df.columns = df.columns.astype(str).str.strip()
    return df


# =========================================================
# Utils (keep same style as Phase1)
# =========================================================
def clean_id(x: Any) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x).replace("\u00A0", "").replace("\u200b", "").strip()
    if s.lower() in ("nan", "none", ""):
        return ""
    return s


def to_int(x: Any, default: int = 0) -> int:
    try:
        return int(float(x))
    except Exception:
        return default


def to_float(x: Any, default: float = 0.0) -> float:
    # supports "None" / "" / NaN -> default
    if x is None:
        return default
    s = str(x).strip()
    if s == "" or s.lower() in ("none", "nan"):
        return default
    try:
        return float(x)
    except Exception:
        return default


def to_str(x: Any, default: str = "") -> str:
    s = clean_id(x)
    return s if s else default


# =========================================================
# Repository
# =========================================================
class CardRepository:
    """
    Loads Card.xlsx and provides read APIs.

    Expected sheets:
    - Card: CardId, CharacterId, GroupId, EpiphanyTier
    - CardEffect:
        CardId, EffectIndex, EffectType, ScaleStat, Multiplier, FlatValue,
        CardLifecycle, AfterPlayMove, OnEndTurnAction, Target
    """

    def __init__(self, excel_name: str = "Card.xlsx"):
        self.excel_name = excel_name
        self._cards_by_id: Dict[str, CardDef] = {}
        self._cards_by_character: Dict[str, List[CardDef]] = {}
        self._cards_by_group: Dict[str, List[CardDef]] = {}

    def load(self) -> None:
        card_df = load_sheet(self.excel_name, "Card")
        effect_df = load_sheet(self.excel_name, "CardEffect")

        # Parse effects grouped by CardId
        effects_by_card: Dict[str, List[CardEffectDef]] = {}
        for _, row in effect_df.iterrows():
            card_id = clean_id(row.get("CardId"))
            if not card_id:
                continue

            eff = CardEffectDef(
                card_id=card_id,
                effect_index=to_int(row.get("EffectIndex"), 0),
                effect_type=clean_id(row.get("EffectType")),
                scale_stat=clean_id(row.get("ScaleStat")),
                multiplier=to_float(row.get("Multiplier"), 1.0),
                flat_value=to_float(row.get("FlatValue"), 0.0),
                card_lifecycle=to_str(row.get("CardLifecycle"), "Normal"),
                after_play_move=to_str(row.get("AfterPlayMove"), "Discard"),
                on_end_turn_action=to_str(row.get("OnEndTurnAction"), "None"),
                target=to_str(row.get("Target"), "EnemySingle"),
            )
            effects_by_card.setdefault(card_id, []).append(eff)

        # Sort effects by EffectIndex
        for cid in list(effects_by_card.keys()):
            effects_by_card[cid] = sorted(effects_by_card[cid], key=lambda e: e.effect_index)

        # Build CardDef
        self._cards_by_id.clear()
        self._cards_by_character.clear()
        self._cards_by_group.clear()

        for _, row in card_df.iterrows():
            card_id = clean_id(row.get("CardId"))
            if not card_id:
                continue

            character_id = clean_id(row.get("CharacterId"))
            group_id = clean_id(row.get("GroupId"))
            epiphany_tier = to_int(row.get("EpiphanyTier"), 0)

            card = CardDef(
                card_id=card_id,
                character_id=character_id,
                group_id=group_id,
                epiphany_tier=epiphany_tier,
                effects=effects_by_card.get(card_id, []),
            )

            self._cards_by_id[card_id] = card
            if character_id:
                self._cards_by_character.setdefault(character_id, []).append(card)
            if group_id:
                self._cards_by_group.setdefault(group_id, []).append(card)

        # Optional: stable ordering
        for k in list(self._cards_by_character.keys()):
            self._cards_by_character[k] = sorted(self._cards_by_character[k], key=lambda c: c.card_id)
        for k in list(self._cards_by_group.keys()):
            self._cards_by_group[k] = sorted(self._cards_by_group[k], key=lambda c: (c.epiphany_tier, c.card_id))

    # ---------- Query APIs ----------
    def get_card(self, card_id: str) -> Optional[CardDef]:
        return self._cards_by_id.get(card_id)

    def get_cards_by_character(self, character_id: str) -> List[CardDef]:
        return list(self._cards_by_character.get(character_id, []))

    def get_cards_in_group(self, group_id: str) -> List[CardDef]:
        return list(self._cards_by_group.get(group_id, []))
