# main.py
# Orchestrator / Pipeline Runner

import pandas as pd
from combat_static_calculator import calc_all_character_snapshots

from card_repository import CardRepository
from card_static_calculator import calc_card


def main():
    print("=== Combat Calculator Pipeline ===")

    # -----------------------------
    # Phase 1 (quiet)
    # -----------------------------
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

    # -----------------------------
    # Phase 2 (Card Static Calc)
    # -----------------------------
    print("\n=== Phase 2: Card Static Result ===")

    try:
        repo = CardRepository("Card.xlsx")
        repo.load()
    except Exception as e:
        print(f"❌ Failed to load Card.xlsx: {e}")
        print("\nPipeline done.")
        input("按 Enter 鍵結束程式...")
        return

    if not snapshots:
        print("(skip phase 2: no snapshots)")
        print("\nPipeline done.")
        input("按 Enter 鍵結束程式...")
        return

    card_rows = []
    for s in snapshots:
        cards = repo.get_cards_by_character(s.character_id)
        if not cards:
            print(f"⚠️ No cards found for character: {s.character_id}")
            continue

        for c in cards:
            r = calc_card(s, c, verbose=True)

            card_rows.append({
                "CharacterId": s.character_id,
                "CardId": r.card_id,
                "Tier": r.epiphany_tier,
                "DamageTotal": round(r.totals.get("Damage", 0.0), 2),
                "HealTotal": round(r.totals.get("Heal", 0.0), 2),
                "ShieldTotal": round(r.totals.get("Shield", 0.0), 2),
            })

    print("\n=== Phase 2 Summary ===")
    if not card_rows:
        print("(no card results)")
    else:
        df2 = pd.DataFrame(card_rows).sort_values(by=["CharacterId", "CardId"]).reset_index(drop=True)
        print(df2.to_string(index=False))

    print("\nPipeline done.")
    input("按 Enter 鍵結束程式...")


if __name__ == "__main__":
    main()
