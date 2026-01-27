# main.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

import pandas as pd

from battle_reporter import BattleReporter, make_default_report_name
from battle_simulator import BattleConfig, BattleSimulator
from card_repository import CardRepository
from monster_repository import MonsterRepository
from models import LogLevel, PlayerPartySnapshot

# NEW: runtime input repo
from runtime_input_repository import RuntimeInputRepository

# NEW: Ability system
from ability_models import (
    AbilityDef,
    AbilityEffectType,
    ConditionGroupDef,
    ConditionLogic,
    ConditionRowDef,
    ConditionType,
    EffectGroupDef,
    EffectRowDef,
    ExecMode,
    TriggerEvent,
    ValueRefType,
)
from ability_system import AbilitySystem


# =========================================================
# Paths
# =========================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"
REPORT_DIR = BASE_DIR / "Reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# Phase 1 (載入角色快照)
# =========================================================
def load_party_snapshots() -> PlayerPartySnapshot:
    """
    載入隊伍快照 (Phase 1)。

    這個函式會從 combat_static_calculator.py 載入角色靜態數值計算結果。
    MVP 行為:
    - 取回傳結果的前 3 個角色快照作為隊伍成員
    - 預設第一個成員為場上活動角色
    """
    try:
        from combat_static_calculator import calc_all_character_snapshots  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "❌ 匯入 combat_static_calculator.py 的 calc_all_character_snapshots 函式失敗\n"
            "請確認 combat_static_calculator.py 檔案存在，且內部定義了此函式。\n"
            f"詳細錯誤: {e}"
        )

    snapshots = calc_all_character_snapshots(verbose=False)
    if not snapshots or len(snapshots) < 1:
        raise RuntimeError("❌ 計算函式未回傳任何角色快照，請檢查 Phase 1 的輸入或 Excel 表格。")

    if len(snapshots) < 3:
        print(f"⚠️ 僅找到 {len(snapshots)} 個角色快照，將使用所有找到的角色組成隊伍。")

    members = snapshots[:3]
    active_id = members[0].character_id
    party = PlayerPartySnapshot(members=members, active_character_id=active_id)

    print(
        f"[隊伍資訊] 成員={', '.join(m.character_id for m in members)} | "
        f"團隊血量={party.team_hp:.1f}/{party.team_hp_max:.1f} | 活動角色={party.active_character_id}"
    )
    return party


# =========================================================
# CLI
# =========================================================
def ask_battle_count() -> int:
    while True:
        s = input("請輸入要模擬戰鬥的次數（任一方血量歸零算 1 次）：").strip()
        try:
            n = int(s)
            if n <= 0:
                print("請輸入大於 0 的整數。")
                continue
            return n
        except Exception:
            print("輸入格式錯誤，請輸入整數。")


def ask_confirm(n: int) -> bool:
    s = input(f"確定要開始模擬 {n} 次戰鬥嗎？輸入 Y 開始，其它任意鍵取消：").strip()
    return s.upper() == "Y"


# =========================================================
# Excel helpers (Class maps)
# =========================================================
def _read_excel(df_path: Path, sheet: str) -> pd.DataFrame:
    if not df_path.exists():
        raise FileNotFoundError(f"❌ Excel not found: {df_path}")
    df = pd.read_excel(df_path, sheet_name=sheet)
    df.columns = df.columns.astype(str).str.strip()
    return df


def load_character_class_map(
    data_dir: Path,
    excel_name: str = "Character.xlsx",
    sheet_name: str = "CharacterIndex",
) -> Dict[str, str]:
    """
    讀取 CharacterIndex: CharacterId -> Class
    """
    path = Path(data_dir) / excel_name
    df = _read_excel(path, sheet_name)

    # tolerant column names
    col_id = None
    for c in ["CharacterId", "CharacterID", "character_id"]:
        if c in df.columns:
            col_id = c
            break
    if col_id is None:
        raise ValueError(f"❌ {excel_name}/{sheet_name} missing CharacterId column")

    if "Class" not in df.columns:
        raise ValueError(f"❌ {excel_name}/{sheet_name} missing Class column")

    out: Dict[str, str] = {}
    for _, r in df.iterrows():
        cid = r.get(col_id)
        cls = r.get("Class")
        if pd.isna(cid) or pd.isna(cls):
            continue
        out[str(cid).strip()] = str(cls).strip()
    print(f"✅ Loaded CharacterClassMap: {len(out)}")
    return out


