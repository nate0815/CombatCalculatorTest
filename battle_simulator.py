# battle_simulator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import random

from battle_reporter import BattleReporter
from models import (
    BattleResult,
    Card,
    CardEffect,
    CounterMode,
    CounterStartTrigger,
    EffectType,
    EnemyPhaseActionRule,
    LogLevel,
    MonsterBaseStat,
    MonsterIndex,
    MonsterSkill,
    MonsterSkillType,
    MonsterState,
    PlayerPartySnapshot,
    ReloadTiming,
    ScaleStat,
    TargetType,
)


@dataclass
class BattleConfig:
    ap_max: int = 3
    max_turns: int = 999
    log_level: LogLevel = LogLevel.INFO

    # kept for backward compatibility with main.py
    # 舊版語意：當下一張卡牌費用 > 剩餘 AP 時，停止玩家階段
    # 新版抽手牌邏輯下：我們會改成「沒有可出的牌就結束玩家階段」
    stop_when_insufficient_ap: bool = True

    # 新增：每回合抽牌數
    hand_size: int = 5

    # 可選：固定亂數種子方便重現
    rng_seed: Optional[int] = None


class BattleLogger:
    def __init__(self, level: LogLevel) -> None:
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


def apply_damage(hp: float, shield: float, dmg: float) -> Tuple[float, float]:
    """Damage consumes shield first, then hp."""
    if dmg <= 0:
        return max(0.0, hp), max(0.0, shield)

    remaining = dmg
    if shield > 0:
        used = min(shield, remaining)
        shield -= used
        remaining -= used

    if remaining > 0:
        hp -= remaining

    return max(0.0, hp), max(0.0, shield)


def pick_enemy_single(
    monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]]
) -> Optional[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]]:
    alive = [(mi, ms, st) for (mi, ms, st) in monsters if st.hp > 0]
    if not alive:
        return None
    # Highest weight first, stable by monster_id
    alive.sort(key=lambda x: (-x[0].monster_weight, x[0].monster_id))
    return alive[0]


