# battle_simulator.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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

    # 若為 True: 當下一張卡牌費用 > 剩餘 AP 時，停止玩家階段。
    # 若為 False: 跳過該卡牌直到找到可負擔的卡牌 (MVP 預設保持 True)。
    stop_when_insufficient_ap: bool = True


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
        # 防呆：即使沒有傷害，也確保不會回傳負值
        return max(0.0, hp), max(0.0, shield)

    remaining = dmg
    if shield > 0:
        used = min(shield, remaining)
        shield -= used
        remaining -= used

    if remaining > 0:
        hp -= remaining

    # 防呆：避免出現 hp / shield < 0，讓 log / 報表更乾淨
    return max(0.0, hp), max(0.0, shield)
    remaining -= used
    if remaining > 0:
        hp -= remaining
    return hp, shield


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
    - AP 系統 (最大 AP=3)，每張卡牌有 AP 消耗
    - 計數器觸發: 玩家打出任意卡牌時 (OnPlayerPlayCard)
    - 反應機制: 若玩家階段計數器歸零且怪物尚未行動 => 立即行動一次
    - 敵方階段規則 (ActIfNotActedThisTurn): 若本回合尚未行動且計數器 > 0 => 在敵方階段行動一次
    - 重置時機 (AfterEnemyAttackPhase): 怪物本回合行動後，於敵方階段結束時重置計數器
    - 詳細日誌記錄於 BattleReporter EventLog；控制台也會印出流程
    """

    def __init__(self, config: BattleConfig, reporter: BattleReporter) -> None:
        self.config = config
        self.reporter = reporter
        self.log = BattleLogger(config.log_level)

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

        # --------------------------
        # Init logs
        # 初始化日誌
        # --------------------------
        self._print_and_record_system(
            battle_index, 0, "System", "BattleStart",
            f"=== Battle {battle_index} Start ==="
        )
        self._print_and_record_system(
            battle_index, 0, "System", "Init",
            f"[Init] PartyHP={party_runtime.team_hp:.1f}/{party_runtime.team_hp_max:.1f} "
            f"Shield={party_runtime.team_shield:.1f} Active={active_member.character_id}"
        )
        self._print_and_record_system(
            battle_index, 0, "System", "InitEnemies",
            "[Init] Enemies=" + ", ".join(
                [f"{mi.monster_id}(HP={st.hp:.1f},C={st.counter})" for mi, _, st in monsters]
            )
        )

        if not party_cards:
            raise ValueError("❌ No cards for party. Check Card sheet CharacterId filters.")

        # 決定性的發牌順序 (依 card_id 排序，確保每次模擬一致)
        card_order = sorted(party_cards, key=lambda c: (c.character_id, c.card_id))
        card_cursor = 0

        turn = 1
        while turn <= self.config.max_turns:
            # 每回合開始時，重置怪物的「已行動」標記
            for _, _, mst in monsters:
                mst.has_acted_this_turn = False

            ap = self.config.ap_max

            self._print_and_record_system(
                battle_index, turn, "System", "TurnStart",
                f"[Battle {battle_index}][T{turn:02d}] Turn Start (AP={ap})",
            )

            # ==========================
            # Player Phase (AP driven)
            # 玩家階段 (AP 驅動)
            # ==========================
            self._print_and_record_system(
                battle_index, turn, "Player", "PhaseStart",
                f"[Battle {battle_index}][T{turn:02d}][Player] Start (AP={ap})",
            )

            while ap > 0:
                card = card_order[card_cursor % len(card_order)]
                card_cursor += 1

                cost = max(0, int(card.ap_cost))
                if cost > ap:
                    msg = (
                        f"[Battle {battle_index}][T{turn:02d}][AP] "
                        f"Insufficient AP for {card.card_id} cost={cost} AP={ap}"
                    )
                    self._print_and_record(
                        battle_index, turn, "Player", "APStop", msg,
                        actor=active_member.character_id,
                        card_id=card.card_id,
                        ap_before=ap, ap_after=ap,
                    )
                    if self.config.stop_when_insufficient_ap:
                        break
                    else:
                        continue

                ap_before = ap
                ap -= cost

                msg = (
                    f"[Battle {battle_index}][T{turn:02d}][Player] "
                    f"Play {card.card_id} (cost={cost}, AP {ap_before}->{ap})"
                )
                self._print_and_record(
                    battle_index, turn, "Player", "PlayCard", msg,
                    actor=active_member.character_id,
                    card_id=card.card_id,
                    ap_before=ap_before, ap_after=ap,
                    player_hp_before=party_runtime.team_hp,
                    player_shield_before=party_runtime.team_shield,
                )

                # 依序套用卡牌效果
                effects = card_effects_by_id.get(card.card_id, [])
                for eff in effects:
                    self._apply_card_effect(
                        battle_index=battle_index,
                        turn=turn,
                        party=party_runtime,
                        active_member=active_member,
                        monsters=monsters,
                        card=card,
                        eff=eff,
                    )
                    if self._is_battle_end(party_runtime, monsters):
                        winner = self._get_winner(party_runtime, monsters)
                        return self._finalize_battle(battle_index, turn, winner, party_runtime, monsters)

                # 每打出一張卡牌 (任意卡牌)，觸發一次計數器檢查
                self._tick_counters_on_player_play_card(
                    battle_index=battle_index,
                    turn=turn,
                    party=party_runtime,
                    monsters=monsters,
                    skills_by_monster=skills_by_monster,
                )
                if self._is_battle_end(party_runtime, monsters):
                    winner = self._get_winner(party_runtime, monsters)
                    return self._finalize_battle(battle_index, turn, winner, party_runtime, monsters)

            self._print_and_record_system(
                battle_index, turn, "Player", "PhaseEnd",
                f"[Battle {battle_index}][T{turn:02d}][Player] End",
            )

            if self._is_battle_end(party_runtime, monsters):
                winner = self._get_winner(party_runtime, monsters)
                return self._finalize_battle(battle_index, turn, winner, party_runtime, monsters)

            # ==========================
            # Enemy Phase (fallback)
            # 敵方階段 (補行動)
            # ==========================
            self._print_and_record_system(
                battle_index, turn, "EnemyPhase", "PhaseStart",
                f"[Battle {battle_index}][T{turn:02d}][EnemyPhase] Start",
            )

            # 針對尚未行動且計數器 > 0 的怪物執行補救行動 (Fallback Action)
            for mi, _, mst in monsters:
                if mst.hp <= 0:
                    continue
                sk_list = skills_by_monster.get(mi.monster_id, [])
                if not sk_list:
                    continue
                active_skill = sk_list[0]

                if active_skill.enemy_phase_action_rule == EnemyPhaseActionRule.ActIfNotActedThisTurn:
                    if (not mst.has_acted_this_turn) and mst.counter > 0:
                        msg = (
                            f"[Battle {battle_index}][T{turn:02d}][EnemyPhase] "
                            f"{mi.monster_id} fallback act (counter={mst.counter})"
                        )
                        self._print_and_record(
                            battle_index, turn, "EnemyPhase", "FallbackAct", msg,
                            actor=mi.monster_id,
                            monster_id=mi.monster_id,
                            counter_before=mst.counter,
                        )
                        self._monster_act(
                            battle_index=battle_index,
                            turn=turn,
                            party=party_runtime,
                            monster_index=mi,
                            monster_state=mst,
                            skill=active_skill,
                            reason="EnemyPhaseFallback",
                        )
                        if self._is_battle_end(party_runtime, monsters):
                            winner = self._get_winner(party_runtime, monsters)
                            return self._finalize_battle(battle_index, turn, winner, party_runtime, monsters)

            # 敵方攻擊階段結束後重置計數器 (MVP: 重置本回合有行動的怪物)
            for mi, _, mst in monsters:
                if mst.hp <= 0:
                    continue
                if mst.has_acted_this_turn:
                    sk_list = skills_by_monster.get(mi.monster_id, [])
                    if not sk_list:
                        continue
                    active_skill = sk_list[0]
                    if active_skill.reload_timing == ReloadTiming.AfterEnemyAttackPhase:
                        before = mst.counter
                        mst.counter_max = int(active_skill.counter_max)
                        mst.counter = int(active_skill.counter_max)
                        msg = f"[Battle {battle_index}][T{turn:02d}][Reload] {mi.monster_id} {before}->{mst.counter}"
                        self._print_and_record(
                            battle_index, turn, "EnemyPhase", "Reload", msg,
                            actor=mi.monster_id,
                            monster_id=mi.monster_id,
                            counter_before=before,
                            counter_after=mst.counter,
                        )

            self._print_and_record_system(
                battle_index, turn, "EnemyPhase", "PhaseEnd",
                f"[Battle {battle_index}][T{turn:02d}][EnemyPhase] End",
            )

            if self._is_battle_end(party_runtime, monsters):
                winner = self._get_winner(party_runtime, monsters)
                return self._finalize_battle(battle_index, turn, winner, party_runtime, monsters)

            turn += 1

        # 超過最大回合數，強制結束
        winner = "Unknown"
        return self._finalize_battle(battle_index, turn, winner, party_runtime, monsters)

    # =========================================================
    # Card effect application
    # =========================================================
    def _get_scale_base(self, party: PlayerPartySnapshot, active_member: Any, stat: ScaleStat) -> float:
        if stat == ScaleStat.ATK:
            return float(active_member.final_atk)
        if stat == ScaleStat.DEF:
            return float(active_member.final_def)
        if stat == ScaleStat.HP:
            # MVP: 共用血條系統使用隊伍最大血量
            return float(party.team_hp_max)
        return 0.0

    def _apply_card_effect(
        self,
        battle_index: int,
        turn: int,
        party: PlayerPartySnapshot,
        active_member: Any,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
        card: Card,
        eff: CardEffect,
    ) -> None:
        base = self._get_scale_base(party, active_member, eff.scale_stat)
        value = base * float(eff.multiplier) + float(eff.flat_value)

        if eff.effect_type == EffectType.Damage:
            # 傷害效果: 優先扣除護盾，再扣除血量
            if eff.target == TargetType.EnemyAll:
                for mi, _, mst in monsters:
                    if mst.hp <= 0:
                        continue
                    hp_b, sh_b = mst.hp, mst.shield
                    mst.hp, mst.shield = apply_damage(mst.hp, mst.shield, value)
                    msg = (
                        f"[Battle {battle_index}][T{turn:02d}][CardDamage] {card.card_id} -> {mi.monster_id} "
                        f"dmg={value:.1f} (Shield {sh_b:.1f}->{mst.shield:.1f}, HP {hp_b:.1f}->{mst.hp:.1f})"
                    )
                    self._print_and_record(
                        battle_index, turn, "Player", "Damage", msg,
                        actor=active_member.character_id,
                        card_id=card.card_id,
                        monster_id=mi.monster_id,
                        target="EnemyAll",
                        value=float(value),
                        enemy_hp_before=hp_b, enemy_hp_after=mst.hp,
                        enemy_shield_before=sh_b, enemy_shield_after=mst.shield,
                        player_hp_before=party.team_hp, player_hp_after=party.team_hp,
                        player_shield_before=party.team_shield, player_shield_after=party.team_shield,
                    )
            else:
                pick = pick_enemy_single(monsters)
                if pick is None:
                    return
                mi, _, mst = pick
                hp_b, sh_b = mst.hp, mst.shield
                mst.hp, mst.shield = apply_damage(mst.hp, mst.shield, value)
                msg = (
                    f"[Battle {battle_index}][T{turn:02d}][CardDamage] {card.card_id} -> {mi.monster_id} "
                    f"dmg={value:.1f} (Shield {sh_b:.1f}->{mst.shield:.1f}, HP {hp_b:.1f}->{mst.hp:.1f})"
                )
                self._print_and_record(
                    battle_index, turn, "Player", "Damage", msg,
                    actor=active_member.character_id,
                    card_id=card.card_id,
                    monster_id=mi.monster_id,
                    target="EnemySingle",
                    value=float(value),
                    enemy_hp_before=hp_b, enemy_hp_after=mst.hp,
                    enemy_shield_before=sh_b, enemy_shield_after=mst.shield,
                )

        elif eff.effect_type == EffectType.Shield:
            # 護盾效果: 增加隊伍共用護盾
            sh_b = party.team_shield
            party.team_shield += float(value)
            msg = f"[Battle {battle_index}][T{turn:02d}][CardShield] +{value:.1f} (Shield {sh_b:.1f}->{party.team_shield:.1f})"
            self._print_and_record(
                battle_index, turn, "Player", "Shield", msg,
                actor=active_member.character_id,
                card_id=card.card_id,
                target="Party",
                value=float(value),
                player_shield_before=sh_b,
                player_shield_after=party.team_shield,
                player_hp_before=party.team_hp,
                player_hp_after=party.team_hp,
            )

        elif eff.effect_type == EffectType.Heal:
            # 治療效果: 恢復隊伍血量，不超過上限
            hp_b = party.team_hp
            party.team_hp = clamp(party.team_hp + float(value), 0.0, party.team_hp_max)
            msg = f"[Battle {battle_index}][T{turn:02d}][CardHeal] +{value:.1f} (HP {hp_b:.1f}->{party.team_hp:.1f})"
            self._print_and_record(
                battle_index, turn, "Player", "Heal", msg,
                actor=active_member.character_id,
                card_id=card.card_id,
                target="Party",
                value=float(value),
                player_hp_before=hp_b,
                player_hp_after=party.team_hp,
            )
        else:
            self.log.debug(f"[Battle {battle_index}][T{turn:02d}][CardEffect] Unsupported {eff.effect_type} ignored")

    # =========================================================
    # Counter tick + reaction
    # =========================================================
    def _tick_counters_on_player_play_card(
        self,
        battle_index: int,
        turn: int,
        party: PlayerPartySnapshot,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
        skills_by_monster: Dict[str, List[MonsterSkill]],
    ) -> None:
        for mi, _, mst in monsters:
            if mst.hp <= 0:
                continue
            sk_list = skills_by_monster.get(mi.monster_id, [])
            if not sk_list:
                continue
            skill = sk_list[0]

            # MVP 支援: 啟用狀態 + 玩家打出卡牌時觸發
            if skill.counter_mode != CounterMode.Enabled:
                continue
            if skill.counter_start_trigger != CounterStartTrigger.OnPlayerPlayCard:
                continue

            before = mst.counter
            mst.counter = max(0, mst.counter - 1)

            msg = f"[Battle {battle_index}][T{turn:02d}][Counter] {mi.monster_id} {before}->{mst.counter} (OnPlayerPlayCard)"
            self._print_and_record(
                battle_index, turn, "Player", "Counter", msg,
                actor=mi.monster_id,
                monster_id=mi.monster_id,
                counter_before=before,
                counter_after=mst.counter,
            )

            # 反應機制: 若在玩家階段計數器歸零，且本回合尚未行動，則立即反擊
            if mst.counter == 0 and (not mst.has_acted_this_turn):
                msg2 = f"[Battle {battle_index}][T{turn:02d}][Reaction] {mi.monster_id} counter==0 => retaliate now"
                self._print_and_record(
                    battle_index, turn, "Reaction", "Retaliate", msg2,
                    actor=mi.monster_id,
                    monster_id=mi.monster_id,
                )
                self._monster_act(
                    battle_index=battle_index,
                    turn=turn,
                    party=party,
                    monster_index=mi,
                    monster_state=mst,
                    skill=skill,
                    reason="PlayerPhaseReaction",
                )

    # =========================================================
    # Monster action
    # =========================================================
    def _monster_act(
        self,
        battle_index: int,
        turn: int,
        party: PlayerPartySnapshot,
        monster_index: MonsterIndex,
        monster_state: MonsterState,
        skill: MonsterSkill,
        reason: str,
    ) -> None:
        mid = monster_index.monster_id

        if skill.skill_type == MonsterSkillType.Attack and skill.target == TargetType.Player:
            hp_b = party.team_hp
            sh_b = party.team_shield

            party.team_hp, party.team_shield = apply_damage(
                party.team_hp, party.team_shield, float(skill.value)
            )

            msg = (
                f"[Battle {battle_index}][T{turn:02d}][EnemyAttack:{reason}] {mid} -> Party "
                f"dmg={float(skill.value):.1f} (Shield {sh_b:.1f}->{party.team_shield:.1f}, HP {hp_b:.1f}->{party.team_hp:.1f})"
            )
            self._print_and_record(
                battle_index, turn,
                "EnemyPhase" if "EnemyPhase" in reason else "Reaction",
                "EnemyAttack",
                msg,
                actor=mid,
                monster_id=mid,
                target="Party",
                value=float(skill.value),
                player_hp_before=hp_b,
                player_hp_after=party.team_hp,
                player_shield_before=sh_b,
                player_shield_after=party.team_shield,
            )
            monster_state.has_acted_this_turn = True

        elif skill.skill_type == MonsterSkillType.AddShield and skill.target == TargetType.Self:
            sh_b = monster_state.shield
            monster_state.shield += float(skill.value)
            msg = (
                f"[Battle {battle_index}][T{turn:02d}][EnemyShield:{reason}] {mid} +{float(skill.value):.1f} "
                f"(Shield {sh_b:.1f}->{monster_state.shield:.1f})"
            )
            self._print_and_record(
                battle_index, turn,
                "EnemyPhase" if "EnemyPhase" in reason else "Reaction",
                "EnemyShield",
                msg,
                actor=mid,
                monster_id=mid,
                target="Self",
                value=float(skill.value),
                enemy_shield_before=sh_b,
                enemy_shield_after=monster_state.shield,
            )
            monster_state.has_acted_this_turn = True

        else:
            # 不支援的技能類型視為已行動 (避免在 fallback 迴圈中無限執行)
            msg = f"[Battle {battle_index}][T{turn:02d}][EnemyAct:{reason}] {mid} unsupported skill={skill.skill_type}/{skill.target} (ignored)"
            self._print_and_record(
                battle_index, turn,
                "EnemyPhase" if "EnemyPhase" in reason else "Reaction",
                "EnemyAct",
                msg,
                actor=mid,
                monster_id=mid,
            )
            monster_state.has_acted_this_turn = True

    # =========================================================
    # End / Result helpers
    # =========================================================
    def _is_battle_end(
        self,
        party: PlayerPartySnapshot,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
    ) -> bool:
        if party.team_hp <= 0:
            return True
        alive = sum(1 for _, _, mst in monsters if mst.hp > 0)
        return alive == 0

    def _get_winner(
        self,
        party: PlayerPartySnapshot,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
    ) -> str:
        if party.team_hp <= 0:
            return "Enemy"
        alive = sum(1 for _, _, mst in monsters if mst.hp > 0)
        return "Player" if alive == 0 else "Unknown"

    def _finalize_battle(
        self,
        battle_index: int,
        turn: int,
        winner: str,
        party: PlayerPartySnapshot,
        monsters: List[Tuple[MonsterIndex, MonsterBaseStat, MonsterState]],
    ) -> BattleResult:
        enemies_alive = sum(1 for _, _, mst in monsters if mst.hp > 0)
        msg = (
            f"=== Battle {battle_index} End === Winner={winner} Turns={turn} "
            f"PartyHP={party.team_hp:.1f} EnemiesAlive={enemies_alive}"
        )
        self._print_and_record_system(battle_index, turn, "System", "BattleEnd", msg)

        # 記錄摘要列
        if hasattr(self.reporter, "add_summary"):
            self.reporter.add_summary(
                battle_index=battle_index,
                winner=winner,
                turns=turn,
                player_hp_end=float(party.team_hp),
                enemies_alive=int(enemies_alive),
            )

        return BattleResult(
            battle_index=battle_index,
            winner=winner,
            turns=turn,
            player_hp_end=float(party.team_hp),
            enemies_alive=int(enemies_alive),
        )

    # =========================================================
    # Logging bridge (console + reporter)
    # =========================================================
    def _print_and_record_system(
        self,
        battle_index: int,
        turn: int,
        phase: str,
        action_type: str,
        msg: str,
    ) -> None:
        # 控制台輸出
        self.log.info(msg)

        # 報表記錄 (系統訊息)
        payload = {
            "battle_index": battle_index,
            "turn": turn,
            "phase": phase,
            "action_type": action_type,
            "msg": msg,
        }
        self._report_event(payload)

    def _print_and_record(
        self,
        battle_index: int,
        turn: int,
        phase: str,
        action_type: str,
        msg: str,
        **fields: Any,
    ) -> None:
        # 控制台詳細度控制:
        # - INFO: 印出主要訊息
        # - DEBUG/TRACE: 也印出訊息 (目前相同，未來可擴充)
        self.log.info(msg)

        payload: Dict[str, Any] = {
            "battle_index": battle_index,
            "turn": turn,
            "phase": phase,
            "action_type": action_type,
            "msg": msg,
        }
        payload.update(fields)

        self._report_event(payload)

    def _report_event(self, payload: Dict[str, Any]) -> None:
        """
        報表轉接器 (Reporter Adapter):
        - 若 BattleReporter 有 add_event(payload_dict): 使用之
        - 若有 record_event(**kwargs): 使用之
        - 否則: 忽略 (確保模擬器不會因報表介面不符而崩潰)
        """
        if self.reporter is None:
            return

        if hasattr(self.reporter, "add_event"):
            try:
                # expected: add_event(dict)
                self.reporter.add_event(payload)
                return
            except TypeError:
                # maybe add_event(**kwargs)
                try:
                    self.reporter.add_event(**payload)
                    return
                except Exception:
                    return

        if hasattr(self.reporter, "record_event"):
            try:
                self.reporter.record_event(**payload)
            except Exception:
                return
