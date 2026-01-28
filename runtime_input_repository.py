# runtime_input_repository.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


# ----------------------------
# Helpers
# ----------------------------
def _norm_cell(v: Any) -> Optional[Any]:
    """
    標準化 Excel 儲存格的值：
    - None / NaN / "" / "None" -> None
    - 其他字串 -> strip
    """
    if v is None:
        return None
    # pandas NaN
    try:
        if isinstance(v, float) and pd.isna(v):
            return None
    except Exception:
        pass

    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() == "none":
            return None
        return s
    return v


def _to_int(v: Any, default: int = 0) -> int:
    v = _norm_cell(v)
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    v = _norm_cell(v)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _to_bool(v: Any, default: bool = False) -> bool:
    """
    嘗試將值轉換為布林值。
    支援字串 ("true", "yes", "1") 與數值 (1/0) 的判斷。
    """
    v = _norm_cell(v)
    if v is None:
        return default

    if isinstance(v, bool):
        return v

    if isinstance(v, (int, float)):
        try:
            return bool(int(v))
        except Exception:
            return default

    s = str(v).strip().lower()
    if s in ("true", "t", "yes", "y", "1"):
        return True
    if s in ("false", "f", "no", "n", "0", "none", "nan", ""):
        return False
    return default


def _require_columns(df: pd.DataFrame, required_cols: List[str]) -> None:
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CombatInputPanel missing columns: {missing}")


# ----------------------------
# Dataclasses
# ----------------------------
@dataclass
class FragmentInput:
    fragment_id: str
    level: float = 0.0
    random_stat: Optional[str] = None
    random_value: float = 0.0


@dataclass
class PotentialNodeInput:
    node_id: str
    level: float = 0.0


@dataclass
class CharacterLoadoutInput:
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

    Excel 格式（Block 設計）：
    - 當 'CharacterId' 有值時，視為一個新角色的開始 (Header row)
    - 隨後 'CharacterId' 空白的行視為該角色的列表資料 (List rows)
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
        Returns:
            Dict[character_id, CharacterLoadoutInput]
        """
        path = self.data_dir / excel_name
        if not path.exists():
            raise FileNotFoundError(f"Input panel not found: {path}")

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
        _require_columns(df, required_cols)

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

            # Header row: new character block
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

            # List row: belongs to current block
            if current is None:
                continue

            # Fragment list row
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

            # Equipment list row
            eq_id = _norm_cell(row.get("EquipmentIdList[]"))
            if eq_id is not None:
                current.equipment_ids.append(str(eq_id))

            # Card list row
            card_id = _norm_cell(row.get("CardList[]"))
            if card_id is not None:
                current.card_ids.append(str(card_id))

            # CardAwake list row (append to align, keep your original behavior)
            awake = _norm_cell(row.get("CardAwakeList[]"))
            if awake is not None:
                current.card_awake_flags.append(_to_bool(awake, False))

            # Potential node list row
            node_id = _norm_cell(row.get("PotentialNodeList[]"))
            if node_id is not None:
                node_level = _to_float(row.get("PotentialLevelList[]"), 0.0)
                current.potential_nodes.append(PotentialNodeInput(node_id=str(node_id), level=node_level))

        flush_current()

        if self.log:
            print(f"Loaded CombatInputPanel: {len(inputs)} character blocks")
            for cid, it in list(inputs.items())[:5]:
                print(
                    f" - {cid}: Lv{it.level} Partner={it.partner_id} Stack={it.partner_stack_count} "
                    f"Fragments={len(it.fragments)} Equip={len(it.equipment_ids)} Cards={len(it.card_ids)} "
                    f"Potentials={len(it.potential_nodes)} BonusFlag={it.is_partner_bonus_applied}"
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
        會保證輸出 key 與型別，讓 battle_simulator / ability_system 更穩定。

        Required output keys:
        - partner_id: Optional[str]
        - partner_stack_count: int
        - owner_class: Optional[str]
        - partner_class: Optional[str]
        - runtime_mod: Dict[str, Any]
        - statuses: List[Any]
        - extra_ctx: Dict[str, Any]
        """
        if active_character_id not in inputs_by_character:
            raise KeyError(f"active_character_id not found in input panel: {active_character_id}")

        inp = inputs_by_character[active_character_id]

        # Base context (always present)
        ctx: Dict[str, Any] = {
            "partner_id": None,
            "partner_stack_count": 0,
            "owner_class": None,
            "partner_class": None,
            "runtime_mod": {},
            "statuses": [],
            "extra_ctx": {},
        }

        partner_id = inp.partner_id
        if not partner_id:
            ctx["extra_ctx"] = {"reason": "NoPartnerEquipped"}
            if self.log:
                print("[AbilityContext] No partner equipped on active character.")
            return ctx

        if ignore_if_bonus_flag_off and (not inp.is_partner_bonus_applied):
            ctx["extra_ctx"] = {"reason": "PartnerBonusFlagOff"}
            if self.log:
                print("[AbilityContext] Partner equipped but bonus flag is OFF. Ignored by config.")
            return ctx

        owner_class = character_class_by_id.get(active_character_id)
        partner_class = partner_class_by_id.get(partner_id)

        ctx["partner_id"] = str(partner_id)
        ctx["partner_stack_count"] = int(inp.partner_stack_count)
        ctx["owner_class"] = owner_class
        ctx["partner_class"] = partner_class
        ctx["extra_ctx"] = {
            "partner_level": float(inp.partner_level),
            "is_partner_bonus_applied": bool(inp.is_partner_bonus_applied),
            "affection_level": int(inp.affection_level),
        }

        # Helpful logs for common "not triggered" causes
        if self.log:
            if owner_class is None:
                print(
                    f"[AbilityContext][Warn] owner_class not found for CharacterId={active_character_id}. "
                    "Check Character.xlsx/CharacterIndex: Class column and CharacterId match."
                )
            if partner_class is None:
                print(
                    f"[AbilityContext][Warn] partner_class not found for PartnerId={partner_id}. "
                    "Check Partner.xlsx: a sheet contains PartnerId + Class mapping."
                )
            print(
                "[AbilityContext] "
                f"partner_id={ctx['partner_id']} stack={ctx['partner_stack_count']} "
                f"owner_class={ctx['owner_class']} partner_class={ctx['partner_class']} "
                f"bonus_flag={ctx['extra_ctx']['is_partner_bonus_applied']}"
            )

        return ctx
