# main.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import inspect


def ask_int_with_default(prompt: str, default: int, min_v: int = 1, max_v: int = 10**9) -> int:
    while True:
        s = input(f"{prompt} (default={default}): ").strip()
        if s == "":
            return default
        try:
            v = int(s)
            if v < min_v or v > max_v:
                print(f"請輸入介於 {min_v} ~ {max_v} 的整數")
                continue
            return v
        except ValueError:
            print("請輸入整數")


def ask_choice(prompt: str, default: str, choices: List[str]) -> str:
    choices_lower = [c.lower() for c in choices]
    default_lower = default.lower()
    while True:
        s = input(f"{prompt} {choices} (default={default}): ").strip().lower()
        if s == "":
            return default_lower
        if s in choices_lower:
            return s
        print(f"請輸入以下其中一個：{choices}")


def ask_yes_no(prompt: str, default_yes: bool = False) -> bool:
    default = "y" if default_yes else "n"
    while True:
        s = input(f"{prompt} (y/n, default={default}): ").strip().lower()
        if s == "":
            s = default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        print("請輸入 y 或 n")


def try_load_ability_system(data_dir: Path) -> Optional[Any]:
    try:
        from ability_system import AbilitySystem  # type: ignore
    except Exception:
        return None

    try:
        sys = AbilitySystem(data_dir=data_dir)  # type: ignore
    except TypeError:
        try:
            sys = AbilitySystem()  # type: ignore
        except Exception:
            return None
    except Exception:
        return None

    # loader method candidates
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


def _select_party_snapshots(all_snapshots: Any, party_ids: List[str]) -> List[Any]:
    if isinstance(all_snapshots, dict):
        return [all_snapshots[cid] for cid in party_ids]
    by_id = {s.character_id: s for s in all_snapshots}
    return [by_id[cid] for cid in party_ids]


def _construct_battle_simulator(BattleSimulator: Any, cfg: Any, reporter: Any, ability_system: Any) -> Any:
    """
    依照 BattleSimulator.__init__ 的實際參數，自動組 kwargs。
    你的錯誤就是因為它不吃 config / cfg，所以這裡用 signature 來判斷。
    """
    sig = inspect.signature(BattleSimulator.__init__)
    params = set(sig.parameters.keys())

    # 注意：__init__(self, ...) 會包含 self
    params.discard("self")

    candidates: List[Dict[str, Any]] = []

    # 先嘗試塞最多資訊（但要看它支援哪些參數）
    kw: Dict[str, Any] = {}
    if "config" in params:
        kw["config"] = cfg
    if "cfg" in params:
        kw["cfg"] = cfg
    if "reporter" in params:
        kw["reporter"] = reporter
    if "ability_system" in params:
        kw["ability_system"] = ability_system
    candidates.append(kw)

    # reporter only
    kw2: Dict[str, Any] = {}
    if "reporter" in params:
        kw2["reporter"] = reporter
    candidates.append(kw2)

    # no args
    candidates.append({})

    last_err: Optional[Exception] = None
    for c in candidates:
        try:
            return BattleSimulator(**c)
        except TypeError as e:
            last_err = e

    raise last_err if last_err else TypeError("Cannot construct BattleSimulator")


