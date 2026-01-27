# runtime_input_repository.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ----------------------------
# Helpers
# ----------------------------
def _norm_cell(v: Any) -> Optional[Any]:
    """
    標準化 Excel 儲存格的值。
    將 None, "None", 空字串統一視為 None，方便後續處理。
    """
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() == "none":
            return None
        return s
    return v


def _to_int(v: Any, default: int = 0) -> int:
    """嘗試將值轉換為整數，若失敗則回傳預設值。"""
    v = _norm_cell(v)
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    """嘗試將值轉換為浮點數，若失敗則回傳預設值。"""
    v = _norm_cell(v)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _to_bool(v, default: bool = False) -> bool:
    """
    嘗試將值轉換為布林值。
    支援字串 ("true", "yes", "1") 與數值 (1/0) 的判斷。
    """
    # None / NaN / empty -> default
    try:
        import pandas as pd
        if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
            return default
    except Exception:
        # if pandas not available or pd.isna fails, fallback checks
        if v is None:
            return default

    # already bool
    if isinstance(v, bool):
        return v

    # numeric-like
    if isinstance(v, (int, float)):
        return bool(int(v))

    # string-like
    s = str(v).strip().lower()
    if s in ("true", "t", "yes", "y", "1"):
        return True
    if s in ("false", "f", "no", "n", "0", "", "none", "nan"):
        return False

    # unknown -> default
    return default



# ----------------------------
# Dataclasses
# ----------------------------
@dataclass
class FragmentInput:
    """
    碎片 (Fragment) 輸入資料結構。
    對應 Excel 中的 FragmentIdList, FragmentLevelList 等欄位。
    """
    fragment_id: str
    level: float = 0.0
    random_stat: Optional[str] = None
    random_value: float = 0.0


@dataclass
class PotentialNodeInput:
    """
    潛能節點 (Potential Node) 輸入資料結構。
    """
    node_id: str
    level: float = 0.0


@dataclass
class CharacterLoadoutInput:
    """
    單一角色的完整戰鬥配置輸入。
    包含等級、夥伴、好感度，以及列表式的裝備、卡牌、碎片、潛能等資訊。
    """
    character_id: str
    level: float

    partner_id: Optional[str] = None
    partner_level: float = 0.0
    partner_stack_count: int = 0
    is_partner_bonus_applied: bool = False

    affection_level: int = 0

    fragments: List[FragmentInput] = field(default_factory=list)
    equipment_ids: List[str] = field(default_factory=list)
    card_ids: List[str] = field(default_factory=list)
    card_awake_flags: List[bool] = field(default_factory=list)
    potential_nodes: List[PotentialNodeInput] = field(default_factory=list)

    note: Optional[str] = None


