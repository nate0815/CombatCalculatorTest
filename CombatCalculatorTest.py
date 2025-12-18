# CombatCalculatorTest.py
import pandas as pd
from pathlib import Path

# =========================================================
# Path & Loader
# =========================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Data"


def load_sheet(excel_name: str, sheet_name: str) -> pd.DataFrame:
    """
    Load a specific sheet from an Excel file inside Data folder.
    """
    path = DATA_DIR / excel_name
    if not path.exists():
        raise FileNotFoundError(f"❌ Excel file not found: {path}")

    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
    except ValueError:
        raise ValueError(f"❌ Sheet '{sheet_name}' not found in {excel_name}")

    print(f"✅ Loaded {excel_name} / {sheet_name} ({len(df)} rows)")
    return df


# =========================================================
# Load required tables (Phase 1 only)
# =========================================================

character_index_df = load_sheet(
    "Character.xlsx", "CharacterIndex"
)

base_stat_df = load_sheet(
    "Character.xlsx", "CharacterBaseStatByLevel"
)

combat_input_df = load_sheet(
    "CombatInputPanel.xlsx", "CombatInputPanel"
)

equipment_df = load_sheet(
    "Equipment.xlsx", "Equipment"
)


# =========================================================
# Core Calculation (Phase 1: Final ATK / DEF / HP)
# =========================================================

def calc_final_base_stats(character_id: str):
    """
    Phase 1 calculation:
    Final ATK / DEF / HP
    (Only Base Stat + Equipment Main Flat)
    """

    # -----------------------------------------------------
    # 1. Combat input
    # -----------------------------------------------------
    input_row = combat_input_df[
        combat_input_df["CharacterId"] == character_id
    ]

    if input_row.empty:
        print(f"⚠️ No combat input found for {character_id}")
        return None

    input_row = input_row.iloc[0]
    level = input_row["Level"]
    equipment_id = input_row["EquipmentIdList[]"]

    # -----------------------------------------------------
    # 2. Base stat lookup
    # -----------------------------------------------------
    base_row = base_stat_df[
        (base_stat_df["CharacterId"] == character_id) &
        (base_stat_df["Level"] == level)
    ]

    if base_row.empty:
        print(f"❌ Base stat not found: {character_id} Lv{level}")
        return None

    base_row = base_row.iloc[0]

    atk = base_row["Attack"]
    defense = base_row["Defense"]
    hp = base_row["Health"]

    print("\n------------------------------------------")
    print(f"Character: {character_id}")
    print(f"Level: {level}")
    print(f"[Base] ATK={atk}, DEF={defense}, HP={hp}")

    # -----------------------------------------------------
    # 3. Equipment main stat (Flat only)
    # -----------------------------------------------------
    if equipment_id != 0:
        equip_row = equipment_df[
            equipment_df["EquipmentId"] == equipment_id
        ]

        if equip_row.empty:
            print(f"⚠️ Equipment not found: {equipment_id}")
        else:
            equip_row = equip_row.iloc[0]
            stat_type = equip_row["MainStatType"]
            value = equip_row["MainStatValue"]

            print(f"[Equipment] {equipment_id}: {stat_type} +{value}")

            if stat_type == "ATK_FLAT":
                atk += value
            elif stat_type == "DEF_FLAT":
                defense += value
            elif stat_type == "HP_FLAT":
                hp += value

    # -----------------------------------------------------
    # 4. Final result (Phase 1)
    # -----------------------------------------------------
    print(f"[Final] ATK={atk}, DEF={defense}, HP={hp}")
    return {
        "CharacterId": character_id,
        "Level": level,
        "FinalATK": atk,
        "FinalDEF": defense,
        "FinalHP": hp,
    }


# =========================================================
# Entry Point
# =========================================================

if __name__ == "__main__":
    print("\n========== Phase 1: Final Base Stat Test ==========")

    for char_id in combat_input_df["CharacterId"].unique():
        calc_final_base_stats(char_id)

    print("\n========== Done ==========")
