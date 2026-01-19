# main.py
# 從 __future__ 匯入 annotations，讓類型提示支援 postponed evaluation，意即在定義 class 時，可以在內部參考自己
from __future__ import annotations

# 匯入標準函式庫
from datetime import datetime
from pathlib import Path

# 匯入專案內部模組
from battle_reporter import BattleReporter, make_default_report_name
from battle_simulator import BattleConfig, BattleSimulator
from card_repository import CardRepository
from monster_repository import MonsterRepository
from models import LogLevel, PlayerPartySnapshot


# =========================================================
# 全域變數：定義常用的路徑
# =========================================================
# BASE_DIR: 專案根目錄，透過 __file__ 取得目前檔案所在位置的父目錄
BASE_DIR = Path(__file__).parent
# DATA_DIR: 資料檔案目錄，存放 Excel 等資料
DATA_DIR = BASE_DIR / "Data"
# REPORT_DIR: 報表輸出目錄
REPORT_DIR = BASE_DIR / "Reports"
# 建立報表目錄，如果已存在則不拋出錯誤 (exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# Phase 1 (載入角色快照)
# =========================================================
def load_party_snapshots() -> PlayerPartySnapshot:
    """
    載入隊伍快照 (Phase 1)。
    這個函式會從 combat_static_calculator.py 載入角色靜態數值計算結果。
    這是與 Phase 1 計算機串接的主要入口。

    預期行為:
      - combat_static_calculator.calc_all_character_snapshots() -> List[CharacterSnapshot]

    MVP (Minimum Viable Product) 的簡化行為:
    - 取回傳結果的前 3 個角色快照作為隊伍成員。
    - 預設第一個成員為場上活動角色。
    """
    try:
        # 動態匯入 Phase 1 的計算函式，這樣可以讓 main.py 與 Phase 1 的實作脫鉤，
        # 只要函式名稱與回傳格式正確即可。
        # type: ignore 是為了抑制靜態檢查工具對於動態 import 的警告。
        from combat_static_calculator import calc_all_character_snapshots  # type: ignore
    except Exception as e:
        # 若匯入失敗，拋出詳細的錯誤訊息，指導使用者如何修正問題。
        raise RuntimeError(
            "❌ 匯入 combat_static_calculator.py 的 calc_all_character_snapshots 函式失敗\n"
            "請確認 combat_static_calculator.py 檔案存在，且內部定義了此函式。\n"
            f"詳細錯誤: {e}"
        )

    # 呼叫函式取得所有角色的快照資料，verbose=False 表示不印出詳細計算過程。
    snapshots = calc_all_character_snapshots(verbose=False)

    # 檢查是否有成功取得資料，確保後續流程有資料可用。
    if not snapshots or len(snapshots) < 1:
        raise RuntimeError("❌ 計算函式未回傳任何角色快照，請檢查 Phase 1 的輸入或 Excel 表格。")

    # 如果角色數量不足 3 位，顯示警告訊息但仍繼續執行。
    if len(snapshots) < 3:
        print(f"⚠️ 僅找到 {len(snapshots)} 個角色快照，將使用所有找到的角色組成隊伍。")

    # 選取前 3 個角色作為隊伍成員 (切片語法 `[:3]` 會自動處理數量不足的情況)
    members = snapshots[:3]
    # 預設隊伍中第一個角色為活動角色 (Active Character)
    active_id = members[0].character_id
    # 使用載入的成員資料，建立玩家隊伍快照物件 (PlayerPartySnapshot)
    party = PlayerPartySnapshot(members=members, active_character_id=active_id)

    # 在控制台印出隊伍基本資訊，方便快速確認。
    print(
        f"[隊伍資訊] 成員={', '.join(m.character_id for m in members)} | "
        f"團隊血量={party.team_hp:.1f}/{party.team_hp_max:.1f} | 活動角色={party.active_character_id}"
    )
    # 回傳隊伍快照物件，供後續模擬使用。
    return party


# =========================================================
# CLI (命令列互動介面)
# =========================================================
def ask_battle_count() -> int:
    """詢問使用者要模擬的戰鬥次數，並確保輸入為正整數。"""
    while True:
        # 提示使用者輸入，並用 strip() 去除頭尾空白。
        s = input("請輸入要模擬戰鬥的次數（任一方血量歸零算 1 次）：").strip()
        try:
            # 嘗試將輸入轉換為整數
            n = int(s)
            # 檢查輸入是否為正數
            if n <= 0:
                print("請輸入大於 0 的整數。")
                continue  # 若不合法，繼續下一次迴圈
            # 若輸入合法，回傳數字並結束函式
            return n
        except Exception:
            # 若轉換失敗 (例如輸入了文字)，提示格式錯誤
            print("輸入格式錯誤，請輸入整數。")


def ask_confirm(n: int) -> bool:
    """向使用者顯示將要執行的次數，並確認是否要開始模擬。"""
    # 提示使用者確認，並將輸入轉為大寫以便比較
    s = input(f"確定要開始模擬 {n} 次戰鬥嗎？輸入 Y 開始，其它任意鍵取消：").strip()
    # 判斷輸入是否為 'Y'，是則回傳 True，否則回傳 False
    return s.upper() == "Y"


