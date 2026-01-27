# ability_system.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ability_models import (
    AbilityDef,
    AbilityEffectType,
    ConditionGroupDef,
    ConditionLogic,
    ConditionRowDef,
    ConditionType,
    EffectGroupDef,
    EffectRowDef,
    ExecMode,
    StatusInstance,
    StatusParamKey,
    StatusType,
    TriggerEvent,
    ValueRefType,
)

EmitFn = Callable[[int, int, str, str, str], None]


@dataclass
class AbilityRuntimePack:
    abilities: List[AbilityDef]


class AbilitySystem:
    """
    Ability / Condition / Effect 執行引擎（MVP）
    """

    def __init__(
        self,
        abilities: Dict[str, AbilityDef],
        condition_groups: Dict[str, ConditionGroupDef],
        condition_rows_by_group: Dict[str, List[ConditionRowDef]],
        effect_groups: Dict[str, EffectGroupDef],
        effect_rows_by_group: Dict[str, List[EffectRowDef]],
        partner_abilities: Dict[str, List[str]],
        partner_stack_curves: Dict[str, Dict[str, List[float]]],
        default_max_partner_stack: int = 4,
    ) -> None:
        self.abilities = abilities
        self.condition_groups = condition_groups
        self.condition_rows_by_group = condition_rows_by_group
        self.effect_groups = effect_groups
        self.effect_rows_by_group = effect_rows_by_group
        self.partner_abilities = partner_abilities
        self.partner_stack_curves = partner_stack_curves
        self.default_max_partner_stack = int(default_max_partner_stack)

        self._proc_counter: Dict[Tuple[int, str], int] = {}

    # =========================================================
    # Public API (called by battle_simulator)
    # =========================================================
    def on_trigger(
        self,
        trigger_event: str,
        battle_index: int,
        turn: int,
        ctx: Dict[str, Any],
        emit: Optional[EmitFn] = None,
    ) -> None:
        try:
            trig = TriggerEvent(str(trigger_event))
        except Exception:
            return

        partner_id = ctx.get("partner_id")
        if not partner_id:
            return

        ability_ids = self.partner_abilities.get(str(partner_id), [])
        if not ability_ids:
            return

        defs: List[AbilityDef] = []
        for aid in ability_ids:
            ad = self.abilities.get(str(aid))
            if ad and ad.trigger_event == trig:
                defs.append(ad)

        if not defs:
            return

        defs.sort(key=lambda x: int(getattr(x, "priority", 0)))

        for ad in defs:
            ok, reason = self._eval_condition_group(ad.condition_group_id, ctx)
            if not ok:
                self._emit(
                    emit,
                    battle_index,
                    turn,
                    "Ability",
                    "CondFail",
                    f"[Ability] {ad.ability_id} condition failed: {reason}",
                )
                continue

            self._emit(
                emit,
                battle_index,
                turn,
                "Ability",
                "Proc",
                f"[Ability] {ad.ability_id} triggered by {trig.value}",
            )

            self._exec_effect_group(ad, battle_index, turn, ctx, emit)
            self._mark_procced(battle_index, ad.ability_id)

    # =========================================================
    # Conditions
    # =========================================================
    def _eval_condition_group(
        self, condition_group_id: Optional[str], ctx: Dict[str, Any]
    ) -> Tuple[bool, str]:
        if not condition_group_id:
            return True, "NoConditionGroup"

        gid = str(condition_group_id)
        g = self.condition_groups.get(gid)
        rows = self.condition_rows_by_group.get(gid, [])

        if not g or not rows:
            return True, "EmptyOrMissingConditionGroup"

        logic = g.logic

        results = [self._eval_condition_row(r, ctx) for r in rows]

        if logic == ConditionLogic.AND:
            for ok, reason in results:
                if not ok:
                    return False, reason
            return True, "AND:AllPass"

        for ok, _ in results:
            if ok:
                return True, "OR:OnePass"
        return False, "OR:AllFail"

    def _eval_condition_row(
        self, row: ConditionRowDef, ctx: Dict[str, Any]
    ) -> Tuple[bool, str]:
        if row.condition_type == ConditionType.OwnerClassEqualsPartnerClass:
            oc = ctx.get("owner_class")
            pc = ctx.get("partner_class")
            if oc is None or pc is None:
                return False, "ClassMissing"
            return (str(oc) == str(pc)), "ClassMatch" if str(oc) == str(pc) else "ClassMismatch"

        return False, f"UnsupportedConditionType({row.condition_type.value})"

    # =========================================================
    # Effects
    # =========================================================
    def _exec_effect_group(
        self,
        ability_def: AbilityDef,
        battle_index: int,
        turn: int,
        ctx: Dict[str, Any],
        emit: Optional[EmitFn],
    ) -> None:
        gid = str(ability_def.effect_group_id)
        rows = self.effect_rows_by_group.get(gid, [])
        if not rows:
            return

        current_status: Optional[StatusInstance] = None

        for r in rows:
            if r.effect_type == AbilityEffectType.AddStatus:
                stype = StatusType(str(r.value1))
                duration = int(r.value2 or 0)
                current_status = StatusInstance(
                    status_type=stype,
                    remaining_turns=duration,
                    params={},
                    source_ability_id=ability_def.ability_id,
                )
                ctx.setdefault("statuses", []).append(current_status)
                continue

            if r.effect_type == AbilityEffectType.SetStatusParam and current_status:
                key = str(r.value1)
                val = self._resolve_value(r, ctx)
                current_status.params[key] = float(val)
                self._apply_status_to_runtime_mod(current_status, ctx)

    def _apply_status_to_runtime_mod(self, status: StatusInstance, ctx: Dict[str, Any]) -> None:
        runtime_mod = ctx.setdefault("runtime_mod", {})
        if status.status_type == StatusType.AttackUp:
            inc = float(status.params.get(StatusParamKey.increase.value, 0.0))
            cur = float(runtime_mod.get("player_damage_multiplier", 1.0))
            runtime_mod["player_damage_multiplier"] = cur * (1.0 + inc)

    # =========================================================
    # Value resolve
    # =========================================================
    def _resolve_value(self, row: EffectRowDef, ctx: Dict[str, Any]) -> float:
        if row.value_ref_type in (None, ValueRefType.None_):
            return float(row.value2 or 0)

        if row.value_ref_type == ValueRefType.PartnerStack:
            partner_id = str(ctx.get("partner_id") or "")
            curve_id = str(row.value_ref_id or "")
            stack = int(ctx.get("partner_stack_count", 0))
            return float(self._get_partner_stack_value(partner_id, curve_id, stack))

        return float(row.value2 or 0)

    def _get_partner_stack_value(self, partner_id: str, curve_id: str, stack: int) -> float:
        curves = self.partner_stack_curves.get(partner_id, {})
        values = curves.get(curve_id)
        if not values:
            return 0.0
        max_stack = min(len(values) - 1, self.default_max_partner_stack)
        s = max(0, min(int(stack), int(max_stack)))
        return float(values[s])

    # =========================================================
    # Proc helpers
    # =========================================================
    def _mark_procced(self, battle_index: int, ability_id: str) -> None:
        key = (int(battle_index), str(ability_id))
        self._proc_counter[key] = self._proc_counter.get(key, 0) + 1

    # =========================================================
    # Emit
    # =========================================================
    def _emit(
        self,
        emit: Optional[EmitFn],
        battle_index: int,
        turn: int,
        actor: str,
        event_type: str,
        message: str,
    ) -> None:
        if emit:
            emit(battle_index, turn, actor, event_type, message)
