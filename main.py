# main.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List

import pandas as pd

from battle_reporter import BattleReporter, make_default_report_name
from battle_simulator import BattleConfig, BattleSimulator
from card_repository import CardRepository
from monster_repository import MonsterRepository
from models import LogLevel, PlayerPartySnapshot

# NEW: runtime input repo
from runtime_input_repository import RuntimeInputRepository

# Ability system
from ability_models import (
    AbilityDef,
    AbilityEffectType,
    ApplyPhase,
    ConditionGroupDef,
    ConditionLogic,
    ConditionRowDef,
    ConditionType,
    DurationType,
    EffectGroupDef,
    EffectRowDef,
    ExecMode,
    SourceType,
    TargetScope,
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
# Excel helpers
# =========================================================
def _read_excel(df_path: Path, sheet: str) -> pd.DataFrame:
    if not df_path.exists():
        raise FileNotFoundError(f"❌ Excel not found: {df_path}")
    df = pd.read_excel(df_path, sheet_name=sheet)
    df.columns = df.columns.astype(str).str.strip()
    return df


def _to_bool(v: Any, default: bool = True) -> bool:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y"):
        return True
    if s in ("0", "false", "f", "no", "n"):
        return False
    return default


def _get_col(df: pd.DataFrame, candidates: Tuple[str, ...], required: bool = True) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    if required:
        raise ValueError(f"❌ Missing required columns: {candidates}. Existing={list(df.columns)}")
    return None


def load_character_class_map(
    data_dir: Path,
    excel_name: str = "Character.xlsx",
    sheet_name: str = "CharacterIndex",
) -> Dict[str, str]:
    """CharacterIndex: CharacterId -> Class"""
    path = Path(data_dir) / excel_name
    df = _read_excel(path, sheet_name)

    col_id = _get_col(df, ("CharacterId", "CharacterID", "character_id"))
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

        col_pid = _get_col(df, ("PartnerId", "PartnerID", "partner_id"), required=False)
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
# Ability: load from menus
# =========================================================
def load_partner_stack_curves(
    data_dir: Path,
    excel_name: str = "Partner.xlsx",
    sheet_name: str = "PartnerStatStack",
) -> Dict[str, Dict[str, List[float]]]:
    """
    讀 Partner.xlsx / PartnerStatStack (wide format)：
    PartnerId + StatTypeId + Stack0Value..Stack4Value
    -> partner_stack_curves[PartnerId][StatTypeId] = [v0..v4]
    """
    path = Path(data_dir) / excel_name
    if not path.exists():
        print(f"⚠️ Partner excel not found: {path} (partner stack curves will be empty)")
        return {}

    df = _read_excel(path, sheet_name)

    col_pid = _get_col(df, ("PartnerId", "PartnerID", "partner_id"))
    col_stat = _get_col(df, ("StatTypeId", "StatTypeID", "stat_type_id", "StatType"))

    # stack columns (keep tolerant)
    stack_cols = []
    for i in range(0, 20):
        c1 = f"Stack{i}Value"
        c2 = f"Stack{i}"
        if c1 in df.columns:
            stack_cols.append(c1)
        elif c2 in df.columns:
            stack_cols.append(c2)
        else:
            # stop when sequence breaks (assume contiguous)
            if i <= 4:
                # still allow 0~4 missing to raise later
                pass
            # do not break; we want to keep scanning for Stack0Value..Stack4Value at least
    if not stack_cols:
        # fallback common 0~4
        for i in range(0, 5):
            c = f"Stack{i}Value"
            if c in df.columns:
                stack_cols.append(c)

    if not stack_cols:
        print(f"⚠️ No Stack columns found in {excel_name}/{sheet_name}. partner stack curves will be empty.")
        return {}

    out: Dict[str, Dict[str, List[float]]] = {}
    for _, r in df.iterrows():
        pid = r.get(col_pid)
        st = r.get(col_stat)
        if pd.isna(pid) or pd.isna(st):
            continue

        values: List[float] = []
        for c in stack_cols:
            v = r.get(c)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                values.append(0.0)
            else:
                try:
                    values.append(float(v))
                except Exception:
                    values.append(0.0)

        pid_s = str(pid).strip()
        st_s = str(st).strip()
        out.setdefault(pid_s, {})[st_s] = values

    print(f"✅ Loaded PartnerStackCurves: partners={len(out)}")
    return out


def build_ability_system_from_menus(
    data_dir: Path,
    ability_excel: str = "AbilityMenu.xlsx",
    condition_excel: str = "ConditionMenu.xlsx",
    effect_excel: str = "EffectMenu.xlsx",
    ability_sheet_catalog: str = "AbilityCatalog",
    ability_sheet_partner: str = "PartnerAbility",
    cond_sheet_group: str = "ConditionGroup",
    cond_sheet_row: str = "ConditionRow",
    eff_sheet_group: str = "EffectGroup",
    eff_sheet_row: str = "EffectRow",
) -> Tuple[AbilitySystem, Dict[str, Any]]:
    """
    從三套 Menu Excel 讀入並建立 AbilitySystem。
    """
    # -------------------------
    # 1) AbilityCatalog
    # -------------------------
    ability_path = Path(data_dir) / ability_excel
    df_ability = _read_excel(ability_path, ability_sheet_catalog)

    col_ability_id = _get_col(df_ability, ("AbilityId", "AbilityID", "ability_id"))
    col_trigger = _get_col(df_ability, ("TriggerEvent", "Trigger", "trigger_event"))
    col_cond_gid = _get_col(df_ability, ("ConditionGroupId", "ConditionGroupID", "condition_group_id"), required=False)
    col_eff_gid = _get_col(df_ability, ("EffectGroupId", "EffectGroupID", "effect_group_id"))
    col_pri = _get_col(df_ability, ("Priority", "priority"), required=False)

    col_apply_phase = _get_col(df_ability, ("ApplyPhase", "AbilityLayer", "ExecutionPhase"), required=False)
    col_source_type = _get_col(df_ability, ("SourceType", "source_type"), required=False)
    col_enabled = _get_col(df_ability, ("Enabled", "enabled", "IsEnabled"), required=False)

    abilities: Dict[str, AbilityDef] = {}
    skipped = 0
    for _, r in df_ability.iterrows():
        aid = r.get(col_ability_id)
        trig_raw = r.get(col_trigger)
        if pd.isna(aid) or pd.isna(trig_raw):
            continue

        enabled = _to_bool(r.get(col_enabled), default=True) if col_enabled else True
        if not enabled:
            continue

        # trigger
        try:
            trig = TriggerEvent(str(trig_raw).strip())
        except Exception:
            skipped += 1
            continue

        # condition group
        cond_gid = None
        if col_cond_gid:
            v = r.get(col_cond_gid)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                cond_gid = s if s else None

        # effect group
        eff_gid = str(r.get(col_eff_gid)).strip()

        # priority
        pri = 0
        if col_pri:
            v = r.get(col_pri)
            try:
                pri = int(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else 0
            except Exception:
                pri = 0

        # apply_phase
        ap = ApplyPhase.RUNTIME
        if col_apply_phase:
            v = r.get(col_apply_phase)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                try:
                    ap = ApplyPhase(s)
                except Exception:
                    ap = ApplyPhase.RUNTIME

        # source_type
        st = None
        if col_source_type:
            v = r.get(col_source_type)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                try:
                    st = SourceType(s)
                except Exception:
                    st = None

        aid_s = str(aid).strip()
        abilities[aid_s] = AbilityDef(
            ability_id=aid_s,
            trigger_event=trig,
            condition_group_id=cond_gid,
            effect_group_id=eff_gid,
            priority=pri,
            apply_phase=ap,
            source_type=st,
            enabled=True,
        )

    print(f"✅ Loaded AbilityCatalog: {len(abilities)} (skipped invalid triggers={skipped})")

    # -------------------------
    # 2) PartnerAbility binding
    # -------------------------
    df_bind = _read_excel(ability_path, ability_sheet_partner)
    col_pid = _get_col(df_bind, ("PartnerId", "PartnerID", "partner_id"))
    col_aid = _get_col(df_bind, ("AbilityId", "AbilityID", "ability_id"))
    col_b_enabled = _get_col(df_bind, ("Enabled", "enabled", "IsEnabled"), required=False)

    partner_abilities: Dict[str, List[str]] = {}
    for _, r in df_bind.iterrows():
        pid = r.get(col_pid)
        aid = r.get(col_aid)
        if pd.isna(pid) or pd.isna(aid):
            continue

        enabled = _to_bool(r.get(col_b_enabled), default=True) if col_b_enabled else True
        if not enabled:
            continue

        pid_s = str(pid).strip()
        aid_s = str(aid).strip()

        # only keep abilities that exist & enabled
        if aid_s not in abilities:
            continue

        partner_abilities.setdefault(pid_s, []).append(aid_s)

    print(f"✅ Loaded PartnerAbility: {sum(len(v) for v in partner_abilities.values())} bindings")

    # -------------------------
    # 3) Conditions
    # -------------------------
    cond_path = Path(data_dir) / condition_excel
    df_cg = _read_excel(cond_path, cond_sheet_group)
    df_cr = _read_excel(cond_path, cond_sheet_row)

    col_gid = _get_col(df_cg, ("ConditionGroupId", "ConditionGroupID", "condition_group_id"))
    col_logic = _get_col(df_cg, ("Logic", "logic"), required=False)

    condition_groups: Dict[str, ConditionGroupDef] = {}
    for _, r in df_cg.iterrows():
        gid = r.get(col_gid)
        if pd.isna(gid):
            continue
        gid_s = str(gid).strip()
        logic = ConditionLogic.AND
        if col_logic:
            v = r.get(col_logic)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                try:
                    logic = ConditionLogic(s)
                except Exception:
                    logic = ConditionLogic.AND

        condition_groups[gid_s] = ConditionGroupDef(condition_group_id=gid_s, logic=logic)

    col_r_gid = _get_col(df_cr, ("ConditionGroupId", "ConditionGroupID", "condition_group_id"))
    col_type = _get_col(df_cr, ("ConditionType", "condition_type"))
    col_p1 = _get_col(df_cr, ("Param1", "Arg1", "arg1"), required=False)
    col_p2 = _get_col(df_cr, ("Param2", "Arg2", "arg2"), required=False)
    col_p3 = _get_col(df_cr, ("Param3", "Arg3", "arg3"), required=False)
    col_p4 = _get_col(df_cr, ("Param4", "Arg4", "arg4"), required=False)

    condition_rows_by_group: Dict[str, List[ConditionRowDef]] = {}
    for idx, r in df_cr.iterrows():
        gid = r.get(col_r_gid)
        ctype_raw = r.get(col_type)
        if pd.isna(gid) or pd.isna(ctype_raw):
            continue

        gid_s = str(gid).strip()
        try:
            ctype = ConditionType(str(ctype_raw).strip())
        except Exception:
            continue

        def _opt_str(col: Optional[str]) -> Optional[str]:
            if not col:
                return None
            v = r.get(col)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            s = str(v).strip()
            return s if s else None

        row = ConditionRowDef(
            condition_group_id=gid_s,
            row_index=len(condition_rows_by_group.get(gid_s, [])),
            condition_type=ctype,
            arg1=_opt_str(col_p1),
            arg2=_opt_str(col_p2),
            arg3=_opt_str(col_p3),
            arg4=_opt_str(col_p4),
        )
        condition_rows_by_group.setdefault(gid_s, []).append(row)

    print(f"✅ Loaded Conditions: groups={len(condition_groups)}, rows={sum(len(v) for v in condition_rows_by_group.values())}")

    # -------------------------
    # 4) Effects
    # -------------------------
    eff_path = Path(data_dir) / effect_excel
    df_eg = _read_excel(eff_path, eff_sheet_group)
    df_er = _read_excel(eff_path, eff_sheet_row)

    col_egid = _get_col(df_eg, ("EffectGroupId", "EffectGroupID", "effect_group_id"))
    col_mode = _get_col(df_eg, ("ExecMode", "ExecutionMode", "exec_mode"), required=False)

    effect_groups: Dict[str, EffectGroupDef] = {}
    for _, r in df_eg.iterrows():
        gid = r.get(col_egid)
        if pd.isna(gid):
            continue
        gid_s = str(gid).strip()
        mode = ExecMode.Sequential
        if col_mode:
            v = r.get(col_mode)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                try:
                    mode = ExecMode(s)
                except Exception:
                    mode = ExecMode.Sequential
        effect_groups[gid_s] = EffectGroupDef(effect_group_id=gid_s, exec_mode=mode)

    col_er_gid = _get_col(df_er, ("EffectGroupId", "EffectGroupID", "effect_group_id"))
    col_er_type = _get_col(df_er, ("EffectType", "effect_type"))
    col_v1 = _get_col(df_er, ("Value1", "value1"), required=False)
    col_v2 = _get_col(df_er, ("Value2", "value2"), required=False)
    col_vrt = _get_col(df_er, ("ValueRefType", "value_ref_type"), required=False)
    col_vrid = _get_col(df_er, ("ValueRefId", "ValueRefID", "value_ref_id"), required=False)

    # optional new columns
    col_scope = _get_col(df_er, ("TargetScope", "target_scope"), required=False)
    col_dt = _get_col(df_er, ("DurationType", "duration_type"), required=False)
    col_dv = _get_col(df_er, ("DurationValue", "duration_value"), required=False)

    effect_rows_by_group: Dict[str, List[EffectRowDef]] = {}
    for _, r in df_er.iterrows():
        gid = r.get(col_er_gid)
        etype_raw = r.get(col_er_type)
        if pd.isna(gid) or pd.isna(etype_raw):
            continue

        gid_s = str(gid).strip()
        try:
            etype = AbilityEffectType(str(etype_raw).strip())
        except Exception:
            continue

        def _opt_str2(col: Optional[str]) -> Optional[str]:
            if not col:
                return None
            v = r.get(col)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            s = str(v).strip()
            return s if s else None

        v1 = _opt_str2(col_v1)
        v2f: Optional[float] = None
        if col_v2:
            v = r.get(col_v2)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                try:
                    v2f = float(v)
                except Exception:
                    v2f = None

        vrt = ValueRefType.None_
        if col_vrt:
            v = r.get(col_vrt)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                try:
                    vrt = ValueRefType(s)
                except Exception:
                    vrt = ValueRefType.None_

        vrid = _opt_str2(col_vrid)

        # optional target/duration (read but ability_system may ignore)
        scope = None
        if col_scope:
            v = _opt_str2(col_scope)
            if v:
                try:
                    scope = TargetScope(v)
                except Exception:
                    scope = None

        dty = None
        if col_dt:
            v = _opt_str2(col_dt)
            if v:
                try:
                    dty = DurationType(v)
                except Exception:
                    dty = None

        dval = None
        if col_dv:
            v = r.get(col_dv)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                try:
                    dval = int(v)
                except Exception:
                    dval = None

        row = EffectRowDef(
            effect_group_id=gid_s,
            row_index=len(effect_rows_by_group.get(gid_s, [])),
            effect_type=etype,
            value1=v1,
            value2=v2f,
            value_ref_type=vrt,
            value_ref_id=vrid,
            target_scope=scope,
            duration_type=dty,
            duration_value=dval,
        )
        effect_rows_by_group.setdefault(gid_s, []).append(row)

    print(f"✅ Loaded Effects: groups={len(effect_groups)}, rows={sum(len(v) for v in effect_rows_by_group.values())}")

    # -------------------------
    # 5) Partner stack curves (keep old table as-is)
    # -------------------------
    partner_stack_curves = load_partner_stack_curves(
        data_dir=data_dir,
        excel_name="Partner.xlsx",
        sheet_name="PartnerStatStack",
    )

    # -------------------------
    # 6) Build system
    # -------------------------
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
        "ability_excel": ability_excel,
        "condition_excel": condition_excel,
        "effect_excel": effect_excel,
        "ability_count": len(abilities),
        "condition_group_count": len(condition_groups),
        "condition_row_count": sum(len(v) for v in condition_rows_by_group.values()),
        "effect_group_count": len(effect_groups),
        "effect_row_count": sum(len(v) for v in effect_rows_by_group.values()),
        "partner_binding_count": sum(len(v) for v in partner_abilities.values()),
        "partner_stack_partner_count": len(partner_stack_curves),
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
    # 5.1) load ability system from menus
    ability_system, ability_debug = build_ability_system_from_menus(data_dir=DATA_DIR)

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
        # Ability context
        "ability_partner_id": ability_context.get("partner_id"),
        "ability_owner_class": ability_context.get("owner_class"),
        "ability_partner_class": ability_context.get("partner_class"),
        "ability_partner_stack_count": ability_context.get("partner_stack_count"),
        # Ability debug
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
