from common.models import CharacterSnapshot

def calc_simple_damage(snapshot: CharacterSnapshot, multiplier: float) -> float:
    return snapshot.final_atk * multiplier


snap = CharacterSnapshot(
    character_id="Test",
    final_atk=1000,
    final_def=500,
    final_hp=3000
)

print(calc_simple_damage(snap, 1.8))
