# card_repository.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from models import (
    AfterPlayMove,
    Card,
    CardEffect,
    CardLifecycle,
    EffectType,
    LogLevel,
    OnEndTurnAction,
    ScaleStat,
    TargetType,
    parse_enum,
)


@dataclass
class CardRepository:
    """
    Load Card / CardEffect from Excel.
    負責從 Excel 載入卡牌與效果資料。
    Supports:
    - Party card pool: load_cards_for_characters(["Yuki","Cassius","Mika"])
    - NEW: ApCost (int). Default to 1 if missing/blank.
    """
    data_dir: Path
    log_level: LogLevel = LogLevel.INFO

    _cards: Dict[str, Card] = None
    _effects_by_card: Dict[str, List[CardEffect]] = None

    def __post_init__(self) -> None:
        self._cards = {}
        self._effects_by_card = {}

    # -----------------------------------------------------
    # Public API
    # -----------------------------------------------------

    def load_cards_for_characters(
        self,
        excel_name: str,
        sheet_card: str,
        sheet_effect: str,
        character_ids: List[str],
    ) -> Tuple[List[Card], Dict[str, List[CardEffect]]]:
        """
        根據角色 ID 列表載入對應的卡牌與效果。
        Load cards filtered by character_ids, and all their effects.
        Returns:
            cards(list), effects_by_card(dict)
        """
        card_df = self._load_sheet(excel_name, sheet_card)
        effect_df = self._load_sheet(excel_name, sheet_effect)

        cards = self._parse_cards(card_df, character_ids)
        effects_by_card = self._parse_effects(effect_df, set(c.card_id for c in cards))

        # cache
        self._cards = {c.card_id: c for c in cards}
        self._effects_by_card = effects_by_card

        self._log_info(
            f"[Card] Loaded {len(cards)} cards for party: {', '.join(character_ids)}"
        )
        return cards, effects_by_card

    def get_card(self, card_id: str) -> Optional[Card]:
        return self._cards.get(card_id)

    def get_effects(self, card_id: str) -> List[CardEffect]:
        return self._effects_by_card.get(card_id, [])

    # -----------------------------------------------------
    # Internal: Loaders
    # -----------------------------------------------------

    def _load_sheet(self, excel_name: str, sheet_name: str) -> pd.DataFrame:
        path = self.data_dir / excel_name
        if not path.exists():
            raise FileNotFoundError(f"❌ Excel file not found: {path}")

        try:
            df = pd.read_excel(path, sheet_name=sheet_name)
        except ValueError:
            raise ValueError(f"❌ Sheet '{sheet_name}' not found in {excel_name}")

        df.columns = df.columns.astype(str).str.strip()
        return df

    # -----------------------------------------------------
    # Internal: Parsers
    # -----------------------------------------------------

    def _parse_cards(self, df: pd.DataFrame, character_ids: List[str]) -> List[Card]:
        required = ["CardId", "CharacterId", "GroupId", "EpiphanyTier"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"❌ Card sheet missing column: {col}")

        # NEW: ApCost is optional (default 1)
        has_ap_cost = "ApCost" in df.columns

        # Filter by party characters
        df2 = df[df["CharacterId"].astype(str).isin(character_ids)].copy()

        cards: List[Card] = []
        for _, row in df2.iterrows():
            card_id = str(row["CardId"]).strip()
            char_id = str(row["CharacterId"]).strip()
            group_id = str(row["GroupId"]).strip()
            epi = int(row["EpiphanyTier"]) if not pd.isna(row["EpiphanyTier"]) else 0

            ap_cost = 1
            if has_ap_cost:
                v = row.get("ApCost", 1)
                if pd.isna(v):
                    ap_cost = 1
                else:
                    try:
                        ap_cost = int(v)
                    except Exception:
                        ap_cost = 1

            cards.append(
                Card(
                    card_id=card_id,
                    character_id=char_id,
                    group_id=group_id,
                    epiphany_tier=epi,
                    ap_cost=ap_cost,
                )
            )

        return cards

    def _parse_effects(
        self, df: pd.DataFrame, allowed_card_ids: set
    ) -> Dict[str, List[CardEffect]]:
        required = [
            "CardId",
            "EffectIndex",
            "EffectType",
            "ScaleStat",
            "Multiplier",
            "FlatValue",
            "CardLifecycle",
            "AfterPlayMove",
            "OnEndTurnAction",
            "Target",
        ]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"❌ CardEffect sheet missing column: {col}")

        effects_by_card: Dict[str, List[CardEffect]] = {}

        df2 = df[df["CardId"].astype(str).isin(allowed_card_ids)].copy()

        for _, row in df2.iterrows():
            card_id = str(row["CardId"]).strip()
            idx = int(row["EffectIndex"]) if not pd.isna(row["EffectIndex"]) else 0

            effect_type = parse_enum(
                EffectType, row.get("EffectType", ""), EffectType.Damage
            )
            scale_stat = parse_enum(
                ScaleStat, row.get("ScaleStat", ""), ScaleStat.None_
            )

            mult = row.get("Multiplier", 0.0)
            flat = row.get("FlatValue", 0.0)

            multiplier = float(mult) if not pd.isna(mult) else 0.0
            flat_value = float(flat) if not pd.isna(flat) else 0.0

            lifecycle = parse_enum(
                CardLifecycle, row.get("CardLifecycle", ""), CardLifecycle.Normal
            )
            after_play = parse_enum(
                AfterPlayMove, row.get("AfterPlayMove", ""), AfterPlayMove.Discard
            )
            on_end = parse_enum(
                OnEndTurnAction, row.get("OnEndTurnAction", ""), OnEndTurnAction.None_
            )
            target = parse_enum(TargetType, row.get("Target", ""), TargetType.EnemySingle)

            effects_by_card.setdefault(card_id, []).append(
                CardEffect(
                    card_id=card_id,
                    effect_index=idx,
                    effect_type=effect_type,
                    scale_stat=scale_stat,
                    multiplier=multiplier,
                    flat_value=flat_value,
                    card_lifecycle=lifecycle,
                    after_play_move=after_play,
                    on_end_turn_action=on_end,
                    target=target,
                )
            )

        # Ensure ordering by EffectIndex
        for cid in effects_by_card:
            effects_by_card[cid].sort(key=lambda e: e.effect_index)

        return effects_by_card

    # -----------------------------------------------------
    # Internal: Logging
    # -----------------------------------------------------

    def _log_info(self, msg: str) -> None:
        if self.log_level in (LogLevel.INFO, LogLevel.DEBUG, LogLevel.TRACE):
            print(msg)
