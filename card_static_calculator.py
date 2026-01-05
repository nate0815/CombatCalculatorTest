"""
card_static_calculator.py

Phase: Static Card Calculation (Phase 2 MVP)
Responsibility:
- Take Phase1 CharacterSnapshot (final ATK/DEF/HP)
- Apply CardDef (ordered effects) to compute card outputs
- No draw, no turn, no enemy logic (yet)

MVP supports EffectType:
- Damage / Shield / Heal

FlatValue supports None/empty/"None" -> treated as 0.0
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from models import CharacterSnapshot
from card_repository import CardDef, CardEffectDef


# =========================================================
# Utils
# =========================================================

def debug_print(verbose: bool, *args, **kwargs):
    if verbose:
        print(*args, **kwargs)


def _get_base_stat(snapshot: CharacterSnapshot, scale_stat: str) -> float:
    key = (scale_stat or "").strip().upper()
    if key == "ATK":
        return float(snapshot.final_atk)
    if key == "DEF":
        return float(snapshot.final_def)
    if key == "HP":
        return float(snapshot.final_hp)
    # Unknown scale stat -> 0 (safe fallback)
    return 0.0


def _norm_effect_type(effect_type: str) -> str:
    return (effect_type or "").strip()


# =========================================================
# Output Models
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
    totals: Dict[str, float]  # {"Damage": x, "Heal": y, "Shield": z}


# =========================================================
# Core Calculation
# =========================================================

def calc_effect(snapshot: CharacterSnapshot, eff: CardEffectDef) -> CardEffectResult:
    base = _get_base_stat(snapshot, eff.scale_stat)
    mult = float(eff.multiplier)
    flat = float(eff.flat_value)
    value = base * mult + flat

    return CardEffectResult(
        effect_index=eff.effect_index,
        effect_type=eff.effect_type,
        scale_stat=eff.scale_stat,
        base_stat=base,
        multiplier=mult,
        flat_value=flat,
        value=value,
    )


def calc_card(snapshot: CharacterSnapshot, card: CardDef, verbose: bool = False) -> CardResult:
    results: List[CardEffectResult] = []
    totals: Dict[str, float] = {"Damage": 0.0, "Heal": 0.0, "Shield": 0.0}

    debug_print(verbose, "----------------------------------")
    debug_print(verbose, f"Card: {card.card_id} (Tier={card.epiphany_tier}, Group={card.group_id})")
    debug_print(verbose, f"Owner: {card.character_id}")
    debug_print(verbose, f"Snapshot: ATK={snapshot.final_atk}, DEF={snapshot.final_def}, HP={snapshot.final_hp}")

    if not card.effects:
        debug_print(verbose, "⚠️ No effects found for this card.")
    else:
        for eff in card.effects:
            r = calc_effect(snapshot, eff)
            results.append(r)

            et = _norm_effect_type(r.effect_type)
            if et in totals:
                totals[et] += r.value
            else:
                # Unknown effect types are kept but not summed in totals (future-proof)
                totals.setdefault(et, 0.0)
                totals[et] += r.value

            debug_print(
                verbose,
                f"  [{r.effect_index}] {r.effect_type} scale={r.scale_stat} "
                f"base={r.base_stat} mult={r.multiplier} flat={r.flat_value} => {r.value}"
            )

    debug_print(
        verbose,
        f"Totals: Damage={totals.get('Damage', 0.0)}, Heal={totals.get('Heal', 0.0)}, Shield={totals.get('Shield', 0.0)}"
    )

    return CardResult(
        card_id=card.card_id,
        character_id=card.character_id,
        epiphany_tier=card.epiphany_tier,
        effects=results,
        totals=totals,
    )
