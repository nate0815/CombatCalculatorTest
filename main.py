# main.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


# ----------------------------
# Safe helpers for reporter API differences
# ----------------------------
def safe_add_config(reporter: Any, key: str, value: Any) -> None:
    if reporter is None:
        return
    fn = getattr(reporter, "add_config", None)
    if not callable(fn):
        return

    try:
        fn(key, value)
        return
    except TypeError:
        pass

    try:
        fn({key: value})
        return
    except TypeError:
        pass

    try:
        fn(**{key: value})
    except TypeError:
        return


def safe_add_summary(reporter: Any, row: Dict[str, Any]) -> None:
    if reporter is None:
        return
    fn = getattr(reporter, "add_summary", None)
    if not callable(fn):
        return

    try:
        fn(**row)
        return
    except TypeError:
        pass

    try:
        fn(row)
        return
    except TypeError:
        return


# ----------------------------
# Ability loader (best-effort)
# ----------------------------
def try_load_ability_system(data_dir: Path) -> Optional[Any]:
    try:
        from ability_system import AbilitySystem  # type: ignore
    except Exception:
        return None

    try:
        try:
            sys = AbilitySystem(data_dir=data_dir)
        except TypeError:
            sys = AbilitySystem()
    except Exception:
        return None

    candidates = ["load_from_excel", "load_excel", "load"]
    excel_name = "Ability.xlsx"

    for method_name in candidates:
        m = getattr(sys, method_name, None)
        if not callable(m):
            continue
        try:
            m(
                excel_name=excel_name,
                sheet_ability="Ability",
                sheet_condition_group="ConditionGroup",
                sheet_condition="Condition",
                sheet_effect_group="EffectGroup",
                sheet_effect="Effect",
            )
            return sys
        except TypeError:
            try:
                m(excel_name=excel_name)
                return sys
            except Exception:
                pass
        except Exception:
            pass

    return None


def build_ability_context_from_inputs(first_input: Any) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {}

    def pick(*names: str) -> Any:
        for n in names:
            if hasattr(first_input, n):
                v = getattr(first_input, n)
                if v is not None and v != "":
                    return v
        return None

    owner_class = pick("owner_class", "OwnerClass", "character_class", "CharacterClass")
    partner_class = pick("partner_class", "PartnerClass")
    partner_id = pick("partner_id", "PartnerId")
    stack = pick("partner_stack_count", "PartnerStackCount", "stack_count", "StackCount")

    if owner_class is not None:
        ctx["owner_class"] = owner_class
    if partner_class is not None:
        ctx["partner_class"] = partner_class
    if partner_id is not None:
        ctx["partner_id"] = partner_id
    if stack is not None:
        try:
            ctx["partner_stack_count"] = int(stack)
        except Exception:
            ctx["partner_stack_count"] = stack

    return ctx


# ----------------------------
# Build BattleConfig safely (support frozen dataclass)
# ----------------------------
def build_battle_config(BattleConfig: Any, battle_count: int, max_turns: int, seed: int) -> Any:
    candidates = [
        {"battle_count": battle_count, "max_turns": max_turns, "seed": seed},
        {"battle_count": battle_count, "max_turns": max_turns, "rng_seed": seed},
        {"runs": battle_count, "max_turns": max_turns, "seed": seed},
        {"runs": battle_count, "turn_limit": max_turns, "seed": seed},
        {"seed": seed},
        {"rng_seed": seed},
        {},
    ]

    last_err: Optional[Exception] = None
    for kw in candidates:
        try:
            return BattleConfig(**kw)
        except TypeError as e:
            last_err = e

    raise last_err if last_err else TypeError("Unable to construct BattleConfig")


def _select_party_snapshots(all_snapshots: Any, party_ids: List[str]) -> List[Any]:
    """
    calc_all_character_snapshots() 可能回傳 list 或 dict
    - list: [CharacterSnapshot, ...]
    - dict: {character_id: CharacterSnapshot, ...}

    這裡只挑 party 需要的三隻，並依照 party_ids 的順序回傳。
    """
    if isinstance(all_snapshots, dict):
        out = []
        for cid in party_ids:
            if cid not in all_snapshots:
                raise ValueError(f"Phase1 snapshot 缺少角色: {cid}")
            out.append(all_snapshots[cid])
        return out

    # list fallback
    by_id = {s.character_id: s for s in all_snapshots}
    out = []
    for cid in party_ids:
        if cid not in by_id:
            raise ValueError(f"Phase1 snapshot 缺少角色: {cid}")
        out.append(by_id[cid])
    return out


