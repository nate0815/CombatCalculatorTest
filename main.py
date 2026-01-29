# main.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def ask_int(prompt: str, default: Optional[int] = None) -> int:
    while True:
        suffix = f" (default={default})" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw == "" and default is not None:
            return int(default)
        try:
            return int(raw)
        except Exception:
            print("請輸入整數。")


def ask_choice(prompt: str, choices: list[str], default: str) -> str:
    raw = input(f"{prompt} {choices} (default={default}): ").strip()
    if raw == "":
        return default
    raw_u = raw.upper()
    for c in choices:
        if raw_u == c.upper():
            return c
    print(f"不支援的輸入，改用 default={default}")
    return default


def ask_yes_no(prompt: str, default: str = "n") -> bool:
    raw = input(f"{prompt} (y/n, default={default}): ").strip().lower()
    if raw == "":
        raw = default
    return raw in ("y", "yes")


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
    except TypeError:
        return


def try_load_ability_system(data_dir: Path) -> Optional[Any]:
    try:
        from ability_system import AbilitySystem  # type: ignore
    except Exception:
        return None

    try:
        sys = AbilitySystem()
    except Exception:
        return None

    # 嘗試載入（允許 AbilitySystem 內部自己決定讀哪些分頁）
    for mname in ["load_from_excel", "load_excel", "load"]:
        m = getattr(sys, mname, None)
        if not callable(m):
            continue
        try:
            m(excel_name="Ability.xlsx")
            return sys
        except TypeError:
            # 如果這版需要更多參數，就略過
            continue
        except Exception:
            continue
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