class BattleSimulator:
    """
    MVP 戰鬥流程包含:
    - 隊伍共用血條 (PlayerPartySnapshot.team_hp / team_hp_max)
    - 隊伍共用護盾池 (PlayerPartySnapshot.team_shield)
    - AP 系統 (最大 AP=3)，每張卡牌依 Card.ap_cost 消耗
    - 抽牌/棄牌/洗牌:
        1) 初始全部卡牌進 Draw Pile
        2) 玩家回合開始抽 hand_size 張
        3) 每次出牌：先看 AP -> 找出手牌中可出卡 -> 隨機挑 1 張打出
        4) 若沒有可出卡(手牌都太貴/手牌為空/AP不足) -> 結束玩家階段
        5) 回合結束：手牌剩餘全部丟棄牌堆
        6) 抽牌時 Draw 不足：把 Discard 洗回 Draw
    - 計數器觸發: 玩家打出任意卡牌時 (OnPlayerPlayCard)
    - 反應機制: 若玩家階段計數器歸零且怪物尚未行動 => 立即行動一次
    - 敵方階段規則 (ActIfNotActedThisTurn): 若本回合尚未行動且 counter > 0 => 在敵方階段行動一次
    - 重置時機 (AfterEnemyAttackPhase): 怪物本回合行動後，於敵方階段結束時重置計數器
    """

    def __init__(self, config: BattleConfig, reporter: BattleReporter) -> None:
        self.config = config
        self.reporter = reporter
        self.log = BattleLogger(config.log_level)
        self._rng = random.Random(config.rng_seed)

    # =========================================================
    # Public
    # =========================================================
    def run_many(
        self,
        battle_count: int,
        party: PlayerPartySnapshot,
        party_cards: List[Card],
        card_effects_by_id: Dict[str, List[CardEffect]],
        monster_indexes: List[MonsterIndex],
        monster_base_stats: Dict[str, MonsterBaseStat],
        monster_skills: List[MonsterSkill],
    ) -> List[BattleResult]:
        results: List[BattleResult] = []
        for i in range(1, battle_count + 1):
            # 每場 battle 有獨立亂數序列（但仍可重現）
            if self.config.rng_seed is not None:
                self._rng = random.Random(self.config.rng_seed + i)

            res = self.run_single(
                battle_index=i,
                party=party,
                party_cards=party_cards,
                card_effects_by_id=card_effects_by_id,
                monster_indexes=monster_indexes,
                monster_base_stats=monster_base_stats,
                monster_skills=monster_skills,
            )
            results.append(res)
        return results

    def run_single(
        self,
        battle_index: int,
        party: PlayerPartySnapshot,
        party_cards: List[Card],
        card_effects_by_id: Dict[str, List[CardEffect]],
        monster_indexes: List[MonsterIndex],
        monster_base_stats: Dict[str, MonsterBaseStat],
        monster_skills: List[MonsterSkill],
    ) -> BattleResult:
        # --------------------------
        # Init party runtime state
        # 初始化隊伍執行時狀態
        # --------------------------
        party_runtime = PlayerPartySnapshot(
            members=party.members,
            active_character_id=party.active_character_id,
        )
        party_runtime.team_shield = 0.0  # 重置護盾
        active_member = party_runtime.get_active_member()

        # --------------------------
        # Build monsters runtime
        # 建立怪物執行時狀態
        # --------------------------
        skills_by_monster: Dict[str, List[MonsterSkill]] = {}
        for sk in monster_skills:
            skills_by_monster.setdefault(sk.monster_id, []).append(sk)
        for mid in skills_by_monster:
            # 讓技能順序可預期
            skills_by_monster[mid].sort(key=lambda s: s.skill_id)

        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]] = []
        for mi in monster_indexes:
            base = monster_base_stats.get(mi.monster_id)
            if base is None:
                raise ValueError(f"❌ Missing MonsterBaseStat for MonsterId={mi.monster_id}")

            # MVP: 選取第一個技能作為主要技能
            sk_list = skills_by_monster.get(mi.monster_id, [])
            counter_max = sk_list[0].counter_max if sk_list else 0

            st = MonsterState(
                monster_id=mi.monster_id,
                hp=float(base.health),
                shield=0.0,
                counter=int(counter_max),
                counter_max=int(counter_max),
                has_acted_this_turn=False,
            )
            monsters.append((mi, base, st))

        if not party_cards:
            raise ValueError("❌ No cards for party.")

        # --------------------------
        # Deck runtime state
        # 抽牌/棄牌/洗牌：runtime 狀態
        # --------------------------
        draw_pile: List[Card] = list(party_cards)
        discard_pile: List[Card] = []
        hand: List[Card] = []

        self._rng.shuffle(draw_pile)

        # --------------------------
        # Init logs
        # 初始化日誌
        # --------------------------
        self._print_and_record_system(
            battle_index, 0, "System", "BattleStart", f"=== Battle {battle_index} Start ==="
        )
        self._print_and_record_system(
            battle_index,
            0,
            "System",
            "Init",
            f"[Init] PartyHP={party_runtime.team_hp:.1f}/{party_runtime.team_hp_max:.1f} "
            f"Shield={party_runtime.team_shield:.1f} Active={active_member.character_id}",
        )
        self._print_and_record_system(
            battle_index,
            0,
            "System",
            "InitEnemies",
            "[Init] Enemies="
            + ", ".join([f"{mi.monster_id}(HP={st.hp:.1f},C={st.counter})" for mi, _, st in monsters]),
        )

        def draw_cards(turn: int, n: int) -> None:
            """Draw up to n cards into hand. If draw pile insufficient, shuffle discard into draw."""
            nonlocal draw_pile, discard_pile, hand
            for _ in range(n):
                if not draw_pile:
                    if discard_pile:
                        draw_pile = discard_pile
                        discard_pile = []
                        self._rng.shuffle(draw_pile)
                        self._print_and_record_system(
                            battle_index,
                            turn,
                            "System",
                            "Shuffle",
                            f"[Shuffle] Discard -> Draw (count={len(draw_pile)})",
                        )
                    else:
                        break
                hand.append(draw_pile.pop())

        # --------------------------
        # Main loop
        # --------------------------
        turn = 0
        while True:
            turn += 1
            if turn > self.config.max_turns:
                # 超過回合上限：以目前狀態返回
                return BattleResult(
                    battle_index=battle_index,
                    winner="Enemy" if party_runtime.team_hp <= 0 else "Player",
                    turns=turn - 1,
                    player_hp_end=float(party_runtime.team_hp),
                    enemies_alive=int(sum(1 for _, _, st in monsters if st.hp > 0)),
                )

            # Reset per-turn flags
            for _, _, st in monsters:
                st.has_acted_this_turn = False

            # =========================
            # Player Phase
            # =========================
            ap = int(self.config.ap_max)

            # 回合開始抽手牌
            hand.clear()
            draw_cards(turn, int(self.config.hand_size))

            self._print_and_record_system(
                battle_index,
                turn,
                "System",
                "TurnStart",
                f"--- Turn {turn} Start --- (AP={ap}, Hand={len(hand)}, Draw={len(draw_pile)}, Discard={len(discard_pile)})",
            )

            # 玩家出牌迴圈：先看 AP -> 篩可出 -> 隨機挑 1 張出
            while ap > 0:
                playable = [c for c in hand if int(getattr(c, "ap_cost", 1)) <= ap]
                if not playable:
                    self._print_and_record_system(
                        battle_index,
                        turn,
                        "System",
                        "NoPlayableCard",
                        f"[PlayerPhase] No playable card (AP={ap}, Hand={len(hand)}) -> End Player Phase",
                    )
                    break

                card = self._rng.choice(playable)
                cost = int(getattr(card, "ap_cost", 1))

                # 扣 AP，從手牌移除，丟棄牌堆
                ap -= cost
                hand.remove(card)
                discard_pile.append(card)

                self._print_and_record_system(
                    battle_index,
                    turn,
                    active_member.character_id,
                    "PlayCard",
                    f"[PlayCard] {active_member.character_id} plays {card.card_id} (Cost={cost}, APLeft={ap})",
                )

                effects = card_effects_by_id.get(card.card_id, [])
                for ef in effects:
                    self._apply_card_effect(
                        battle_index=battle_index,
                        turn=turn,
                        party=party_runtime,
                        active_member_id=active_member.character_id,
                        effect=ef,
                        monsters=monsters,
                    )

                # 玩家出任意卡牌 -> tick counters
                self._tick_counters_on_player_play_card(
                    battle_index=battle_index,
                    turn=turn,
                    party=party_runtime,
                    monsters=monsters,
                    skills_by_monster=skills_by_monster,
                )

                # Battle end check
                winner = self._get_winner(party_runtime, monsters)
                if winner is not None:
                    return BattleResult(
                        battle_index=battle_index,
                        winner=winner,
                        turns=turn,
                        player_hp_end=float(party_runtime.team_hp),
                        enemies_alive=int(sum(1 for _, _, st in monsters if st.hp > 0)),
                    )

            # 回合結束：手牌剩餘全部丟棄牌堆
            if hand:
                discard_pile.extend(hand)
                hand.clear()

            # =========================
            # Enemy Phase
            # =========================
            for (mi, base, st) in monsters:
                if st.hp <= 0:
                    continue

                sk_list = skills_by_monster.get(mi.monster_id, [])
                if not sk_list:
                    continue
                sk = sk_list[0]

                # 若設定為 ActIfNotActedThisTurn，且本回合尚未行動，且 counter > 0，則在敵方階段行動一次
                if sk.enemy_phase_action_rule == EnemyPhaseActionRule.ActIfNotActedThisTurn:
                    if (not st.has_acted_this_turn) and (st.counter > 0):
                        self._monster_act(
                            battle_index=battle_index,
                            turn=turn,
                            party=party_runtime,
                            monster_index=mi,
                            monster_base=base,
                            monster_state=st,
                            skills_by_monster=skills_by_monster,
                            reason="EnemyPhase",
                        )

                winner = self._get_winner(party_runtime, monsters)
                if winner is not None:
                    return BattleResult(
                        battle_index=battle_index,
                        winner=winner,
                        turns=turn,
                        player_hp_end=float(party_runtime.team_hp),
                        enemies_alive=int(sum(1 for _, _, st in monsters if st.hp > 0)),
                    )

            # =========================
            # End of Turn: Reload (AfterEnemyAttackPhase)
            # =========================
            for (mi, _, st) in monsters:
                if st.hp <= 0:
                    continue
                if not st.has_acted_this_turn:
                    continue

                sk_list = skills_by_monster.get(mi.monster_id, [])
                if not sk_list:
                    continue
                sk = sk_list[0]

                if sk.reload_timing == ReloadTiming.AfterEnemyAttackPhase:
                    st.counter = int(st.counter_max)
                    self._print_and_record_system(
                        battle_index,
                        turn,
                        mi.monster_id,
                        "Reload",
                        f"[Reload] counter reset to {st.counter}",
                    )

            winner = self._get_winner(party_runtime, monsters)
            if winner is not None:
                return BattleResult(
                    battle_index=battle_index,
                    winner=winner,
                    turns=turn,
                    player_hp_end=float(party_runtime.team_hp),
                    enemies_alive=int(sum(1 for _, _, st in monsters if st.hp > 0)),
                )

    # =========================================================
    # Internal - Effects
    # =========================================================
    def _apply_card_effect(
        self,
        battle_index: int,
        turn: int,
        party: PlayerPartySnapshot,
        active_member_id: str,
        effect: CardEffect,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
    ) -> None:
        # Value = base(stat)*multiplier + flat_value
        if effect.scale_stat == ScaleStat.ATK:
            base_value = party.get_active_member().final_atk if party.active_character_id == active_member_id else party.get_active_member().final_atk
            base_value = party.get_active_member().final_atk if party.get_active_member().character_id == active_member_id else party.get_active_member().final_atk
            base_value = party.get_active_member().final_atk
        elif effect.scale_stat == ScaleStat.DEF:
            base_value = party.get_active_member().final_def
        elif effect.scale_stat == ScaleStat.HP:
            # 隊伍共用血條：HP scale 用 team_hp_max
            base_value = party.team_hp_max
        else:
            base_value = 0.0

        value = float(base_value) * float(effect.multiplier) + float(effect.flat_value)

        if effect.effect_type == EffectType.Damage:
            if effect.target == TargetType.EnemyAll:
                for (mi, _, st) in monsters:
                    if st.hp <= 0:
                        continue
                    old_hp, old_sh = st.hp, st.shield
                    st.hp, st.shield = apply_damage(st.hp, st.shield, value)
                    self._print_and_record_system(
                        battle_index,
                        turn,
                        "Player",
                        "Damage",
                        f"[Damage] Player -> {mi.monster_id} Dmg={value:.1f} | HP {old_hp:.1f}->{st.hp:.1f} Shield {old_sh:.1f}->{st.shield:.1f}",
                    )
            elif effect.target == TargetType.EnemySingle:
                picked = pick_enemy_single(monsters)
                if picked is not None:
                    mi, _, st = picked
                    old_hp, old_sh = st.hp, st.shield
                    st.hp, st.shield = apply_damage(st.hp, st.shield, value)
                    self._print_and_record_system(
                        battle_index,
                        turn,
                        "Player",
                        "Damage",
                        f"[Damage] Player -> {mi.monster_id} Dmg={value:.1f} | HP {old_hp:.1f}->{st.hp:.1f} Shield {old_sh:.1f}->{st.shield:.1f}",
                    )

        elif effect.effect_type == EffectType.Shield:
            old = party.team_shield
            party.team_shield = max(0.0, party.team_shield + value)
            self._print_and_record_system(
                battle_index,
                turn,
                "Player",
                "Shield",
                f"[Shield] +{value:.1f} (Shield {old:.1f} -> {party.team_shield:.1f})",
            )

        elif effect.effect_type == EffectType.Heal:
            old = party.team_hp
            party.team_hp = clamp(party.team_hp + value, 0.0, party.team_hp_max)
            self._print_and_record_system(
                battle_index,
                turn,
                "Player",
                "Heal",
                f"[Heal] +{value:.1f} (HP {old:.1f} -> {party.team_hp:.1f})",
            )

    # =========================================================
    # Internal - Counter / Monster act
    # =========================================================
    def _tick_counters_on_player_play_card(
        self,
        battle_index: int,
        turn: int,
        party: PlayerPartySnapshot,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
        skills_by_monster: Dict[str, List[MonsterSkill]],
    ) -> None:
        for (mi, base, st) in monsters:
            if st.hp <= 0:
                continue

            sk_list = skills_by_monster.get(mi.monster_id, [])
            if not sk_list:
                continue
            sk = sk_list[0]

            if sk.counter_mode != CounterMode.Enabled:
                continue
            if sk.counter_start_trigger != CounterStartTrigger.OnPlayerPlayCard:
                continue

            before = st.counter
            st.counter = max(0, int(st.counter) - 1)
            self._print_and_record_system(
                battle_index,
                turn,
                mi.monster_id,
                "CounterTick",
                f"[Counter] {before} -> {st.counter}",
            )

            # Reaction: counter==0 and not acted => act immediately
            if st.counter == 0 and (not st.has_acted_this_turn):
                self._monster_act(
                    battle_index=battle_index,
                    turn=turn,
                    party=party,
                    monster_index=mi,
                    monster_base=base,
                    monster_state=st,
                    skills_by_monster=skills_by_monster,
                    reason="PlayerPhaseReaction",
                )

    def _monster_act(
        self,
        battle_index: int,
        turn: int,
        party: PlayerPartySnapshot,
        monster_index: MonsterIndex,
        monster_base: MonsterBaseStat,
        monster_state: MonsterState,
        skills_by_monster: Dict[str, List[MonsterSkill]],
        reason: str,
    ) -> None:
        if monster_state.hp <= 0:
            return

        sk_list = skills_by_monster.get(monster_index.monster_id, [])
        if not sk_list:
            return

        # MVP: 只用第一個技能
        sk = sk_list[0]
        monster_state.has_acted_this_turn = True

        if sk.skill_type == MonsterSkillType.Attack:
            dmg = float(sk.value)
            old_hp, old_sh = party.team_hp, party.team_shield
            party.team_hp, party.team_shield = apply_damage(party.team_hp, party.team_shield, dmg)
            self._print_and_record_system(
                battle_index,
                turn,
                monster_index.monster_id,
                "EnemyAttack",
                f"[Damage] ({reason}) {monster_index.monster_id} -> Party "
                f"Dmg={dmg:.1f} | HP {old_hp:.1f}->{party.team_hp:.1f} Shield {old_sh:.1f}->{party.team_shield:.1f}",
            )

        elif sk.skill_type == MonsterSkillType.AddShield:
            old = monster_state.shield
            monster_state.shield = max(0.0, monster_state.shield + float(sk.value))
            self._print_and_record_system(
                battle_index,
                turn,
                monster_index.monster_id,
                "EnemyShield",
                f"[EnemyShield] ({reason}) +{float(sk.value):.1f} (Shield {old:.1f} -> {monster_state.shield:.1f})",
            )

    # =========================================================
    # Internal - End check
    # =========================================================
    def _get_winner(
        self,
        party: PlayerPartySnapshot,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
    ) -> Optional[str]:
        if party.team_hp <= 0:
            return "Enemy"
        if all(st.hp <= 0 for _, _, st in monsters):
            return "Player"
        return None

    # =========================================================
    # Reporter helpers (use BattleReporter.add_event)
    # =========================================================
    def _print_and_record_system(
        self,
        battle_index: int,
        turn: int,
        actor: str,
        event_type: str,
        message: str,
    ) -> None:
        self.log.info(message)

        # Reporter event log is optional (enable_event_log=False by default)
        payload: Dict[str, Any] = {
            "battle_index": battle_index,
            "turn": turn,
            "actor": actor,
            "event_type": event_type,
            "message": message,
        }
        self.reporter.add_event(payload)