def main() -> int:
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "Data"
    REPORT_DIR = BASE_DIR / "Reports"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    from runtime_input_repository import RuntimeInputRepository
    from combat_static_calculator import calc_all_character_snapshots
    from card_repository import CardRepository
    from monster_repository import MonsterRepository
    from models import PlayerPartySnapshot

    # reporter
    reporter = None
    try:
        from battle_reporter import BattleReporter  # type: ignore
        try:
            reporter = BattleReporter(report_dir=REPORT_DIR, enable_event_log=False)
        except TypeError:
            reporter = BattleReporter(report_dir=REPORT_DIR)
    except Exception:
        reporter = None

    safe_add_config(reporter, "data_dir", str(DATA_DIR))

    # 1) Load CombatInputPanel
    input_repo = RuntimeInputRepository(data_dir=DATA_DIR, log=True)
    inputs_by_char = input_repo.load_combat_input_panel(
        excel_name="CombatInputPanel.xlsx",
        sheet_name="CombatInputPanel",
    )
    if not inputs_by_char:
        raise ValueError("CombatInputPanel.xlsx / CombatInputPanel 沒有任何輸入資料")

    party_char_ids = list(inputs_by_char.keys())
    active_character_id = party_char_ids[0]
    safe_add_config(reporter, "party_char_ids", ",".join(party_char_ids))
    safe_add_config(reporter, "active_character_id", active_character_id)

    # 2) Phase1 snapshots (只取 party 三隻)
    all_snapshots = calc_all_character_snapshots(verbose=False)
    party_snapshots = _select_party_snapshots(all_snapshots, party_char_ids)

    party_snapshot = PlayerPartySnapshot(
        members=party_snapshots,
        active_character_id=active_character_id,
    )

    # 3) Cards
    card_repo = CardRepository(data_dir=DATA_DIR)
    party_cards, effects_by_card_id = card_repo.load_cards_for_characters(
        excel_name="Card.xlsx",
        sheet_card="Card",
        sheet_effect="CardEffect",
        character_ids=party_char_ids,
    )
    if not party_cards:
        raise ValueError("Card.xlsx 沒有載到任何卡牌（請檢查 Card / CardEffect 分頁與欄位）")
    safe_add_config(reporter, "party_card_count", len(party_cards))

    # 4) Monsters
    mon_repo = MonsterRepository(data_dir=DATA_DIR)
    monster_indexes, monster_base_stats, monster_skills = mon_repo.load_monsters(
        excel_name="Monster.xlsx",
        sheet_index="MonsterIndex",
        sheet_base_stat="MonsterBaseStat",
        sheet_skill="MonsterSkill",
    )
    if not monster_indexes:
        raise ValueError("Monster.xlsx / MonsterIndex 沒有資料")
    safe_add_config(reporter, "monster_count", len(monster_indexes))

    # 5) Ability (best-effort)
    ability_system = try_load_ability_system(DATA_DIR)
    safe_add_config(reporter, "ability_enabled", ability_system is not None)

    first_input = inputs_by_char[active_character_id]
    ability_ctx = build_ability_context_from_inputs(first_input)
    safe_add_config(reporter, "ability_ctx_keys", ",".join(list(ability_ctx.keys())))

    # 6) Simulator + config
    from battle_simulator import BattleConfig, BattleSimulator  # type: ignore

    battle_count = 3
    max_turns = 30
    seed = 123
    cfg = build_battle_config(BattleConfig, battle_count=battle_count, max_turns=max_turns, seed=seed)

    # 建構 simulator（相容多版本）
    simulator = None
    ctor_errors: List[str] = []
    for kwargs in [
        {"config": cfg, "reporter": reporter, "ability_system": ability_system},
        {"config": cfg, "reporter": reporter},
        {"reporter": reporter, "ability_system": ability_system},
        {"reporter": reporter},
        {"config": cfg},
        {},
    ]:
        try:
            simulator = BattleSimulator(**kwargs)
            break
        except TypeError as e:
            ctor_errors.append(str(e))

    if simulator is None:
        raise TypeError("BattleSimulator 建構失敗: " + " | ".join(ctor_errors))

    # 7) Run (優先走你 traceback 看到的 run_battles)
    results = None
    run_errors: List[str] = []

    if hasattr(simulator, "run_battles"):
        for kwargs in [
            dict(
                config=cfg,
                party=party_snapshot,
                party_cards=party_cards,
                effects_by_card_id=effects_by_card_id,
                monster_indexes=monster_indexes,
                monster_base_stats=monster_base_stats,
                monster_skills=monster_skills,
                ability_extra_ctx=ability_ctx,
            ),
            dict(
                config=cfg,
                party=party_snapshot,
                party_cards=party_cards,
                effects_by_card_id=effects_by_card_id,
                monster_indexes=monster_indexes,
                monster_base_stats=monster_base_stats,
                monster_skills=monster_skills,
            ),
        ]:
            try:
                results = simulator.run_battles(**kwargs)
                break
            except TypeError as e:
                run_errors.append(f"run_battles: {e}")

    if results is None and hasattr(simulator, "run_many"):
        for kwargs in [
            dict(
                battle_count=battle_count,
                party=party_snapshot,
                party_cards=party_cards,
                card_effects_by_id=effects_by_card_id,
                monster_indexes=monster_indexes,
                monster_base_stats=monster_base_stats,
                monster_skills=monster_skills,
                ability_context=ability_ctx,
            ),
            dict(
                battle_count=battle_count,
                party=party_snapshot,
                party_cards=party_cards,
                card_effects_by_id=effects_by_card_id,
                monster_indexes=monster_indexes,
                monster_base_stats=monster_base_stats,
                monster_skills=monster_skills,
            ),
        ]:
            try:
                results = simulator.run_many(**kwargs)
                break
            except TypeError as e:
                run_errors.append(f"run_many: {e}")

    if results is None:
        raise TypeError("BattleSimulator 執行失敗: " + " | ".join(run_errors))

    # 8) Summary
    for r in results:
        row = {
            "battle_index": getattr(r, "battle_index", None),
            "winner": getattr(r, "winner", None),
            "turns": getattr(r, "turns", None),
            "player_hp_end": getattr(r, "player_hp_end", None),
            "enemies_alive": getattr(r, "enemies_alive", None),
        }
        safe_add_summary(reporter, row)

    # 9) Export report
    out = None
    if reporter is not None:
        if hasattr(reporter, "flush_to_excel"):
            out = reporter.flush_to_excel()
        elif hasattr(reporter, "flush"):
            out = reporter.flush()

    print(f"✅ Done. Report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
