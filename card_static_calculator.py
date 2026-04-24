# card_static_calculator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from models import (
    Card,
    CardEffect,
    CharacterSnapshot,
    EffectType,
    PlayerPartySnapshot,
    ScaleStat,
)


@dataclass
class CardEffectResult:
    """
    A lightweight, structured result of applying ONE card effect.
    單一卡牌效果的計算結果 (數值預覽)。

    Note:
    - In current MVP, battle_simulator.py applies effects directly for speed.
    - This module remains useful for future refactor (clean architecture):
      BattleSimulator -> CardStaticCalculator -> returns results -> apply to state / report.
    """
    card_id: str
    effect_index: int
    effect_type: EffectType
    target: str
    value: float


class CardStaticCalculator:
    """
    Card static effect calculator (MVP).
    卡牌靜態數值計算器。

    Responsibilities:
    - Convert (CardEffect + ActiveCharacterSnapshot + PartySnapshot) into numeric value.
    - Does NOT mutate battle state.
    """

    def compute_effect_value(
        self,
        party: PlayerPartySnapshot,
        active_member: CharacterSnapshot,
        effect: CardEffect,
    ) -> float:
        """
        計算效果數值:
            value = base_stat(effect.scale_stat) * multiplier + flat_value

        MVP decisions:
        - ATK/DEF use active_member final stats
        - HP uses party.team_hp_max (because party shares one HP bar)
        """
        base = 0.0
        if effect.scale_stat == ScaleStat.ATK:
            base = float(active_member.final_atk)
        elif effect.scale_stat == ScaleStat.DEF:
            base = float(active_member.final_def)
        elif effect.scale_stat == ScaleStat.HP:
            base = float(party.team_hp_max)
        else:
            base = 0.0

        return base * float(effect.multiplier) + float(effect.flat_value)

    def preview_card(
        self,
        party: PlayerPartySnapshot,
        active_member: CharacterSnapshot,
        card: Card,
        effects_by_card: Dict[str, List[CardEffect]],
    ) -> List[CardEffectResult]:
        """
        預覽卡牌的所有效果數值 (不改變戰鬥狀態)。

        Returns:
            List[CardEffectResult]
        """
        effects = effects_by_card.get(card.card_id, [])
        out: List[CardEffectResult] = []

        for eff in effects:
            v = self.compute_effect_value(party, active_member, eff)
            out.append(
                CardEffectResult(
                    card_id=card.card_id,
                    effect_index=eff.effect_index,
                    effect_type=eff.effect_type,
                    target=str(eff.target.value if hasattr(eff.target, "value") else eff.target),
                    value=float(v),
                )
            )
        return out


# ---------------------------------------------------------
# Optional small helpers for future refactor
# ---------------------------------------------------------

def compute_all_card_values_for_party(
    party: PlayerPartySnapshot,
    active_member: CharacterSnapshot,
    cards: List[Card],
    effects_by_card: Dict[str, List[CardEffect]],
) -> Dict[str, List[CardEffectResult]]:
    """
    Convenience function: compute values for many cards at once.
    """
    calc = CardStaticCalculator()
    out: Dict[str, List[CardEffectResult]] = {}
    for c in cards:
        out[c.card_id] = calc.preview_card(party, active_member, c, effects_by_card)
    return out