def load_partner_class_map_auto(
    data_dir: Path,
    excel_name: str = "Partner.xlsx",
    candidate_sheets: Tuple[str, ...] = ("PartnerStatStack", "PartnerIndex", "Partner", "PartnerStatType"),
) -> Dict[str, str]:
    """
    嘗試從 Partner.xlsx 的多個 sheet 找到 PartnerId -> Class 的對照表。
    只要 sheet 內有 (PartnerId/PartnerID) 與 Class 欄位就採用。
    """
    path = Path(data_dir) / excel_name
    if not path.exists():
        print(f"⚠️ Partner excel not found: {path} (partner class map will be empty)")
        return {}

    for sheet in candidate_sheets:
        try:
            df = _read_excel(path, sheet)
        except Exception:
            continue

        col_pid = None
        for c in ["PartnerId", "PartnerID", "partner_id"]:
            if c in df.columns:
                col_pid = c
                break
        if col_pid is None or "Class" not in df.columns:
            continue

        out: Dict[str, str] = {}
        for _, r in df.iterrows():
            pid = r.get(col_pid)
            cls = r.get("Class")
            if pd.isna(pid) or pd.isna(cls):
                continue
            out[str(pid).strip()] = str(cls).strip()

        if out:
            print(f"✅ Loaded PartnerClassMap: {len(out)} from {excel_name}/{sheet}")
            return out

    print(f"⚠️ No usable PartnerId/Class mapping found in {excel_name} (partner class map will be empty)")
    return {}


# =========================================================
# AbilitySystem (MVP: Douglas)
# =========================================================
def build_douglas_ability_system() -> Tuple[AbilitySystem, Dict[str, Any]]:
    """
    MVP：先在 code 內硬編 Douglas 的 ability/condition/effect 與 stack curve。
    回傳 (ability_system, debug_info)
    """

    PARTNER_ID = "Douglas"
    ABILITY_ID = "AB_Douglas_FirstTurn_AttackUp"
    COND_GROUP_ID = "CG_Douglas_ClassMatch"
    EFFECT_GROUP_ID = "EG_AttackUp16_1Turn"
    PARTNER_STACK_CURVE_ID = "PartnerAttackIncrease"

    abilities = {
        ABILITY_ID: AbilityDef(
            ability_id=ABILITY_ID,
            trigger_event=TriggerEvent.FirstTurnStart,
            condition_group_id=COND_GROUP_ID,
            effect_group_id=EFFECT_GROUP_ID,
            priority=0,
        )
    }

    condition_groups = {
        COND_GROUP_ID: ConditionGroupDef(
            condition_group_id=COND_GROUP_ID,
            logic=ConditionLogic.AND,
        )
    }

    condition_rows_by_group = {
        COND_GROUP_ID: [
            ConditionRowDef(
                condition_group_id=COND_GROUP_ID,
                row_index=0,
                condition_type=ConditionType.OwnerClassEqualsPartnerClass,
                arg1=None,
                arg2=None,
            )
        ]
    }

    effect_groups = {
        EFFECT_GROUP_ID: EffectGroupDef(
            effect_group_id=EFFECT_GROUP_ID,
            exec_mode=ExecMode.Sequential,
        )
    }

    effect_rows_by_group = {
        EFFECT_GROUP_ID: [
            EffectRowDef(
                effect_group_id=EFFECT_GROUP_ID,
                row_index=0,
                effect_type=AbilityEffectType.AddStatus,
                value1="AttackUp",
                value2=1,  # duration=1 turn
                value_ref_type=ValueRefType.None_,
                value_ref_id=None,
            ),
            EffectRowDef(
                effect_group_id=EFFECT_GROUP_ID,
                row_index=1,
                effect_type=AbilityEffectType.SetStatusParam,
                value1="increase",
                value2=None,  # const not used
                value_ref_type=ValueRefType.PartnerStack,
                value_ref_id=PARTNER_STACK_CURVE_ID,
            ),
        ]
    }

    partner_abilities = {
        PARTNER_ID: [ABILITY_ID]
    }

    partner_stack_curves = {
        PARTNER_ID: {
            PARTNER_STACK_CURVE_ID: [0.08, 0.10, 0.12, 0.14, 0.16]
        }
    }

    system = AbilitySystem(
        abilities=abilities,
        condition_groups=condition_groups,
        condition_rows_by_group=condition_rows_by_group,
        effect_groups=effect_groups,
        effect_rows_by_group=effect_rows_by_group,
        partner_abilities=partner_abilities,
        partner_stack_curves=partner_stack_curves,
        default_max_partner_stack=4,
    )

    debug = {
        "mvp_partner_id": PARTNER_ID,
        "mvp_ability_id": ABILITY_ID,
        "mvp_effect_group_id": EFFECT_GROUP_ID,
        "mvp_curve_id": PARTNER_STACK_CURVE_ID,
    }
    return system, debug


