# battle_simulator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import random

from models import (
    BattleResult,
    Card,
    CardEffect,
    EffectType,
    LogLevel,
    MonsterBaseStat,
    MonsterIndex,
    MonsterSkill,
    MonsterSkillType,
    MonsterState,
    PlayerPartySnapshot,
    TargetType,
)

from ability_models import TriggerEvent
from ability_system import AbilitySystem
from battle_reporter import BattleReporter


@dataclass(frozen=True)
class BattleConfig:
    battle_count: int = 1
    seed: int = 123
    max_turns: int = 50


class BattleSimulator:
    def __init__(
        self,
        *,
        ability_system: Optional[AbilitySystem] = None,
        reporter: Optional[BattleReporter] = None,
        log_level: LogLevel = LogLevel.INFO,
    ) -> None:
        self.ability_system = ability_system
        self.reporter = reporter
        self.log_level = log_level

    # ----------------------------
    # Internal logging helper
    # ----------------------------
    def _event(
        self,
        battle_index: int,
        turn: int,
        actor: str,
        event_type: str,
        message: str,
        **extra: Any,
    ) -> None:
        if self.reporter:
            payload = {
                "battle_index": battle_index,
                "turn": turn,
                "actor": actor,
                "event_type": event_type,
                "message": message,
            }
            payload.update(extra)
            self.reporter.add_event(payload)

        if self.log_level in (LogLevel.DEBUG, LogLevel.TRACE):
            print(f"[B{battle_index} T{turn}] {actor} {event_type}: {message}")

    # ----------------------------
    # Ability trigger wrapper
    # ----------------------------
    def _trigger_ability(
        self,
        battle_index: int,
        turn: int,
        trigger: TriggerEvent,
        extra_ctx: Dict[str, Any],
        runtime_mod: Dict[str, Any],
        source_desc: str,
    ) -> None:
        if not self.ability_system:
            return

        # reporter patterns want these lines
        dmg_mul = float(runtime_mod.get("player_damage_multiplier", 1.0))
        heal_mul = float(runtime_mod.get("healing_multiplier", 1.0))
        self._event(
            battle_index,
            turn,
            "Ability",
            "BeforeTrigger",
            f"[Ability] Before trigger: player_damage_multiplier={dmg_mul} healing_multiplier={heal_mul}",
        )

        self.ability_system.trigger(
            trigger_event=trigger,
            extra_ctx=extra_ctx,
            runtime_mod=runtime_mod,
        )

        dmg_mul2 = float(runtime_mod.get("player_damage_multiplier", 1.0))
        heal_mul2 = float(runtime_mod.get("healing_multiplier", 1.0))
        self._event(
            battle_index,
            turn,
            "Ability",
            "AfterTrigger",
            f"[Ability] After trigger: player_damage_multiplier={dmg_mul2} healing_multiplier={heal_mul2} (triggered by {source_desc})",
            extra_ctx_keys=list(extra_ctx.keys()),
        )

    # ----------------------------
    # Battle entry
    # ----------------------------
    def run_battles(
        self,
        *,
        config: BattleConfig,
        party: PlayerPartySnapshot,
        party_cards: List[Card],
        effects_by_card_id: Dict[str, List[CardEffect]],
        monster_indexes: List[MonsterIndex],
        monster_base_stats: Dict[str, MonsterBaseStat],
        monster_skills: List[MonsterSkill],
        # injected context from main/runtime_input (for ability condition)
        ability_extra_ctx: Optional[Dict[str, Any]] = None,
    ) -> List[BattleResult]:
        random.seed(config.seed)
        results: List[BattleResult] = []

        for bi in range(config.battle_count):
            r = self._run_one_battle(
                battle_index=bi,
                cfg=config,
                party=party,
                party_cards=party_cards,
                effects_by_card_id=effects_by_card_id,
                monster_indexes=monster_indexes,
                monster_base_stats=monster_base_stats,
                monster_skills=monster_skills,
                ability_extra_ctx=ability_extra_ctx or {},
            )
            results.append(r)

        return results

    def _run_one_battle(
        self,
        *,
        battle_index: int,
        cfg: BattleConfig,
        party: PlayerPartySnapshot,
        party_cards: List[Card],
        effects_by_card_id: Dict[str, List[CardEffect]],
        monster_indexes: List[MonsterIndex],
        monster_base_stats: Dict[str, MonsterBaseStat],
        monster_skills: List[MonsterSkill],
        ability_extra_ctx: Dict[str, Any],
    ) -> BattleResult:
        # clone party hp (MVP: shared HP bar)
        team_hp_max = float(party.team_hp_max)
        team_hp_now = float(party.team_hp_now)

        # choose monsters by weight (MVP: pick 1~3)
        # 你 Arwen 的點數會依「敵人數量」決定，所以這裡保持多敵人情境
        enemy_count = min(3, max(1, len(monster_indexes)))
        pool: List[str] = []
        for m in monster_indexes:
            pool += [m.monster_id] * max(1, int(m.monster_weight))
        chosen_ids = [random.choice(pool) for _ in range(enemy_count)]

        enemies: List[MonsterState] = []
        for mid in chosen_ids:
            bs = monster_base_stats[mid]
            enemies.append(MonsterState(monster_id=mid, hp_now=float(bs.health)))

        # build skill map
        skills_by_monster: Dict[str, List[MonsterSkill]] = {}
        for s in monster_skills:
            skills_by_monster.setdefault(s.monster_id, []).append(s)

        # ability contexts
        extra_ctx: Dict[str, Any] = dict(ability_extra_ctx)  # persistent
        runtime_mod: Dict[str, Any] = {
            "player_damage_multiplier": 1.0,
            "healing_multiplier": 1.0,
            "incoming_damage_multiplier": 1.0,  # for Arwen consume-point mitigation
        }

        # ---------- BattleStart trigger ----------
        # Arwen: init points based on enemy count (max 3) — 你之前也確認是「開戰一次」
        extra_ctx.setdefault("enemy_count", enemy_count)
        extra_ctx.setdefault("arwen_points", min(3, int(enemy_count)))
        self._event(battle_index, 0, "Arwen", "Init", f"[Arwen] Init points={extra_ctx['arwen_points']}")

        self._trigger_ability(
            battle_index=battle_index,
            turn=0,
            trigger=TriggerEvent.BattleStart,
            extra_ctx=extra_ctx,
            runtime_mod=runtime_mod,
            source_desc="BattleStart",
        )

        # ---------- Turns loop ----------
        turn = 0
        while turn < cfg.max_turns:
            turn += 1

            # reset per-turn flags
            for e in enemies:
                e.acted_this_turn = False

            # ========== Player Phase ==========
            if not party_cards:
                # no cards => skip
                self._event(battle_index, turn, "Player", "NoCard", "No card to play.")
            else:
                card = random.choice(party_cards)
                effects = effects_by_card_id.get(card.card_id, [])

                # trigger ability on play card
                self._trigger_ability(
                    battle_index=battle_index,
                    turn=turn,
                    trigger=TriggerEvent.OnPlayCard,
                    extra_ctx=extra_ctx,
                    runtime_mod=runtime_mod,
                    source_desc=f"OnPlayCard card={card.card_id}",
                )

                # apply effects
                for eff in effects:
                    # compute base using first member as active (MVP)
                    active = party.members[0]
                    base = 0.0
                    if eff.scale_stat.value == "ATK":
                        base = float(active.final_atk)
                    elif eff.scale_stat.value == "DEF":
                        base = float(active.final_def)
                    elif eff.scale_stat.value == "HP":
                        base = float(team_hp_max)

                    value = base * float(eff.multiplier) + float(eff.flat_value)

                    if eff.effect_type == EffectType.Damage:
                        # Douglas-like outgoing multiplier
                        dmg_mul = float(runtime_mod.get("player_damage_multiplier", 1.0))
                        self._event(
                            battle_index,
                            turn,
                            "Ability",
                            "Apply",
                            f"[Ability] Apply player_damage_multiplier={dmg_mul} to damage value",
                        )
                        value = value * dmg_mul

                        # target first alive enemy
                        tgt = next((x for x in enemies if not x.is_dead()), None)
                        if tgt is None:
                            break
                        tgt.hp_now -= float(value)
                        self._event(
                            battle_index,
                            turn,
                            "Player",
                            "Damage",
                            f"PlayCard {card.card_id} deal {value:.2f} to {tgt.monster_id} (hp={tgt.hp_now:.2f})",
                        )

                    elif eff.effect_type == EffectType.Heal:
                        heal_mul = float(runtime_mod.get("healing_multiplier", 1.0))
                        self._event(
                            battle_index,
                            turn,
                            "Ability",
                            "Apply",
                            f"[Ability] Apply healing_multiplier={heal_mul} to heal value",
                        )
                        value = value * heal_mul
                        team_hp_now = min(team_hp_max, team_hp_now + float(value))
                        self._event(
                            battle_index,
                            turn,
                            "Player",
                            "Heal",
                            f"PlayCard {card.card_id} heal {value:.2f} (team_hp={team_hp_now:.2f}/{team_hp_max:.2f})",
                        )

                    elif eff.effect_type == EffectType.Shield:
                        # MVP ignore shield (or keep for later)
                        self._event(battle_index, turn, "Player", "Shield", f"Shield effect {value:.2f} (ignored in MVP)")

            # check win after player phase
            if all(e.is_dead() for e in enemies):
                return BattleResult(
                    battle_index=battle_index,
                    winner="Player",
                    turns=turn,
                    player_hp_end=float(team_hp_now),
                    enemies_alive=0,
                    extra={"enemy_count": enemy_count},
                )

            # ========== Enemy Phase ==========
            for e in enemies:
                if e.is_dead():
                    continue

                bs = monster_base_stats[e.monster_id]
                # find a simple attack skill (MVP)
                s_list = skills_by_monster.get(e.monster_id, [])
                attack_skill = next((s for s in s_list if s.skill_type == MonsterSkillType.Attack), None)
                damage = float(attack_skill.value if attack_skill else bs.attack)

                # Arwen: consume point on being attacked -> set incoming_damage_multiplier
                # NOTE: ability_system has TriggerEvent.OnEnemyAttack for data-driven version
                # Here we also keep a simple fallback:
                self._trigger_ability(
                    battle_index=battle_index,
                    turn=turn,
                    trigger=TriggerEvent.OnEnemyAttack,
                    extra_ctx=extra_ctx,
                    runtime_mod=runtime_mod,
                    source_desc=f"OnEnemyAttack monster={e.monster_id}",
                )

                inc_mul = float(runtime_mod.get("incoming_damage_multiplier", 1.0))
                if inc_mul < 0.9999:
                    # reporter wants this pattern
                    self._event(
                        battle_index,
                        turn,
                        "Arwen",
                        "OnEnemyAttack",
                        f"[Arwen] After OnEnemyAttack: points={extra_ctx.get('arwen_points', 0)} (mul={inc_mul})",
                    )

                team_hp_now -= damage * inc_mul
                self._event(
                    battle_index,
                    turn,
                    "Enemy",
                    "Attack",
                    f"{e.monster_id} attack {damage:.2f} * {inc_mul:.2f} => team_hp={team_hp_now:.2f}/{team_hp_max:.2f}",
                )

                # reset incoming mul to 1 each hit (so next hit re-evaluates)
                runtime_mod["incoming_damage_multiplier"] = 1.0

                if team_hp_now <= 0:
                    alive = sum(1 for x in enemies if not x.is_dead())
                    return BattleResult(
                        battle_index=battle_index,
                        winner="Enemy",
                        turns=turn,
                        player_hp_end=0.0,
                        enemies_alive=alive,
                        extra={"enemy_count": enemy_count},
                    )

        # max turns reached
        alive = sum(1 for x in enemies if not x.is_dead())
        return BattleResult(
            battle_index=battle_index,
            winner="Timeout",
            turns=cfg.max_turns,
            player_hp_end=max(0.0, float(team_hp_now)),
            enemies_alive=alive,
            extra={"enemy_count": enemy_count},
        )
