# main.py
# Orchestrator / Pipeline Runner + Battle Simulator CLI

import pandas as pd

from combat_static_calculator import calc_all_character_snapshots
from card_repository import CardRepository
from monster_repository import MonsterRepository
from battle_simulator import BattleSimulator
from models import BattleConfig, LogLevel


def prompt_positive_int(prompt: str) -> int:
    while True:
        s = input(prompt).strip()
        try:
            v = int(s)
            if v <= 0:
                print("請輸入正整數。")
                continue
            return v
        except Exception:
            print("輸入格式錯誤，請輸入正整數。")


def prompt_confirm_y(prompt: str = "是否確定開始？ (Y/N)\n> ") -> bool:
    s = input(prompt).strip().upper()
    return s == "Y"


def main():
    print("=== Battle Simulator (MVP) ===")

    battle_count = prompt_positive_int("請輸入要模擬的戰鬥次數（正整數）：\n> ")
    print(f"\n你即將模擬 {battle_count} 場戰鬥。")
    print("每一場戰鬥會在『我方或敵方全滅』時結束。")

    if not prompt_confirm_y("是否確定開始模擬？ (Y/N)\n> "):
        print("已取消模擬。")
        input("按 Enter 鍵結束程式...")
        return

    # -----------------------------
    # Phase 1: player snapshot
    # -----------------------------
    snapshots = calc_all_character_snapshots(verbose=False)
    if not snapshots:
        print("❌ Phase 1: no snapshots. Check CombatInputPanel.xlsx")
        input("按 Enter 鍵結束程式...")
        return

    # MVP: pick the first character as player
    player_snap = snapshots[0]
    print(f"\n[Player] Use CharacterSnapshot: {player_snap.character_id} ATK={player_snap.final_atk} DEF={player_snap.final_def} HP={player_snap.final_hp}")

    # -----------------------------
    # Load cards
    # -----------------------------
    try:
        card_repo = CardRepository("Card.xlsx")
        card_repo.load()
    except Exception as e:
        print(f"❌ Failed to load Card.xlsx: {e}")
        input("按 Enter 鍵結束程式...")
        return

    player_cards = card_repo.get_cards_by_character(player_snap.character_id)
    if not player_cards:
        print(f"❌ No cards found for character: {player_snap.character_id}")
        input("按 Enter 鍵結束程式...")
        return

    print(f"[Card] Loaded {len(player_cards)} cards for {player_snap.character_id}")

    # -----------------------------
    # Load monsters
    # -----------------------------
    try:
        monster_repo = MonsterRepository("Monster.xlsx")
        monster_repo.load()
    except Exception as e:
        print(f"❌ Failed to load Monster.xlsx: {e}")
        input("按 Enter 鍵結束程式...")
        return

    monsters = monster_repo.get_all_monsters()
    if not monsters:
        print("❌ No monsters found.")
        input("按 Enter 鍵結束程式...")
        return

    print(f"[Monster] Loaded {len(monsters)} monsters: " + ", ".join([m.monster_id for m in monsters]))

    # -----------------------------
    # Run Simulation
    # -----------------------------
    config = BattleConfig(log_level=LogLevel.INFO, max_turns=999)
    sim = BattleSimulator(config)

    results = sim.run_many(
        battle_count=battle_count,
        player_snapshot=player_snap,
        player_cards=player_cards,
        monsters=monsters,
    )

    # -----------------------------
    # Summary
    # -----------------------------
    print("\n=== Simulation Summary ===")
    df = pd.DataFrame(
        [
            {
                "Battle": r.battle_index,
                "Winner": r.winner,
                "Turns": r.turns,
                "PlayerHP_End": round(r.player_hp_end, 1),
                "EnemiesAlive": r.enemies_alive,
            }
            for r in results
        ]
    )

    print(df.to_string(index=False))

    # Simple aggregate
    win_player = sum(1 for r in results if r.winner == "Player")
    win_enemy = sum(1 for r in results if r.winner == "Enemy")
    print(f"\nPlayer Wins: {win_player}/{len(results)} | Enemy Wins: {win_enemy}/{len(results)}")

    input("\n按 Enter 鍵結束程式...")


if __name__ == "__main__":
    main()
