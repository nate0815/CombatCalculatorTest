# main.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from battle_reporter import BattleReporter, make_default_report_name
from battle_simulator import BattleConfig, BattleSimulator
from card_repository import CardRepository
from monster_repository import MonsterRepository
from models import LogLevel, PlayerPartySnapshot


# =========================================================
# Paths
# =========================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"
REPORT_DIR = BASE_DIR / "Reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# Phase 1 (Character snapshots)
# =========================================================
def load_party_snapshots() -> PlayerPartySnapshot:
    """
    載入隊伍快照 (Phase 1)。
    Reuse Phase1 calculator.
    Expected:
      combat_static_calculator.calc_all_character_snapshots() -> List[CharacterSnapshot]

    MVP behavior:
    - Take the first 3 snapshots as party members.
    - Active character defaults to the first member.
    """
    try:
        from combat_static_calculator import calc_all_character_snapshots  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "❌ Failed to import calc_all_character_snapshots from combat_static_calculator.py\n"
            "請確認 combat_static_calculator.py 內有這個函式，且 main.py 與該檔案在同一層。\n"
            f"Import error: {e}"
        )

    snapshots = calc_all_character_snapshots(verbose=False)

    if not snapshots or len(snapshots) < 1:
        raise RuntimeError("❌ No character snapshots returned. Check your Phase1 inputs/tables.")

    if len(snapshots) < 3:
        print(f"⚠️ Only {len(snapshots)} character snapshots found. Party will use all of them.")

    members = snapshots[:3]
    active_id = members[0].character_id
    party = PlayerPartySnapshot(members=members, active_character_id=active_id)

    print(
        f"[Party] Members={', '.join(m.character_id for m in members)} | "
        f"TeamHP={party.team_hp:.1f}/{party.team_hp_max:.1f} | Active={party.active_character_id}"
    )
    return party


# =========================================================
# CLI
# =========================================================
def ask_battle_count() -> int:
    """詢問使用者要模擬的戰鬥次數"""
    while True:
        s = input("請輸入要模擬戰鬥的次數（清空任一方血量算 1 次）：").strip()
        try:
            n = int(s)
            if n <= 0:
                print("請輸入大於 0 的整數。")
                continue
            return n
        except Exception:
            print("輸入格式錯誤，請輸入整數。")


def ask_confirm(n: int) -> bool:
    """確認是否開始"""
    s = input(f"你確定要開始模擬 {n} 次戰鬥嗎？輸入 Y 開始，其它任意鍵取消：").strip()
    return s.upper() == "Y"


# =========================================================
# Main
# =========================================================
def main() -> None:
    # -------------------------
    # 1) Ask user
    # 1) 詢問使用者設定
    # -------------------------
    battle_count = ask_battle_count()
    if not ask_confirm(battle_count):
        print("已取消。")
        return

    # -------------------------
    # 2) Load party snapshot (Phase1)
    # 2) 載入隊伍資料 (Phase 1 計算結果)
    # -------------------------
    party = load_party_snapshots()
    party_character_ids = [m.character_id for m in party.members]

    # -------------------------
    # 3) Load cards (Party pool)
    # 3) 載入卡牌資料 (根據隊伍成員篩選)
    # -------------------------
    card_repo = CardRepository(data_dir=DATA_DIR, log_level=LogLevel.INFO)
    party_cards, effects_by_card = card_repo.load_cards_for_characters(
        excel_name="Card.xlsx",
        sheet_card="Card",
        sheet_effect="CardEffect",
        character_ids=party_character_ids,
    )

    if not party_cards:
        raise RuntimeError("❌ Party has no cards. Check Card.xlsx filters (CharacterId) and rows.")

    ap_costs = sorted(set(int(c.ap_cost) for c in party_cards))
    print(f"[Card] PartyCardCount={len(party_cards)} | ApCostSet={ap_costs}")

    # -------------------------
    # 4) Load monsters
    # 4) 載入怪物資料
    # -------------------------
    monster_repo = MonsterRepository(data_dir=DATA_DIR, log_level=LogLevel.INFO)
    monster_indexes, monster_base_stats, monster_skills = monster_repo.load_monsters(
        excel_name="Monster.xlsx",
        sheet_index="MonsterIndex",
        sheet_base_stat="MonsterBaseStat",
        sheet_skill="MonsterSkill",
    )

    # -------------------------
    # 5) Prepare reporter (NO EventLog in Excel)
    # 5) 準備報表產生器 (設定不輸出 EventLog 到 Excel 以節省效能)
    # -------------------------
    report_name = make_default_report_name(prefix="battle_report")
    reporter = BattleReporter(
        report_dir=REPORT_DIR,
        report_name=report_name,
        enable_event_log=False,   # ✅ Excel 不輸出 EventLog
        log_level=LogLevel.INFO,  # 保留相容性（不影響）
    )

    # -------------------------
    # 6) Run simulation
    # 6) 執行戰鬥模擬
    # -------------------------
    config = BattleConfig(
        ap_max=3,
        max_turns=999,
        log_level=LogLevel.INFO,
        stop_when_insufficient_ap=True,
    )
    sim = BattleSimulator(config=config, reporter=reporter)

    results = sim.run_many(
        battle_count=battle_count,
        party=party,
        party_cards=party_cards,
        card_effects_by_id=effects_by_card,
        monster_indexes=monster_indexes,
        monster_base_stats=monster_base_stats,
        monster_skills=monster_skills,
    )

    # -------------------------
    # 7) Console summary (簡潔統計)
    # 7) 控制台輸出簡易統計
    # -------------------------
    player_wins = sum(1 for r in results if r.winner == "Player")
    enemy_wins = sum(1 for r in results if r.winner == "Enemy")
    unknown = len(results) - player_wins - enemy_wins

    print("\n=== Simulation Summary ===")
    print(f"Total Battles: {len(results)}")
    print(f"Player Wins : {player_wins}")
    print(f"Enemy Wins  : {enemy_wins}")
    if unknown > 0:
        print(f"Unknown     : {unknown}")

    # -------------------------
    # 8) Export Excel report (Summary + Config only)
    # 8) 匯出 Excel 報表
    # -------------------------
    extra_config = {
        "battle_count": battle_count,
        "ap_max": config.ap_max,
        "max_turns": config.max_turns,
        "stop_when_insufficient_ap": config.stop_when_insufficient_ap,
        "party_members": ",".join(party_character_ids),
        "party_team_hp_max": float(party.team_hp_max),
        "cards_count": len(party_cards),
        "ap_cost_set": ",".join(str(x) for x in ap_costs),
        "monsters_count": len(monster_indexes),
        "enable_event_log": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    out_path = reporter.flush_to_excel(extra_config=extra_config)
    if out_path is None:
        print("⚠️ 報表輸出未配置（report_dir/report_name 為空），已略過 Excel 輸出。")
    else:
        print(f"\n✅ 已輸出報表：{out_path}")

    input("\n按 Enter 鍵結束程式...")


if __name__ == "__main__":
    main()
