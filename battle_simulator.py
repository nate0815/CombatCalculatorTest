"""
battle_simulator.py
Phase: Battle Simulation (MVP)

MVP rules implemented:
- Player plays cards in a deterministic cycle (all cards of selected character).
- Each card play ticks ALL monsters counters (CounterStartTrigger=OnPlayerPlayCard).
- If a monster counter reaches 0 during Player Phase and monster hasn't acted this turn -> immediate retaliate once.
- When Player Phase ends, Enemy Phase:
  - If EnemyPhaseActionRule=ActIfNotActedThisTurn and monster has NOT acted this turn and counter > 0 -> act once (fallback).
- ReloadTiming=AfterEnemyAttackPhase:
  - After a monster acts (either reaction or fallback), we reload its counter to counter_max at the end of the enemy attack phase.
  - MVP simplification: reload right after the action if reloadTiming == AfterEnemyAttackPhase AND we are in enemy attack resolution section.
- Battle ends when Player HP <= 0 OR all monsters HP <= 0

Damage/Shield/Heal MVP:
- Card Damage: subtract from monster shield then HP
- Card Heal: add to player HP up to max
- Card Shield: add to player shield
- Monster Attack: subtract from player shield then HP
- Monster AddShield: add to monster shield
"""

from typing import List, Optional, Tuple
from models import (
    CharacterSnapshot,
    CardDef,
    CardEffectDef,
    MonsterDef,
    PlayerState,
    MonsterState,
    BattleConfig,
    BattleResult,
    LogLevel,
)


class BattleLogger:
    def __init__(self, level: LogLevel = LogLevel.INFO):
        self.level = level

    def info(self, msg: str) -> None:
        if self.level in (LogLevel.INFO, LogLevel.DEBUG, LogLevel.TRACE):
            print(msg)

    def debug(self, msg: str) -> None:
        if self.level in (LogLevel.DEBUG, LogLevel.TRACE):
            print(msg)

    def trace(self, msg: str) -> None:
        if self.level == LogLevel.TRACE:
            print(msg)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def is_dead(hp: float) -> bool:
    return hp <= 0.0


def pick_enemy_single_by_weight(monsters: List[Tuple[MonsterDef, MonsterState]]) -> Optional[Tuple[MonsterDef, MonsterState]]:
    alive = [(d, s) for (d, s) in monsters if s.hp > 0]
    if not alive:
        return None
    # highest weight first; tie by monster_id for stability
    alive.sort(key=lambda x: (-x[0].monster_weight, x[0].monster_id))
    return alive[0]


def apply_damage_to_target(hp: float, shield: float, dmg: float) -> Tuple[float, float, float]:
    """Return (new_hp, new_shield, damage_to_hp)."""
    if dmg <= 0:
        return hp, shield, 0.0
    remaining = dmg
    if shield > 0:
        used = min(shield, remaining)
        shield -= used
        remaining -= used
    dmg_to_hp = 0.0
    if remaining > 0:
        dmg_to_hp = remaining
        hp -= remaining
    return hp, shield, dmg_to_hp


