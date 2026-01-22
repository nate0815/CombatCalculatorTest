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
    """Normalize excel cell values: treat None/'None'/'' as None."""
    if v is None:
        return None
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


def _to_bool(v, default: bool = False) -> bool:
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
    Parse CombatInputPanel.xlsx (block + list rows format) into structured inputs.
    """

    def __init__(self, data_dir: Path, log: bool = True) -> None:
        self.data_dir = Path(data_dir)
        self.log = log

    def load_combat_input_panel(
        self,
        excel_name: str = "CombatInputPanel.xlsx",
        sheet_name: str = "CombatInputPanel",
    ) -> Dict[str, CharacterLoadoutInput]:
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

            # New block starts when CharacterId has value
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

            # List rows belong to current block
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

            # CardAwake list row (align by append; optional)
            awake = _norm_cell(row.get("CardAwakeList[]"))
            if awake is not None:
                current.card_awake_flags.append(_to_bool(awake, False))

            # Potential node list row
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
        Build ability_context for AbilitySystem.

        Required by current AbilitySystem MVP:
        - partner_id
        - partner_stack_count
        - owner_class
        - partner_class
        - extra_ctx (optional)

        character_class_by_id: CharacterId -> Class
        partner_class_by_id: PartnerId -> Class
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