# ----------------------------
# Repository
# ----------------------------
class RuntimeInputRepository:
    """
    負責讀取 CombatInputPanel.xlsx 並解析為結構化資料。

    Excel 格式說明：
    - 採用區塊式 (Block) 設計。
    - 當 'CharacterId' 有值時，視為一個新角色的開始 (Header row)。
    - 隨後的行若 'CharacterId' 為空，則視為該角色的列表資料 (List rows)，例如裝備列表、卡牌列表等。
    """

    def __init__(self, data_dir: Path, log: bool = True) -> None:
        self.data_dir = Path(data_dir)
        self.log = log

    def load_combat_input_panel(
        self,
        excel_name: str = "CombatInputPanel.xlsx",
        sheet_name: str = "CombatInputPanel",
    ) -> Dict[str, CharacterLoadoutInput]:
        """
        讀取 Excel 並解析所有角色的配置。

        Returns:
            Dict[character_id, CharacterLoadoutInput]
        """
        path = self.data_dir / excel_name
        if not path.exists():
            raise FileNotFoundError(f"❌ Input panel not found: {path}")

        df = pd.read_excel(path, sheet_name=sheet_name)
        df.columns = df.columns.astype(str).str.strip()

        required_cols = [
            "CharacterId",
            "Level",
            "PartnerId",
            "PartnerLevel",
            "PartnerStackCount",
            "IsPartnerBonusApplied",
            "AffectionLevel",
            "FragmentIdList[]",
            "FragmentLevelList[]",
            "FragmentRandomStatList[]",
            "FragmentRandomValueList[]",
            "EquipmentIdList[]",
            "CardList[]",
            "CardAwakeList[]",
            "PotentialNodeList[]",
            "PotentialLevelList[]",
            "Note",
        ]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"❌ CombatInputPanel missing columns: {missing}")

        inputs: Dict[str, CharacterLoadoutInput] = {}
        current: Optional[CharacterLoadoutInput] = None

        def flush_current() -> None:
            nonlocal current
            if current is None:
                return
            inputs[current.character_id] = current
            current = None

        for _, row in df.iterrows():
            char_id = _norm_cell(row.get("CharacterId"))

            # 當 CharacterId 有值時，表示一個新角色的區塊開始
            if char_id is not None:
                flush_current()

                level = _to_float(row.get("Level"), 1.0)
                partner_id = _norm_cell(row.get("PartnerId"))
                partner_level = _to_float(row.get("PartnerLevel"), 0.0)
                partner_stack_count = _to_int(row.get("PartnerStackCount"), 0)
                is_partner_bonus_applied = _to_bool(row.get("IsPartnerBonusApplied"), False)
                affection_level = _to_int(row.get("AffectionLevel"), 0)
                note = _norm_cell(row.get("Note"))

                current = CharacterLoadoutInput(
                    character_id=str(char_id),
                    level=level,
                    partner_id=str(partner_id) if partner_id is not None else None,
                    partner_level=partner_level,
                    partner_stack_count=partner_stack_count,
                    is_partner_bonus_applied=is_partner_bonus_applied,
                    affection_level=affection_level,
                    note=str(note) if note is not None else None,
                )

            # 若 CharacterId 為空，則視為當前角色的列表資料 (List rows)
            if current is None:
                continue

            # 解析碎片列表 (Fragment list row)
            frag_id = _norm_cell(row.get("FragmentIdList[]"))
            if frag_id is not None:
                frag_level = _to_float(row.get("FragmentLevelList[]"), 0.0)
                rnd_stat = _norm_cell(row.get("FragmentRandomStatList[]"))
                rnd_val = _to_float(row.get("FragmentRandomValueList[]"), 0.0)
                current.fragments.append(
                    FragmentInput(
                        fragment_id=str(frag_id),
                        level=frag_level,
                        random_stat=str(rnd_stat) if rnd_stat is not None else None,
                        random_value=rnd_val,
                    )
                )

            # 解析裝備列表 (Equipment list row)
            eq_id = _norm_cell(row.get("EquipmentIdList[]"))
            if eq_id is not None:
                current.equipment_ids.append(str(eq_id))

            # 解析卡牌列表 (Card list row)
            card_id = _norm_cell(row.get("CardList[]"))
            if card_id is not None:
                current.card_ids.append(str(card_id))

            # 解析卡牌覺醒列表 (CardAwake list row) - 透過 append 對齊
            awake = _norm_cell(row.get("CardAwakeList[]"))
            if awake is not None:
                current.card_awake_flags.append(_to_bool(awake, False))

            # 解析潛能節點列表 (Potential node list row)
            node_id = _norm_cell(row.get("PotentialNodeList[]"))
            if node_id is not None:
                node_level = _to_float(row.get("PotentialLevelList[]"), 0.0)
                current.potential_nodes.append(
                    PotentialNodeInput(node_id=str(node_id), level=node_level)
                )

        flush_current()

        if self.log:
            print(f"✅ Loaded CombatInputPanel: {len(inputs)} character blocks")
            for cid, it in list(inputs.items())[:5]:
                print(
                    f"  - {cid}: Lv{it.level} Partner={it.partner_id} Stack={it.partner_stack_count} "
                    f"Fragments={len(it.fragments)} Equip={len(it.equipment_ids)} Cards={len(it.card_ids)} "
                    f"Potentials={len(it.potential_nodes)}"
                )

        return inputs

    # -------------------------------------------------------
    # AbilityContext builder (what battle_simulator needs)
    # -------------------------------------------------------
    def build_ability_context(
        self,
        active_character_id: str,
        inputs_by_character: Dict[str, CharacterLoadoutInput],
        character_class_by_id: Dict[str, str],
        partner_class_by_id: Dict[str, str],
        *,
        ignore_if_bonus_flag_off: bool = False,
    ) -> Dict[str, Any]:
        """
        建立 AbilitySystem 所需的 context (上下文)。

        主要負責將 Excel 輸入的夥伴資訊、堆疊層數、職業對照等資訊，
        轉換為 AbilitySystem 可理解的字典格式。

        Args:
            active_character_id: 當前戰鬥的主要角色 ID
            inputs_by_character: 從 load_combat_input_panel 載入的輸入資料
            character_class_by_id: 角色 ID -> 職業對照表
            partner_class_by_id: 夥伴 ID -> 職業對照表
            ignore_if_bonus_flag_off: 若 Excel 中 IsPartnerBonusApplied 為 False，是否忽略夥伴加成
        """
        if active_character_id not in inputs_by_character:
            raise KeyError(f"❌ active_character_id not found in input panel: {active_character_id}")

        inp = inputs_by_character[active_character_id]
        partner_id = inp.partner_id

        if not partner_id:
            return {
                "partner_id": None,
                "partner_stack_count": 0,
                "owner_class": None,
                "partner_class": None,
                "extra_ctx": {"reason": "NoPartnerEquipped"},
            }

        if ignore_if_bonus_flag_off and (not inp.is_partner_bonus_applied):
            return {
                "partner_id": None,
                "partner_stack_count": 0,
                "owner_class": None,
                "partner_class": None,
                "extra_ctx": {"reason": "PartnerBonusFlagOff"},
            }

        owner_class = character_class_by_id.get(active_character_id)
        partner_class = partner_class_by_id.get(partner_id)

        return {
            "partner_id": partner_id,
            "partner_stack_count": int(inp.partner_stack_count),
            "owner_class": owner_class,
            "partner_class": partner_class,
            "extra_ctx": {
                "partner_level": float(inp.partner_level),
                "is_partner_bonus_applied": bool(inp.is_partner_bonus_applied),
                "affection_level": int(inp.affection_level),
            },
        }
