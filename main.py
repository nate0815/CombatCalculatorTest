# main.py
# Orchestrator / Pipeline Runner

import pandas as pd
from combat_static_calculator import calc_all_character_snapshots


def main():
    print("=== Combat Calculator Pipeline ===")

    # Phase 1 (quiet)
    snapshots = calc_all_character_snapshots(verbose=False)

    print("\n=== Phase 1 Result ===")
    if not snapshots:
        print("(no snapshots)")
    else:
        df = pd.DataFrame([{
            "CharacterId": s.character_id,
            "Level": s.level,
            "ATK": round(s.final_atk, 2),
            "DEF": round(s.final_def, 2),
            "HP": round(s.final_hp, 2),
        } for s in snapshots])

        print(df.to_string(index=False))

    print("\nPipeline done.")
    input("按 Enter 鍵結束程式...")


if __name__ == "__main__":
    main()