class BattleSimulator:
    def __init__(self, config: BattleConfig):
        self.config = config
        self.log = BattleLogger(config.log_level)

    def run_many(
        self,
        battle_count: int,
        player_snapshot: CharacterSnapshot,
        player_cards: List[CardDef],
        monsters: List[MonsterDef],
    ) -> List[BattleResult]:
        results: List[BattleResult] = []
        for i in range(1, battle_count + 1):
            r = self.run_single(i, player_snapshot, player_cards, monsters)
            results.append(r)
        return results

    def run_single(
        self,
        battle_index: int,
        player_snapshot: CharacterSnapshot,
        player_cards: List[CardDef],
        monster_defs: List[MonsterDef],
    ) -> BattleResult:
        # -----------------------
        # Init Player / Monsters
        # -----------------------
        player = PlayerState(
            character_id=player_snapshot.character_id,
            max_hp=float(player_snapshot.final_hp),
            hp=float(player_snapshot.final_hp),
            atk=float(player_snapshot.final_atk),
            defense=float(player_snapshot.final_def),
            shield=0.0,
        )

        # Create MonsterState list
        monsters: List[Tuple[MonsterDef, MonsterState]] = []
        for md in monster_defs:
            st = MonsterState(
                monster_id=md.monster_id,
                max_hp=float(md.base_stat.health),
                hp=float(md.base_stat.health),
                atk=float(md.base_stat.attack),
                defense=float(md.base_stat.defense),
                shield=0.0,
                counter=0,
                counter_max=0,
                has_acted_this_turn=False,
                active_skill_index=0,
            )
            # init counter from first skill
            self._init_monster_counter(md, st)
            monsters.append((md, st))

        self.log.info(f"\n=== Battle {battle_index} Start ===")
        self.log.info(f"[Init] Player={player.character_id} HP={player.hp}/{player.max_hp} ATK={player.atk} DEF={player.defense}")
        self.log.info(f"[Init] Enemies={len(monsters)} " + ", ".join([f"{md.monster_id}(HP={st.hp})" for md, st in monsters]))

        # Card play order: deterministic cycle
        if not player_cards:
            raise ValueError("❌ No cards found for player character. Cannot simulate.")

        card_order = list(player_cards)
        card_cursor = 0

        turn = 1
        while turn <= self.config.max_turns:
            # Turn start
            for _, ms in monsters:
                ms.has_acted_this_turn = False

            self.log.info(f"\n[Battle {battle_index}][T{turn:02d}] Turn Start")

            # -----------------------
            # Player Phase
            # -----------------------
            # MVP: play up to 3 cards per turn (simple & readable logs)
            cards_to_play = 3 if len(card_order) >= 3 else len(card_order)

            for _ in range(cards_to_play):
                card = card_order[card_cursor % len(card_order)]
                card_cursor += 1

                # Apply all effects in the card (ordered)
                self.log.info(f"[Battle {battle_index}][T{turn:02d}][Player] Play {card.card_id}")

                for eff in card.effects:
                    self._apply_card_effect(player, monsters, eff, battle_index, turn)

                    # After each card effect, tick monsters counter ONCE per card (OnPlayerPlayCard)
                    # (If you ever want "per effect tick", you can change here.)
                # Tick counters after the whole card (not per effect)
                self._tick_monsters_on_player_play_card(player, monsters, battle_index, turn)

                # Battle end check
                if self._is_battle_end(player, monsters):
                    return self._build_result(battle_index, turn, player, monsters)

            self.log.info(f"[Battle {battle_index}][T{turn:02d}][Player] End Play Phase")

            if self._is_battle_end(player, monsters):
                return self._build_result(battle_index, turn, player, monsters)

            # -----------------------
            # Enemy Phase (fallback)
            # -----------------------
            self.log.info(f"[Battle {battle_index}][T{turn:02d}][EnemyPhase] Start")

            # Apply fallback act for monsters that haven't acted and counter > 0
            for md, ms in monsters:
                if ms.hp <= 0:
                    continue
                skill = self._get_active_skill(md, ms)
                if skill is None:
                    continue
                if skill.enemy_phase_action_rule == "ActIfNotActedThisTurn":
                    if (not ms.has_acted_this_turn) and ms.counter > 0:
                        self.log.info(
                            f"[Battle {battle_index}][T{turn:02d}][EnemyPhase] {md.monster_id} fallback act (counter={ms.counter})"
                        )
                        self._monster_act(md, ms, player, battle_index, turn, reason="EnemyPhaseFallback")

            # Reload after enemy attack phase (MVP: reload any monster that acted this turn)
            for md, ms in monsters:
                if ms.hp <= 0:
                    continue
                if ms.has_acted_this_turn:
                    self._reload_if_needed(md, ms, battle_index, turn)

            if self._is_battle_end(player, monsters):
                return self._build_result(battle_index, turn, player, monsters)

            self.log.info(f"[Battle {battle_index}][T{turn:02d}][EnemyPhase] End")
            turn += 1

        # Safety end
        self.log.info(f"[Battle {battle_index}] Reached max_turns={self.config.max_turns}. End forced.")
        return self._build_result(battle_index, turn, player, monsters, forced=True)

    # =========================================================
    # Internal Helpers
    # =========================================================

    def _init_monster_counter(self, md: MonsterDef, ms: MonsterState) -> None:
        skill = self._get_active_skill(md, ms)
        if skill is None:
            ms.counter_max = 0
            ms.counter = 0
            return
        ms.counter_max = int(skill.counter_max)
        ms.counter = int(skill.counter_max)

    def _get_active_skill(self, md: MonsterDef, ms: MonsterState):
        if not md.skills:
            return None
        idx = ms.active_skill_index % len(md.skills)
        return md.skills[idx]

    def _apply_card_effect(
        self,
        player: PlayerState,
        monsters: List[Tuple[MonsterDef, MonsterState]],
        eff: CardEffectDef,
        battle_index: int,
        turn: int,
    ) -> None:
        et = (eff.effect_type or "").strip()

        # card value = (baseStat * multiplier + flat) is precomputed in Phase2,
        # but in battle MVP we can compute directly using player stats:
        base = 0.0
        key = (eff.scale_stat or "").strip().upper()
        if key == "ATK":
            base = player.atk
        elif key == "DEF":
            base = player.defense
        elif key == "HP":
            base = player.max_hp

        value = base * float(eff.multiplier) + float(eff.flat_value)
        target = (eff.target or "EnemySingle").strip()

        if et == "Damage":
            if target == "EnemyAll":
                for md, ms in monsters:
                    if ms.hp <= 0:
                        continue
                    before_hp = ms.hp
                    before_sh = ms.shield
                    ms.hp, ms.shield, dmg_to_hp = apply_damage_to_target(ms.hp, ms.shield, value)
                    self.log.info(
                        f"[Battle {battle_index}][T{turn:02d}][CardDamage] {eff.card_id} -> {md.monster_id} "
                        f"dmg={value:.1f} (Shield {before_sh:.1f}->{ms.shield:.1f}, HP {before_hp:.1f}->{ms.hp:.1f})"
                    )
            else:
                pick = pick_enemy_single_by_weight(monsters)
                if pick:
                    md, ms = pick
                    before_hp = ms.hp
                    before_sh = ms.shield
                    ms.hp, ms.shield, _ = apply_damage_to_target(ms.hp, ms.shield, value)
                    self.log.info(
                        f"[Battle {battle_index}][T{turn:02d}][CardDamage] {eff.card_id} -> {md.monster_id} "
                        f"dmg={value:.1f} (Shield {before_sh:.1f}->{ms.shield:.1f}, HP {before_hp:.1f}->{ms.hp:.1f})"
                    )

        elif et == "Heal":
            before = player.hp
            player.hp = clamp(player.hp + value, 0.0, player.max_hp)
            self.log.info(
                f"[Battle {battle_index}][T{turn:02d}][CardHeal] +{value:.1f} (HP {before:.1f}->{player.hp:.1f})"
            )

        elif et == "Shield":
            before = player.shield
            player.shield += value
            self.log.info(
                f"[Battle {battle_index}][T{turn:02d}][CardShield] +{value:.1f} (Shield {before:.1f}->{player.shield:.1f})"
            )

        else:
            self.log.debug(
                f"[Battle {battle_index}][T{turn:02d}][CardEffect] Unsupported EffectType={et} (ignored)"
            )

    def _tick_monsters_on_player_play_card(
        self,
        player: PlayerState,
        monsters: List[Tuple[MonsterDef, MonsterState]],
        battle_index: int,
        turn: int,
    ) -> None:
        # Tick all monsters
        for md, ms in monsters:
            if ms.hp <= 0:
                continue

            skill = self._get_active_skill(md, ms)
            if skill is None:
                continue

            # MVP only supports Enabled + OnPlayerPlayCard
            if skill.counter_mode != "Enabled":
                continue
            if skill.counter_start_trigger != "OnPlayerPlayCard":
                continue

            before = ms.counter
            ms.counter = max(0, ms.counter - 1)
            self.log.info(
                f"[Battle {battle_index}][T{turn:02d}][Counter] {md.monster_id} {before}->{ms.counter} (trigger=OnPlayerPlayCard)"
            )

            # If reached 0 during player phase, immediate retaliate once
            if ms.counter == 0 and (not ms.has_acted_this_turn):
                self.log.info(
                    f"[Battle {battle_index}][T{turn:02d}][Reaction] {md.monster_id} counter==0 => retaliate now"
                )
                self._monster_act(md, ms, player, battle_index, turn, reason="PlayerPhaseReaction")

    def _monster_act(
        self,
        md: MonsterDef,
        ms: MonsterState,
        player: PlayerState,
        battle_index: int,
        turn: int,
        reason: str,
    ) -> None:
        skill = self._get_active_skill(md, ms)
        if skill is None:
            return

        st = (skill.skill_type or "").strip()

        if st == "Attack" and skill.target == "Player":
            before_hp = player.hp
            before_sh = player.shield
            player.hp, player.shield, _ = apply_damage_to_target(player.hp, player.shield, float(skill.value))
            self.log.info(
                f"[Battle {battle_index}][T{turn:02d}][EnemyAttack:{reason}] {md.monster_id} "
                f"-> Player dmg={skill.value:.1f} (Shield {before_sh:.1f}->{player.shield:.1f}, HP {before_hp:.1f}->{player.hp:.1f})"
            )
            ms.has_acted_this_turn = True

        elif st == "AddShield" and skill.target == "Self":
            before = ms.shield
            ms.shield += float(skill.value)
            self.log.info(
                f"[Battle {battle_index}][T{turn:02d}][EnemyShield:{reason}] {md.monster_id} "
                f"+{skill.value:.1f} (Shield {before:.1f}->{ms.shield:.1f})"
            )
            ms.has_acted_this_turn = True

        else:
            self.log.debug(
                f"[Battle {battle_index}][T{turn:02d}][EnemyAct:{reason}] {md.monster_id} unsupported skill={st}/target={skill.target} (ignored)"
            )
            ms.has_acted_this_turn = True  # still counts as acted

    def _reload_if_needed(self, md: MonsterDef, ms: MonsterState, battle_index: int, turn: int) -> None:
        skill = self._get_active_skill(md, ms)
        if skill is None:
            return
        if skill.reload_timing != "AfterEnemyAttackPhase":
            return

        before = ms.counter
        ms.counter_max = int(skill.counter_max)
        ms.counter = int(skill.counter_max)
        self.log.info(
            f"[Battle {battle_index}][T{turn:02d}][Reload] {md.monster_id} {before}->{ms.counter} (AfterEnemyAttackPhase)"
        )

    def _is_battle_end(self, player: PlayerState, monsters: List[Tuple[MonsterDef, MonsterState]]) -> bool:
        if is_dead(player.hp):
            return True
        alive = [1 for _, ms in monsters if ms.hp > 0]
        return len(alive) == 0

    def _build_result(
        self,
        battle_index: int,
        turn: int,
        player: PlayerState,
        monsters: List[Tuple[MonsterDef, MonsterState]],
        forced: bool = False,
    ) -> BattleResult:
        enemies_alive = sum(1 for _, ms in monsters if ms.hp > 0)
        winner = "Enemy" if is_dead(player.hp) else "Player"
        if forced:
            winner = "Unknown"

        self.log.info(
            f"\n=== Battle {battle_index} End === Winner={winner} Turns={turn} PlayerHP={player.hp:.1f} EnemiesAlive={enemies_alive}"
        )

        return BattleResult(
            battle_index=battle_index,
            turns=turn,
            winner=winner,
            player_hp_end=float(player.hp),
            enemies_alive=int(enemies_alive),
        )