# =========================================================
# Main
# =========================================================
def main() -> None:
    battle_count = ask_battle_count()
    if not ask_confirm(battle_count):
        print("操作已取消。")
        return

    # -------------------------
    # 1) Load party (Phase 1)
    # -------------------------
    party = load_party_snapshots()
    party_character_ids = [m.character_id for m in party.members]

    # -------------------------
    # 2) Load cards
    # -------------------------
    card_repo = CardRepository(data_dir=DATA_DIR, log_level=LogLevel.INFO)
    party_cards, effects_by_card = card_repo.load_cards_for_characters(
        excel_name="Card.xlsx",
        sheet_card="Card",
        sheet_effect="CardEffect",
        character_ids=party_character_ids,
    )
    if not party_cards:
        raise RuntimeError("❌ 隊伍沒有任何可用卡牌，請檢查 Card.xlsx 的篩選條件 (CharacterId) 或內容。")

    ap_costs = sorted(set(int(c.ap_cost) for c in party_cards))
    print(f"[卡牌資訊] 隊伍卡牌數={len(party_cards)} | AP消耗種類={ap_costs}")

    # -------------------------
    # 3) Load monsters
    # -------------------------
    monster_repo = MonsterRepository(data_dir=DATA_DIR, log_level=LogLevel.INFO)
    monster_indexes, monster_base_stats, monster_skills = monster_repo.load_monsters(
        excel_name="Monster.xlsx",
        sheet_index="MonsterIndex",
        sheet_base_stat="MonsterBaseStat",
        sheet_skill="MonsterSkill",
    )

    # -------------------------
    # 4) Reporter
    # -------------------------
    report_name = make_default_report_name(prefix="battle_report")
    reporter = BattleReporter(
        report_dir=REPORT_DIR,
        report_name=report_name,
        enable_event_log=True,
        log_level=LogLevel.INFO,
    )

    # -------------------------
    # 5) Ability: build system + build context from CombatInputPanel
    # -------------------------
    # 5.1) build MVP ability system (Douglas)
    ability_system, ability_debug = build_douglas_ability_system()

    # 5.2) read CombatInputPanel.xlsx
    input_repo = RuntimeInputRepository(data_dir=DATA_DIR, log=True)
    inputs_by_character = input_repo.load_combat_input_panel(
        excel_name="CombatInputPanel.xlsx",
        sheet_name="CombatInputPanel",
    )

    # 5.3) build class maps (CharacterIndex + Partner)
    character_class_by_id = load_character_class_map(
        data_dir=DATA_DIR,
        excel_name="Character.xlsx",
        sheet_name="CharacterIndex",
    )

    partner_class_by_id = load_partner_class_map_auto(
        data_dir=DATA_DIR,
        excel_name="Partner.xlsx",
    )

    ability_context = input_repo.build_ability_context(
        active_character_id=party.active_character_id,
        inputs_by_character=inputs_by_character,
        character_class_by_id=character_class_by_id,
        partner_class_by_id=partner_class_by_id,
        ignore_if_bonus_flag_off=False,
    )

    print(
        "[AbilityContext] "
        f"partner_id={ability_context.get('partner_id')} "
        f"stack={ability_context.get('partner_stack_count')} "
        f"owner_class={ability_context.get('owner_class')} "
        f"partner_class={ability_context.get('partner_class')}"
    )

    # -------------------------
    # 6) Run simulation
    # -------------------------
    config = BattleConfig(
        ap_max=3,
        max_turns=999,
        log_level=LogLevel.INFO,
        stop_when_insufficient_ap=True,
        hand_size=5,
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
        ability_system=ability_system,
        ability_context=ability_context,
    )

    # -------------------------
    # 7) Summary
    # -------------------------
    player_wins = sum(1 for r in results if r.winner == "Player")
    enemy_wins = sum(1 for r in results if r.winner == "Enemy")
    unknown = len(results) - player_wins - enemy_wins

    print("\n=== 模擬結果摘要 ===")
    print(f"總戰鬥次數: {len(results)}")
    print(f"玩家勝利 : {player_wins}")
    print(f"敵人勝利 : {enemy_wins}")
    if unknown > 0:
        print(f"其他結果 : {unknown}")

    for r in results:
        reporter.add_summary(
            battle_index=r.battle_index,
            winner=r.winner,
            turns=r.turns,
            player_hp_end=r.player_hp_end,
            enemies_alive=r.enemies_alive,
        )

    # -------------------------
    # 8) Export Excel report
    # -------------------------
    extra_config = {
        "battle_count": battle_count,
        "ap_max": config.ap_max,
        "max_turns": config.max_turns,
        "stop_when_insufficient_ap": config.stop_when_insufficient_ap,
        "hand_size": config.hand_size,
        "party_members": ",".join(party_character_ids),
        "party_team_hp_max": float(party.team_hp_max),
        "cards_count": len(party_cards),
        "ap_cost_set": ",".join(str(x) for x in ap_costs),
        "monsters_count": len(monster_indexes),
        "enable_event_log": True,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # Ability debug
        "ability_partner_id": ability_context.get("partner_id"),
        "ability_owner_class": ability_context.get("owner_class"),
        "ability_partner_class": ability_context.get("partner_class"),
        "ability_partner_stack_count": ability_context.get("partner_stack_count"),
        **ability_debug,
    }

    out_path = reporter.flush_to_excel(extra_config=extra_config)
    if out_path is None:
        print("⚠️ 報表輸出路徑未設定，已略過 Excel 輸出。")
    else:
        print(f"\n✅ 報表已成功匯出至：{out_path}")

    input("\n按 Enter 鍵結束程式...")


if __name__ == "__main__":
    main()