def main() -> int:
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "Data"
    REPORT_DIR = BASE_DIR / "Reports"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    battle_count = ask_int("要模擬幾場 battle？", default=100)
    log_level_str = ask_choice("log 等級？", ["INFO", "DEBUG", "TRACE"], default="TRACE")

    print("\n--- 設定確認 ---")
    print(f"data_dir: {DATA_DIR}")
    print(f"battle_count: {battle_count}")
    print(f"log_level: {log_level_str}")

    # 你剛剛那張截圖的流程是一路跑下去，不需要再多一層「是否開始」
    # 但保留這個詢問讓你避免誤按
    if not ask_yes_no("是否開始執行？", default="y"):
        print("已取消。")
        return 0

    from runtime_input_repository import RuntimeInputRepository
    from combat_static_calculator import calc_all_character_snapshots
    from card_repository import CardRepository
    from monster_repository import MonsterRepository
    from models import LogLevel, PlayerPartySnapshot

    # reporter
    reporter = None
    try:
        from battle_reporter import BattleReporter  # type: ignore

        enable_event_log = log_level_str in ("DEBUG", "TRACE")
        reporter = BattleReporter(report_dir=REPORT_DIR, enable_event_log=enable_event_log)
    except Exception:
        reporter = None

    safe_add_config(reporter, "data_dir", str(DATA_DIR))
    safe_add_config(reporter, "battle_count", battle_count)
    safe_add_config(reporter, "log_level", log_level_str)

    # Load CombatInputPanel
    input_repo = RuntimeInputRepository(data_dir=DATA_DIR, log=True)
    inputs_by_char = input_repo.load_combat_input_panel(
        excel_name="CombatInputPanel.xlsx",
        sheet_name="CombatInputPanel",
    )
    if not inputs_by_char:
        raise ValueError("CombatInputPanel.xlsx / CombatInputPanel 沒有任何輸入資料")

    party_char_ids = list(inputs_by_char.keys())
    active_character_id = party_char_ids[0]
    print(f"[Main] Party: {', '.join(party_char_ids)} (active={active_character_id})")

    # Phase 1 snapshots
    snapshots = calc_all_character_snapshots(verbose=False)
    if not snapshots:
        raise ValueError("calc_all_character_snapshots() 沒有產出任何 CharacterSnapshot")

    party_snapshot = PlayerPartySnapshot(
        members=snapshots,
        active_character_id=active_character_id,
    )

    # Cards
    card_repo = CardRepository(data_dir=DATA_DIR)
    party_cards, effects_by_card_id = card_repo.load_cards_for_characters(
        excel_name="Card.xlsx",
        sheet_card="Card",
        sheet_effect="CardEffect",
        character_ids=party_char_ids,
    )
    print(f"[Main] Loaded cards: {len(party_cards)}")
    if not party_cards:
        raise ValueError("Card.xlsx 沒有載到任何卡牌")

    # Monsters
    mon_repo = MonsterRepository(data_dir=DATA_DIR)
    monster_indexes, monster_base_stats, monster_skills = mon_repo.load_monsters(
        excel_name="Monster.xlsx",
        sheet_index="MonsterIndex",
        sheet_base_stat="MonsterBaseStat",
        sheet_skill="MonsterSkill",
    )
    print(f"[Main] Loaded monsters: {len(monster_indexes)}")
    if not monster_indexes:
        raise ValueError("Monster.xlsx / MonsterIndex 沒有資料")

    # Ability
    ability_system = try_load_ability_system(DATA_DIR)
    safe_add_config(reporter, "ability_enabled", ability_system is not None)

    first_input = inputs_by_char[active_character_id]
    ability_ctx = build_ability_context_from_inputs(first_input)
    safe_add_config(reporter, "ability_ctx_keys", ",".join(list(ability_ctx.keys())))

    # Simulator + Config
    from battle_simulator import BattleConfig, BattleSimulator  # type: ignore

    cfg = BattleConfig(battle_count=battle_count)
    simulator = BattleSimulator(
        ability_system=ability_system,
        reporter=reporter,
        log_level=LogLevel(log_level_str),
    )

    print("\n[Main] Start simulating...\n")
    results = simulator.run_battles(
        config=cfg,
        party=party_snapshot,
        party_cards=party_cards,
        effects_by_card_id=effects_by_card_id,
        monster_indexes=monster_indexes,
        monster_base_stats=monster_base_stats,
        monster_skills=monster_skills,
        ability_extra_ctx=ability_ctx,
    )

    # Summary rows
    for r in results:
        safe_add_summary(
            reporter,
            {
                "battle_index": getattr(r, "battle_index", None),
                "winner": getattr(r, "winner", None),
                "turns": getattr(r, "turns", None),
                "player_hp_end": getattr(r, "player_hp_end", None),
                "enemies_alive": getattr(r, "enemies_alive", None),
                "extra": getattr(r, "extra", None),
            },
        )

    # Win/Loss summary (terminal + EventLog/Config)
    player_win = sum(1 for r in results if getattr(r, "winner", "") == "Player")
    enemy_win = sum(1 for r in results if getattr(r, "winner", "") == "Enemy")
    timeout = sum(1 for r in results if getattr(r, "winner", "") == "Timeout")
    total = len(results)

    summary_line = f"[Result] PlayerWins={player_win} EnemyWins={enemy_win} Timeout={timeout} Total={total}"
    print("\n" + summary_line + "\n")

    safe_add_config(reporter, "result_player_wins", player_win)
    safe_add_config(reporter, "result_enemy_wins", enemy_win)
    safe_add_config(reporter, "result_timeout", timeout)
    safe_add_config(reporter, "result_total", total)

    # 寫入 EventLog（如果 enable_event_log=false 也不會爆，reporter 會忽略）
    if reporter is not None and hasattr(reporter, "add_event"):
        try:
            reporter.add_event(
                {
                    "battle_index": 0,
                    "turn": 0,
                    "actor": "System",
                    "event_type": "ResultSummary",
                    "message": summary_line,
                }
            )
        except Exception:
            pass

    out = None
    if reporter is not None:
        if hasattr(reporter, "flush_to_excel"):
            out = reporter.flush_to_excel()
        elif hasattr(reporter, "flush"):
            out = reporter.flush()

    print(f"✅ Done.\nReport: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
