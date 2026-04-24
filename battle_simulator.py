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
)

from ability_models import TriggerEvent
from ability_system import AbilitySystem
from battle_reporter import BattleReporter

_LEVEL_ORDER = {LogLevel.INFO: 0, LogLevel.DEBUG: 1, LogLevel.TRACE: 2}


@dataclass(frozen=True)
class BattleConfig:
    battle_count: int = 1
    seed: int = 123  # 方案A會忽略 seed（保留欄位不破壞介面）
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

    def _event(
        self,
        battle_index: int,
        turn: int,
        actor: str,
        event_type: str,
        message: str,
        *,
        level: LogLevel = LogLevel.INFO,
        **extra: Any,
    ) -> None:
        if _LEVEL_ORDER.get(self.log_level, 0) < _LEVEL_ORDER.get(level, 0):
            return

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

        dmg_mul = float(runtime_mod.get("player_damage_multiplier", 1.0))
        heal_mul = float(runtime_mod.get("healing_multiplier", 1.0))
        self._event(
            battle_index,
            turn,
            "Ability",
            "BeforeTrigger",
            f"[Ability] Before trigger: player_damage_multiplier={dmg_mul} healing_multiplier={heal_mul}",
            player_damage_multiplier=dmg_mul,
            healing_multiplier=heal_mul,
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
            player_damage_multiplier=dmg_mul2,
            healing_multiplier=heal_mul2,
            extra_ctx_keys=list(extra_ctx.keys()),
        )

    # -----------------------------
    # Counter runtime state helpers
    # -----------------------------
    def _build_skill_runtime_key(self, monster_id: str, skill: MonsterSkill) -> str:
        # 盡量穩定：有 skill_id 用 skill_id；沒有就 fallback
        sid = getattr(skill, "skill_id", None)
        if sid:
            return f"{monster_id}:{sid}"
        return f"{monster_id}:{skill.monster_id}:{skill.skill_type.value}:{float(getattr(skill, 'counter_max', 0.0))}:{float(getattr(skill, 'value', 0.0))}"

    def _init_enemy_counter_state(
        self,
        enemies: List[MonsterState],
        skills_by_monster: Dict[str, List[MonsterSkill]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        runtime structure:
            state[key] = {
                "counter_now": int,
                "ready": bool,
                "counter_max": int,
                "reload_timing": str,
                "counter_mode": str,
                "counter_start_trigger": str,
                "enemy_phase_action_rule": str,
            }
        """
        st: Dict[str, Dict[str, Any]] = {}
        for e in enemies:
            for sk in skills_by_monster.get(e.monster_id, []):
                key = self._build_skill_runtime_key(e.monster_id, sk)

                counter_max = int(getattr(sk, "counter_max", 0) or 0)
                if counter_max <= 0:
                    # 沒有 counter 的技能，當作永遠不會 ready（可改成 always ready，但你目前表格是 counter 驅動）
                    counter_max = 0

                st[key] = {
                    "counter_now": counter_max,
                    "ready": False,
                    "counter_max": counter_max,
                    "reload_timing": str(getattr(sk, "reload_timing", "") or ""),
                    "counter_mode": str(getattr(sk, "counter_mode", "") or ""),
                    "counter_start_trigger": str(getattr(sk, "counter_start_trigger", "") or ""),
                    "enemy_phase_action_rule": str(getattr(sk, "enemy_phase_action_rule", "") or ""),
                }
        return st

    def _is_counter_enabled(self, sk: MonsterSkill) -> bool:
        # 兼容 enum / string
        mode = getattr(sk, "counter_mode", None)
        if mode is None:
            return False
        try:
            # enum
            return str(mode.value).lower() == "enabled"
        except Exception:
            return str(mode).lower() == "enabled"

    def _is_trigger_on_player_play_card(self, sk: MonsterSkill) -> bool:
        t = getattr(sk, "counter_start_trigger", None)
        if t is None:
            return False
        try:
            return str(t.value) == "OnPlayerPlayCard"
        except Exception:
            return str(t) == "OnPlayerPlayCard"

    def _enemy_phase_rule_act_if_not_acted_this_turn(self, sk: MonsterSkill) -> bool:
        r = getattr(sk, "enemy_phase_action_rule", None)
        if r is None:
            return True
        try:
            return str(r.value) == "ActIfNotActedThisTurn"
        except Exception:
            return str(r) == "ActIfNotActedThisTurn"

    def _reload_after_enemy_attack_phase(self, sk: MonsterSkill) -> bool:
        rt = getattr(sk, "reload_timing", None)
        if rt is None:
            return False
        try:
            return str(rt.value) == "AfterEnemyAttackPhase"
        except Exception:
            return str(rt) == "AfterEnemyAttackPhase"

    def _tick_counters_on_player_play_card(
        self,
        *,
        battle_index: int,
        turn: int,
        enemies: List[MonsterState],
        skills_by_monster: Dict[str, List[MonsterSkill]],
        counter_state: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        你要的語意：
        - 玩家出牌時，只做 counter 推進
        - counter 歸零 => 標記 ready
        - 不能在玩家回合直接執行技能
        - 不能在玩家回合 reload
        """
        for e in enemies:
            if e.is_dead():
                continue

            # 若怪物本回合已行動，且規則是 ActIfNotActedThisTurn，則不推進（避免同回合重複蓄力）
            # 這點可以依你想要的調整：若你希望「即使已行動，也照樣蓄力下一招」，把這段拿掉即可
            for sk in skills_by_monster.get(e.monster_id, []):
                if not self._is_counter_enabled(sk):
                    continue
                if not self._is_trigger_on_player_play_card(sk):
                    continue

                if self._enemy_phase_rule_act_if_not_acted_this_turn(sk) and getattr(e, "acted_this_turn", False):
                    continue

                key = self._build_skill_runtime_key(e.monster_id, sk)
                st = counter_state.get(key)
                if not st:
                    continue

                cmax = int(st.get("counter_max", 0))
                if cmax <= 0:
                    continue

                if st.get("ready", False):
                    # 已 ready 就不要再扣，避免負數與重覆 ready
                    continue

                cnow = int(st.get("counter_now", cmax))
                cnow -= 1
                st["counter_now"] = cnow

                self._event(
                    battle_index,
                    turn,
                    "EnemyCounter",
                    "Tick",
                    f"{e.monster_id} skill={getattr(sk, 'skill_type', 'Unknown')} counter {cnow}/{cmax}",
                    level=LogLevel.TRACE,
                )

                if cnow <= 0:
                    st["ready"] = True
                    self._event(
                        battle_index,
                        turn,
                        "EnemyCounter",
                        "Ready",
                        f"{e.monster_id} skill={getattr(sk, 'skill_type', 'Unknown')} is READY (will execute in EnemyPhase)",
                    )

    def _execute_ready_skill_in_enemy_phase(
        self,
        *,
        battle_index: int,
        turn: int,
        enemy: MonsterState,
        team_hp_now: float,
        team_hp_max: float,
        extra_ctx: Dict[str, Any],
        runtime_mod: Dict[str, Any],
        monster_base_stats: Dict[str, MonsterBaseStat],
        skills_by_monster: Dict[str, List[MonsterSkill]],
        counter_state: Dict[str, Dict[str, Any]],
    ) -> Tuple[float, bool]:
        """
        回傳： (team_hp_now, did_act)
        - 每個 enemy phase，通常只讓怪物執行一個 READY skill（符合 ActIfNotActedThisTurn）
        """
        if enemy.is_dead():
            return team_hp_now, False

        ready_skills: List[MonsterSkill] = []
        for sk in skills_by_monster.get(enemy.monster_id, []):
            key = self._build_skill_runtime_key(enemy.monster_id, sk)
            st = counter_state.get(key)
            if not st:
                continue
            if not st.get("ready", False):
                continue
            ready_skills.append(sk)

        if not ready_skills:
            return team_hp_now, False

        # 決定要放哪一招：目前採用「表格順序第一個 READY」
        sk = ready_skills[0]

        # 若規則是 ActIfNotActedThisTurn 且已行動過，則不出招
        if self._enemy_phase_rule_act_if_not_acted_this_turn(sk) and getattr(enemy, "acted_this_turn", False):
            return team_hp_now, False

        # ---- Execute ----
        if sk.skill_type == MonsterSkillType.Attack:
            damage = float(getattr(sk, "value", 0.0) or 0.0)
            if damage <= 0:
                bs = monster_base_stats[enemy.monster_id]
                damage = float(bs.attack)

            # Arwen mitigation hook
            before_points = int(extra_ctx.get("arwen_points", 0))

            self._trigger_ability(
                battle_index=battle_index,
                turn=turn,
                trigger=TriggerEvent.OnEnemyAttack,
                extra_ctx=extra_ctx,
                runtime_mod=runtime_mod,
                source_desc=f"OnEnemyAttack monster={enemy.monster_id}",
            )

            inc_mul = float(runtime_mod.get("incoming_damage_multiplier", 1.0))
            after_points = int(extra_ctx.get("arwen_points", 0))

            # 保底：如果表/能力沒動到 incoming_damage_multiplier，但點數>0，仍然扣點並套 0.9
            if inc_mul >= 0.9999 and before_points > 0 and after_points == before_points:
                extra_ctx["arwen_points"] = before_points - 1
                inc_mul = 0.9

            self._event(
                battle_index,
                turn,
                "Arwen",
                "AfterAttack",
                f"[Arwen] After OnEnemyAttack: points={extra_ctx.get('arwen_points', 0)} (mul={inc_mul})",
                arwen_points=extra_ctx.get("arwen_points", 0),
                incoming_damage_multiplier=inc_mul,
            )

            team_hp_now -= damage * inc_mul
            self._event(
                battle_index,
                turn,
                "Enemy",
                "Attack",
                f"{enemy.monster_id} attack {damage:.2f} * {inc_mul:.2f} => team_hp={team_hp_now:.2f}/{team_hp_max:.2f}",
            )

            # reset per hit
            runtime_mod["incoming_damage_multiplier"] = 1.0

        elif sk.skill_type == MonsterSkillType.AddShield:
            val = float(getattr(sk, "value", 0.0) or 0.0)
            # MonsterState 不一定有 shield_now，安全寫入
            cur = float(getattr(enemy, "shield_now", 0.0) or 0.0)
            cur2 = cur + val
            try:
                setattr(enemy, "shield_now", cur2)
            except Exception:
                # 若 MonsterState frozen 或不允許 setattr，就只能略過
                pass

            self._event(
                battle_index,
                turn,
                "Enemy",
                "AddShield",
                f"{enemy.monster_id} add shield +{val:.2f} (shield={cur2:.2f})",
            )

        else:
            # 其他技能先記錄，避免無聲失敗
            self._event(
                battle_index,
                turn,
                "Enemy",
                "Skill",
                f"{enemy.monster_id} execute skill_type={sk.skill_type} (not implemented)",
            )

        # ---- Mark acted ----
        enemy.acted_this_turn = True

        # ---- Reload (依 ReloadTiming) ----
        if self._reload_after_enemy_attack_phase(sk):
            key = self._build_skill_runtime_key(enemy.monster_id, sk)
            st = counter_state.get(key)
            if st:
                st["ready"] = False
                st["counter_now"] = int(st.get("counter_max", 0))

                self._event(
                    battle_index,
                    turn,
                    "EnemyCounter",
                    "Reload",
                    f"{enemy.monster_id} skill={getattr(sk, 'skill_type', 'Unknown')} reload counter to {st['counter_now']}",
                )

        return team_hp_now, True

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
        ability_extra_ctx: Optional[Dict[str, Any]] = None,
    ) -> List[BattleResult]:
        # =========================
        # 方案A：不做 random.seed()
        # 讓每次執行都不會固定得到同一組結果
        # =========================

        results: List[BattleResult] = []

        # battle_index 從 1 開始
        for bi in range(1, config.battle_count + 1):
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
        team_hp_max = float(party.team_hp_max)
        team_hp_now = float(party.team_hp_now)

        # enemy_count：每場隨機 1~3（你若要固定每場 3 隻，把這行改成 enemy_count = min(3, len(monster_indexes))）
        enemy_count = random.randint(1, min(3, max(1, len(monster_indexes))))

        # weighted pool by monster_weight
        pool: List[str] = []
        for m in monster_indexes:
            pool += [m.monster_id] * max(1, int(m.monster_weight))

        chosen_ids = [random.choice(pool) for _ in range(enemy_count)]
        enemies: List[MonsterState] = []
        for mid in chosen_ids:
            bs = monster_base_stats[mid]
            enemies.append(MonsterState(monster_id=mid, hp_now=float(bs.health)))

        # skills map（保持表格順序）
        skills_by_monster: Dict[str, List[MonsterSkill]] = {}
        for s in monster_skills:
            skills_by_monster.setdefault(s.monster_id, []).append(s)

        # counter runtime state
        counter_state = self._init_enemy_counter_state(enemies, skills_by_monster)

        # ability contexts
        extra_ctx: Dict[str, Any] = dict(ability_extra_ctx)
        runtime_mod: Dict[str, Any] = {
            "player_damage_multiplier": 1.0,
            "healing_multiplier": 1.0,
            "incoming_damage_multiplier": 1.0,
        }

        # ---------- BattleStart ----------
        extra_ctx.setdefault("enemy_count", enemy_count)

        # 亞玟：依敵人數量，最多 3 點（開戰一次）
        extra_ctx["arwen_points"] = min(3, int(enemy_count))

        self._event(
            battle_index,
            0,
            "Arwen",
            "Init",
            f"[Arwen] Init points={extra_ctx['arwen_points']}",
            arwen_points=extra_ctx["arwen_points"],
        )

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

            for e in enemies:
                e.acted_this_turn = False

            # ========== Player Phase ==========
            if not party_cards:
                self._event(battle_index, turn, "Player", "NoCard", "No card to play.")
            else:
                # ❌ 卡牌選取目前為純隨機，無牌組/手牌/AP 費用管理
                card = random.choice(party_cards)
                effects = effects_by_card_id.get(card.card_id, [])

                self._trigger_ability(
                    battle_index=battle_index,
                    turn=turn,
                    trigger=TriggerEvent.OnPlayCard,
                    extra_ctx=extra_ctx,
                    runtime_mod=runtime_mod,
                    source_desc=f"OnPlayCard card={card.card_id}",
                )

                # ✅ 你要的 counter 語意：玩家出牌只推 counter / 變 ready，不執行技能、不 reload
                self._tick_counters_on_player_play_card(
                    battle_index=battle_index,
                    turn=turn,
                    enemies=enemies,
                    skills_by_monster=skills_by_monster,
                    counter_state=counter_state,
                )

                for eff in effects:
                    active = party.members[0]

                    if eff.scale_stat.value == "ATK":
                        base = float(active.final_atk)
                    elif eff.scale_stat.value == "DEF":
                        base = float(active.final_def)
                    else:
                        base = float(team_hp_max)

                    value = base * float(eff.multiplier) + float(eff.flat_value)

                    if eff.effect_type == EffectType.Damage:
                        dmg_mul = float(runtime_mod.get("player_damage_multiplier", 1.0))
                        if dmg_mul != 1.0:
                            self._event(
                                battle_index,
                                turn,
                                "Ability",
                                "ApplyDamageMul",
                                f"[Ability] Apply player_damage_multiplier={dmg_mul} to damage value",
                                player_damage_multiplier=dmg_mul,
                            )
                        value *= dmg_mul

                        tgt = next((x for x in enemies if not x.is_dead()), None)
                        if tgt is None:
                            break

                        # 若你未來有盾，這裡可先扣 shield 再扣 hp
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
                        if heal_mul != 1.0:
                            self._event(
                                battle_index,
                                turn,
                                "Ability",
                                "ApplyHealMul",
                                f"[Ability] Apply healing_multiplier={heal_mul} to heal value",
                                healing_multiplier=heal_mul,
                            )
                        value *= heal_mul

                        team_hp_now = min(team_hp_max, team_hp_now + float(value))
                        self._event(
                            battle_index,
                            turn,
                            "Player",
                            "Heal",
                            f"PlayCard {card.card_id} heal {value:.2f} (team_hp={team_hp_now:.2f}/{team_hp_max:.2f})",
                        )

            # win check
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

                team_hp_now, did_act = self._execute_ready_skill_in_enemy_phase(
                    battle_index=battle_index,
                    turn=turn,
                    enemy=e,
                    team_hp_now=team_hp_now,
                    team_hp_max=team_hp_max,
                    extra_ctx=extra_ctx,
                    runtime_mod=runtime_mod,
                    monster_base_stats=monster_base_stats,
                    skills_by_monster=skills_by_monster,
                    counter_state=counter_state,
                )

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

            # 如果這回合怪物都沒有 ready 技能，是否要做「預設普通攻擊」？
            # 你的表格目前每隻怪都有 Attack counter，所以通常不會發生。
            # 若你希望永遠每回合怪物都能打，請在這裡加 fallback 行為。

        alive = sum(1 for x in enemies if not x.is_dead())
        return BattleResult(
            battle_index=battle_index,
            winner="Timeout",
            turns=cfg.max_turns,
            player_hp_end=max(0.0, float(team_hp_now)),
            enemies_alive=alive,
            extra={"enemy_count": enemy_count},
        )
