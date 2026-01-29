# main.py
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

from battle_reporter import BattleReporter
from battle_simulator import BattleConfig, BattleSimulator
from card_repository import CardRepository
from combat_static_calculator import CombatStaticCalcConfig, CombatStaticCalculator
from monster_repository import MonsterRepository
from runtime_input_repository import RuntimeInputRepository, CharacterLoadoutInput
from models import PlayerPartySnapshot


def _pick_party_inputs(
    inputs_by_char_id: Dict[str, CharacterLoadoutInput],
    max_members: int = 3,
) -> List[CharacterLoadoutInput]:
    party = list(inputs_by_char_id.values())[:max_members]
    if not party:
        raise ValueError("CombatInputPanel 沒有任何角色輸入（至少要 1 個角色 block）")
    return party


def main() -> int:
    parser = argparse.ArgumentParser(description="Combat Simulator Entry")
    parser.add_argument("--data-dir", type=str, default="Data")
    parser.add_argument("--output-dir", type=str, default="Reports")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--enable-event-log", action="store_true")
    args = parser.parse_args()

    base_dir = Path(__file__).parent
    data_dir = (base_dir / args.data_dir).resolve()
    out_dir = (base_dir / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------
    # Reporter
    # -----------------------------
    reporter = BattleReporter(
        report_dir=out_dir,
        report_name=None,
        enable_event_log=bool(args.enable_event_log),
        log_level=None,
    )
    reporter.add_config("data_dir", str(data_dir))
    reporter.add_config("runs", int(args.runs))
    reporter.add_config("seed", args.seed)
    reporter.add_config("enable_event_log", bool(args.enable_event_log))

    # -----------------------------
    # Load runtime input panel
    # -----------------------------
    input_repo = RuntimeInputRepository(data_dir=data_dir, log=True)
    inputs_by_char_id = input_repo.load_combat_input_panel(
        excel_name="CombatInputPanel.xlsx",
        sheet_name="CombatInputPanel",
    )

    party_inputs = _pick_party_inputs(inputs_by_char_id, max_members=3)
    active_input = party_inputs[0]
    active_character_id = active_input.character_id

    reporter.add_config("party_member_ids", [p.character_id for p in party_inputs])
    reporter.add_config("active_character_id", active_character_id)
    reporter.add_config("partner_id", active_input.partner_id)
    reporter.add_config("partner_stack_count", getattr(active_input, "partner_stack_count", 0))

    # -----------------------------
    # Phase 1: CharacterSnapshot
    # -----------------------------
    static_cfg = CombatStaticCalcConfig(
        character_excel="Character.xlsx",
        sheet_base_stat_by_level="CharacterBaseStatByLevel",
        affection_excel="Character.xlsx",
        sheet_affection_by_level="AffectionByLevel",
    )
    static_calc = CombatStaticCalculator(config=static_cfg, verbose=False)

    snapshots = []
    for p in party_inputs:
        snap = static_calc.calc_character_snapshot(
            character_id=p.character_id,
            level=p.level,
            affection_level=p.affection_level,
        )
        snapshots.append(snap)

    party_snapshot = PlayerPartySnapshot(
        members=snapshots,
        active_character_id=active_character_id,
    )
    reporter.add_config("party_hp_max", party_snapshot.team_hp_max)

    # -----------------------------
    # Cards
    # -----------------------------
    card_repo = CardRepository(data_dir=data_dir)
    character_ids = [p.character_id for p in party_inputs]

    party_cards, effects_by_card_id = card_repo.load_cards_for_characters(
        excel_name="Card.xlsx",
        sheet_card="Card",
        sheet_effect="CardEffect",
        character_ids=character_ids,
    )

    # Optional: filter cards by CombatInputPanel CardList[] if provided
    if getattr(active_input, "card_ids", None):
        allowed = set(active_input.card_ids)
        party_cards = [c for c in party_cards if c.card_id in allowed]
        effects_by_card_id = {k: v for k, v in effects_by_card_id.items() if k in allowed}

    if not party_cards:
        raise ValueError("沒有可用的卡牌。請檢查 Card.xlsx / CombatInputPanel 的 CardList[]")

    reporter.add_config("party_card_count", len(party_cards))

    # -----------------------------
    # Monsters
    # -----------------------------
    mon_repo = MonsterRepository(data_dir=data_dir)
    monster_indexes, monster_base_stats, monster_skills = mon_repo.load_monsters(
        excel_name="Monster.xlsx",
        sheet_index="MonsterIndex",
        sheet_base_stat="MonsterBaseStat",
        sheet_skill="MonsterSkill",
    )
    reporter.add_config("monster_count", len(monster_indexes))

    # -----------------------------
    # Ability (disabled for now to ensure run)
    # -----------------------------
    ability_system = None
    ability_context = None

    # -----------------------------
    # Run Simulator
    # -----------------------------
    sim = BattleSimulator(
        config=BattleConfig(rng_seed=args.seed),
        reporter=reporter,
    )

    results = sim.run_many(
        battle_count=int(args.runs),
        party=party_snapshot,
        party_cards=party_cards,
        card_effects_by_id=effects_by_card_id,
        monster_indexes=monster_indexes,
        monster_base_stats=monster_base_stats,
        monster_skills=monster_skills,
        ability_system=ability_system,
        ability_context=ability_context,
    )

    for r in results:
        try:
            reporter.add_summary(asdict(r))
        except Exception:
            reporter.add_summary(r.__dict__)

    report_path = reporter.flush_to_excel()
    print(f"Report exported: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
