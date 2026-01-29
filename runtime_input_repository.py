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
    if v is None:
        return None
    try:
        if isinstance(v, float) and pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() in ("none", "nan"):
            return None
        return s
    return v


def _to_float(v: Any, default: float = 0.0) -> float:
    v = _norm_cell(v)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    v = _norm_cell(v)
    if v is None:
        return default
    try:
        return int(float(v))
    except Exception:
        return default


def _to_bool(v: Any, default: bool = False) -> bool:
    v = _norm_cell(v)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "t", "yes", "y", "1"):
            return True
        if s in ("false", "f", "no", "n", "0", "none", "nan", ""):
            return False
    return default


def _split_csv(v: Any) -> List[str]:
    v = _norm_cell(v)
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if _norm_cell(x) is not None]
    s = str(v).strip()
    if s == "":
        return []
    return [x.strip() for x in s.split(",") if x.strip() != ""]


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

    # IMPORTANT: used to decide which PartnerStack value to apply
    partner_stack_count: int = 0

    affection_level: int = 0

    # NEW (optional): used by AbilitySystem condition OwnerClassEqualsPartnerClass
    owner_class: Optional[str] = None
    partner_class: Optional[str] = None

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
        path = self.data_dir / excel_name
        if not path.exists():
            raise FileNotFoundError(f"Input panel not found: {path}")

        df = pd.read_excel(path, sheet_name=sheet_name)
        df.columns = df.columns.astype(str).str.strip()

        # NOTE: removed IsPartnerBonusApplied
        required_cols = [
            "CharacterId",
            "Level",
            "PartnerId",
            "PartnerLevel",
            "PartnerStackCount",
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

        # Optional columns (if present)
        has_owner_class = "OwnerClass" in df.columns
        has_partner_class = "PartnerClass" in df.columns

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
                affection_level = _to_int(row.get("AffectionLevel"), 0)
                note = _norm_cell(row.get("Note"))

                owner_class = _norm_cell(row.get("OwnerClass")) if has_owner_class else None
                partner_class = _norm_cell(row.get("PartnerClass")) if has_partner_class else None

                current = CharacterLoadoutInput(
                    character_id=str(char_id),
                    level=float(level),
                    partner_id=str(partner_id) if partner_id is not None else None,
                    partner_level=float(partner_level),
                    partner_stack_count=int(partner_stack_count),
                    affection_level=int(affection_level),
                    owner_class=str(owner_class) if owner_class is not None else None,
                    partner_class=str(partner_class) if partner_class is not None else None,
                    note=str(note) if note is not None else None,
                )
                continue

            # List rows (belong to current block)
            if current is None:
                continue

            frag_ids = _split_csv(row.get("FragmentIdList[]"))
            frag_lvls = _split_csv(row.get("FragmentLevelList[]"))
            frag_rstats = _split_csv(row.get("FragmentRandomStatList[]"))
            frag_rvals = _split_csv(row.get("FragmentRandomValueList[]"))

            # fragments
            if frag_ids:
                for i, fid in enumerate(frag_ids):
                    lvl = float(frag_lvls[i]) if i < len(frag_lvls) and frag_lvls[i] != "" else 0.0
                    rstat = frag_rstats[i] if i < len(frag_rstats) and frag_rstats[i] != "" else None
                    rval = float(frag_rvals[i]) if i < len(frag_rvals) and frag_rvals[i] != "" else 0.0
                    current.fragments.append(
                        FragmentInput(fragment_id=str(fid), level=float(lvl), random_stat=rstat, random_value=float(rval))
                    )

            # equipment
            eq_ids = _split_csv(row.get("EquipmentIdList[]"))
            for eid in eq_ids:
                current.equipment_ids.append(str(eid))

            # cards
            card_ids = _split_csv(row.get("CardList[]"))
            card_awake = _split_csv(row.get("CardAwakeList[]"))
            for i, cid in enumerate(card_ids):
                current.card_ids.append(str(cid))
                flag = _to_bool(card_awake[i], False) if i < len(card_awake) else False
                current.card_awake_flags.append(flag)

            # potential
            node_ids = _split_csv(row.get("PotentialNodeList[]"))
            node_lvls = _split_csv(row.get("PotentialLevelList[]"))
            for i, nid in enumerate(node_ids):
                lvl = float(node_lvls[i]) if i < len(node_lvls) and node_lvls[i] != "" else 0.0
                current.potential_nodes.append(PotentialNodeInput(node_id=str(nid), level=float(lvl)))

        flush_current()

        if self.log:
            print(f"[RuntimeInputRepository] Loaded inputs: {len(inputs)}")
        return inputs