def main() -> int:
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "Data"
    REPORT_DIR = BASE_DIR / "Reports"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ============================
    # 你要的互動：只留 3 件事
    # 1) battle 次數（default=1）
    # 2) log level（INFO/DEBUG/TRACE）
    # 3) 是否開始執行（Y/N）
    # ============================
    battle_count = ask_int_with_default("要模擬幾場 battle？", default=1, min_v=1, max_v=200000)
    log_level_choice = ask_choice("log 等級？", default="INFO", choices=["INFO", "DEBUG", "TRACE"])

    print("\n--- 設定確認 ---")
    print(f"data_dir: {DATA_DIR}")
    print(f"battle_count: {battle_count}")
    print(f"log_level: {log_level_choice.upper()}")

    if not ask_yes_no("是否開始執行？", default_yes=False):
        print("已取消。")
        return 0

    # ----------------------------
    # Imports
    # ----------------------------
    from runtime_input_repository import RuntimeInputRepository
    from combat_static_calculator import calc_all_character_snapshots
    from card_repository import CardRepository
    from monster_repository import MonsterRepository
    from models import PlayerPartySnapshot, LogLevel

    # reporter
    reporter = None
    try:
        from battle_reporter import BattleReporter  # type: ignore
        enable_event_log = log_level_choice.lower() in ("debug", "trace")
        reporter = BattleReporter(report_dir=REPORT_DIR, enable_event_log=enable_event_log)
        # 兼容不同 reporter add_config 寫法
        try:
            reporter.add_config("data_dir", str(DATA_DIR))
            reporter.add_config("battle_count", str(battle_count))
            reporter.add_config("log_level", log_level_choice.upper())
        except TypeError:
            try:
                reporter.add_config({"data_dir": str(DATA_DIR), "battle_count": str(battle_count), "log_level": log_level_choice.upper()})
            except Exception:
                pass
    except Exception:
        reporter = None

    # 1) CombatInputPanel
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

    # 2) Phase1 snapshots（只取 party）
    all_snaps = calc_all_character_snapshots(verbose=False)
    party_snaps = _select_party_snapshots(all_snaps, party_char_ids)
    party_snapshot = PlayerPartySnapshot(members=party_snaps, active_character_id=active_character_id)

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
    print(f"[Main] Loaded cards: {len(party_cards)}")

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
    print(f"[Main] Loaded monsters: {len(monster_indexes)}")

    # 5) Ability (best-effort)
    ability_system = try_load_ability_system(DATA_DIR)
    first_input = inputs_by_char[active_character_id]
    ability_ctx = build_ability_context_from_inputs(first_input)

    # 6) Simulator + Config（Config 也用 signature 容錯；但不強制塞）
    from battle_simulator import BattleConfig, BattleSimulator  # type: ignore

    # 嘗試建 BattleConfig，但不硬塞 max_turns/seed
    # 只塞 log_level（如果它支援）
    cfg = None
    try:
        sig = inspect.signature(BattleConfig.__init__)
        params = set(sig.parameters.keys())
        params.discard("self")

        cfg_kwargs: Dict[str, Any] = {}
        if "log_level" in params:
            cfg_kwargs["log_level"] = LogLevel(log_level_choice.upper())
        elif "loglevel" in params:
            cfg_kwargs["loglevel"] = LogLevel(log_level_choice.upper())

        cfg = BattleConfig(**cfg_kwargs)
    except Exception:
        cfg = None

    simulator = _construct_battle_simulator(BattleSimulator, cfg=cfg, reporter=reporter, ability_system=ability_system)

    print("\n[Main] Start simulating...\n")

        # 7) Run（run_battles / run_many / positional 兼容）
    def _call_simulator_run(sim: Any) -> Any:
        # 統一我們想傳的資料
        payload = dict(
            party=party_snapshot,
            party_cards=party_cards,
            effects_by_card_id=effects_by_card_id,
            card_effects_by_id=effects_by_card_id,   # 有些版本用這個名
            monster_indexes=monster_indexes,
            monster_base_stats=monster_base_stats,
            monster_skills=monster_skills,
            ability_context=ability_ctx,
            ability_extra_ctx=ability_ctx,           # 有些版本用這個名
        )

        # 先嘗試 run_battles
        if hasattr(sim, "run_battles") and callable(getattr(sim, "run_battles")):
            fn = sim.run_battles
            sig = inspect.signature(fn)
            params = set(sig.parameters.keys())

            kwargs = {}
            for k, v in payload.items():
                if k in params:
                    kwargs[k] = v

            # battle_count / runs / n_battles / count 等可能名稱
            for count_key in ("battle_count", "runs", "n_battles", "count", "times"):
                if count_key in params:
                    kwargs[count_key] = battle_count
                    break

            # config（如果它是用 config 內帶 battle_count）
            if "config" in params and cfg is not None:
                kwargs["config"] = cfg

            # 1) 先用 kwargs 呼叫
            try:
                return fn(**kwargs)
            except TypeError:
                pass

            # 2) 如果它吃 positional：嘗試把 battle_count 當第一個參數
            try:
                return fn(battle_count, **kwargs)
            except TypeError:
                pass

            # 3) 最後：完全不給 battle_count（讓它用 config / default）
            try:
                # 去掉可能的 battle_count key
                for count_key in ("battle_count", "runs", "n_battles", "count", "times"):
                    kwargs.pop(count_key, None)
                return fn(**kwargs)
            except TypeError as e:
                raise TypeError(f"run_battles 呼叫失敗：{e}")

        # 再嘗試 run_many
        if hasattr(sim, "run_many") and callable(getattr(sim, "run_many")):
            fn = sim.run_many
            sig = inspect.signature(fn)
            params = set(sig.parameters.keys())

            kwargs = {}
            for k, v in payload.items():
                if k in params:
                    kwargs[k] = v

            for count_key in ("battle_count", "runs", "n_battles", "count", "times"):
                if count_key in params:
                    kwargs[count_key] = battle_count
                    break

            try:
                return fn(**kwargs)
            except TypeError:
                pass

            try:
                return fn(battle_count, **kwargs)
            except TypeError:
                pass

            try:
                for count_key in ("battle_count", "runs", "n_battles", "count", "times"):
                    kwargs.pop(count_key, None)
                return fn(**kwargs)
            except TypeError as e:
                raise TypeError(f"run_many 呼叫失敗：{e}")

        raise AttributeError("BattleSimulator 沒有 run_battles / run_many")

    results = _call_simulator_run(simulator)


    # 8) Export
    if reporter is not None:
        for r in results:
            row = {
                "battle_index": getattr(r, "battle_index", 0),
                "winner": getattr(r, "winner", ""),
                "turns": getattr(r, "turns", 0),
                "player_hp_end": getattr(r, "player_hp_end", 0),
                "enemies_alive": getattr(r, "enemies_alive", 0),
            }
            try:
                reporter.add_summary(**row)
            except TypeError:
                try:
                    reporter.add_summary(row)
                except Exception:
                    pass

        out = reporter.flush_to_excel() if hasattr(reporter, "flush_to_excel") else reporter.flush()
        print(f"\n✅ Done. Report: {out}")
    else:
        print("\n✅ Done. (Reporter disabled)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