# =========================================================
# 主程式進入點 (Main Function)
# =========================================================
def main() -> None:
    """程式的主要執行流程"""
    # -------------------------
    # 1) 詢問使用者設定
    # -------------------------
    # 取得要模擬的戰鬥次數
    battle_count = ask_battle_count()
    # 確認是否執行，若使用者取消則提前結束程式
    if not ask_confirm(battle_count):
        print("操作已取消。")
        return

    # -------------------------
    # 2) 載入隊伍資料 (Phase 1 計算結果)
    # -------------------------
    # 呼叫函式取得 Phase 1 計算好的隊伍快照
    party = load_party_snapshots()
    # 從隊伍快照中，提取所有成員的角色 ID 列表，供後續篩選卡牌使用
    party_character_ids = [m.character_id for m in party.members]

    # -------------------------
    # 3) 載入卡牌資料 (根據隊伍成員篩選)
    # -------------------------
    # 初始化卡牌倉庫 (Repository)，負責讀取卡牌相關的 Excel 資料
    card_repo = CardRepository(data_dir=DATA_DIR, log_level=LogLevel.INFO)
    # 呼叫 load_cards_for_characters，只載入屬於隊伍成員的卡牌及其效果
    party_cards, effects_by_card = card_repo.load_cards_for_characters(
        excel_name="Card.xlsx",
        sheet_card="Card",
        sheet_effect="CardEffect",
        character_ids=party_character_ids,
    )

    # 如果隊伍沒有任何可用卡牌，表示設定有誤，應終止程式
    if not party_cards:
        raise RuntimeError("❌ 隊伍沒有任何可用卡牌，請檢查 Card.xlsx 的篩選條件 (CharacterId) 或內容。")

    # 取得所有卡牌的 AP 消耗值，並透過 set 去除重複，再排序，方便檢視
    ap_costs = sorted(set(int(c.ap_cost) for c in party_cards))
    print(f"[卡牌資訊] 隊伍卡牌數={len(party_cards)} | AP消耗種類={ap_costs}")

    # -------------------------
    # 4) 載入怪物資料
    # -------------------------
    # 初始化怪物倉庫，負責讀取怪物相關的 Excel 資料
    monster_repo = MonsterRepository(data_dir=DATA_DIR, log_level=LogLevel.INFO)
    # 載入所有怪物資料，包含索引、基礎數值和技能
    monster_indexes, monster_base_stats, monster_skills = monster_repo.load_monsters(
        excel_name="Monster.xlsx",
        sheet_index="MonsterIndex",
        sheet_base_stat="MonsterBaseStat",
        sheet_skill="MonsterSkill",
    )

    # -------------------------
    # 5) 準備報表產生器
    # -------------------------
    # 產生一個包含時間戳的預設報表檔名
    report_name = make_default_report_name(prefix="battle_report")
    # 初始化報表產生器
    reporter = BattleReporter(
        report_dir=REPORT_DIR,
        report_name=report_name,
        enable_event_log=False,   # ✅ 關鍵設定：不在 Excel 中輸出詳細的事件日誌 (EventLog)，可大幅提升大量模擬時的效能
        log_level=LogLevel.INFO,  # 此處的日誌等級主要用於相容性，實際模擬日誌由 BattleConfig 控制
    )

    # -------------------------
    # 6) 執行戰鬥模擬
    # -------------------------
    # 設定戰鬥模擬的核心參數
    config = BattleConfig(
        ap_max=3,                          # 每回合最大行動點數 (AP)
        max_turns=999,                     # 最大回合數上限，防止無限迴圈
        log_level=LogLevel.INFO,           # 模擬過程中的日誌詳細程度
        stop_when_insufficient_ap=True,    # 當剩餘 AP 不足以使用任何手牌時，是否自動結束回合
    )
    # 初始化戰鬥模擬器，並傳入設定與報表產生器
    sim = BattleSimulator(config=config, reporter=reporter)

    # 執行多次戰鬥模擬，並傳入所有需要的資料
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
# 6.5) 將每場 BattleResult 寫入 Summary
# -------------------------
    for r in results:
        reporter.add_summary(
            battle_index=r.battle_index,
            winner=r.winner,
            turns=r.turns,
            player_hp_end=r.player_hp_end,
            enemies_alive=r.enemies_alive,
        )

    # -------------------------
    # 7) 在控制台輸出簡易統計結果
    # -------------------------
    # 使用列表生成式與 sum() 快速計算玩家勝利次數
    player_wins = sum(1 for r in results if r.winner == "Player")
    # 計算敵人勝利次數
    enemy_wins = sum(1 for r in results if r.winner == "Enemy")
    # 計算其他結果 (例如：平手、達到最大回合數)
    unknown = len(results) - player_wins - enemy_wins

    print("\n=== 模擬結果摘要 ===")
    print(f"總戰鬥次數: {len(results)}")
    print(f"玩家勝利  : {player_wins}")
    print(f"敵人勝利  : {enemy_wins}")
    if unknown > 0:
        print(f"其他結果  : {unknown}")

    # -------------------------
    # 8) 匯出 Excel 報表 (僅含摘要與設定)
    # -------------------------
    # 準備一個字典，存放這次模擬的所有重要設定，將會寫入 Excel 的 'Config' 工作表
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
        "enable_event_log": False, # 與報表設定一致，記錄於此
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 呼叫 reporter 的 flush_to_excel 方法，將結果與設定寫入 Excel 檔案
    out_path = reporter.flush_to_excel(extra_config=extra_config)
    # 檢查是否有成功輸出檔案路徑
    if out_path is None:
        print("⚠️ 報表輸出路徑未設定，已略過 Excel 輸出。")
    else:
        print(f"\n✅ 報表已成功匯出至：{out_path}")

    # 暫停程式，等待使用者按 Enter 鍵後才會結束，方便使用者查看控制台輸出
    input("\n按 Enter 鍵結束程式...")


# __name__ == "__main__" 是 Python 的一個標準寫法。
# 當這個腳本被直接執行時 (例如 `python main.py`)，__name__ 的值會是 "__main__"，
# 這段程式碼就會被執行。如果這個腳本是被其他檔案 import 的，__name__ 會是模組名稱，
# 這段程式碼就不會執行，防止意外的程式啟動。
if __name__ == "__main__":
    main()