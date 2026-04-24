# ability_system.py
from __future__ import annotations

from typing import Dict, Any, List, Optional, Iterable

from ability_models import (
    AbilityDef,
    ConditionGroupDef,
    ConditionRowDef,
    EffectGroupDef,
    EffectRowDef,
    AbilityEffectType,
    TriggerEvent,
    ConditionType,
    ValueRefType,
    StatusType,
    StatusInstance,
)


class AbilitySystem:
    """
    Data-driven ability runner.

    Key ideas:
    - ability_context: persistent state for the whole battle
        - extra_ctx: dict (cross-turn state like arwen_points)
        - statuses: list
        - partner_abilities: Dict[PartnerId, List[AbilityId]]
        - partner_stack_curves: Dict[PartnerId, Dict[StatTypeId, List[float]]]
    - ctx: per-trigger runtime state
        - runtime_mod: dict (per trigger / per phase modifiers)
        - partner_id, partner_stack_count, owner_class, partner_class ...
    """

    def __init__(
        self,
        ability_defs: List[AbilityDef],
        condition_groups: Dict[str, ConditionGroupDef],
        condition_rows: List[ConditionRowDef],
        effect_groups: Dict[str, EffectGroupDef],
        effect_rows: List[EffectRowDef],
    ):
        self.ability_defs = ability_defs
        self.condition_groups = condition_groups
        self.condition_rows = condition_rows
        self.effect_groups = effect_groups
        self.effect_rows = effect_rows

        # Pre-index
        self._conditions_by_group: Dict[str, List[ConditionRowDef]] = {}
        for row in self.condition_rows:
            self._conditions_by_group.setdefault(row.condition_group_id, []).append(row)

        self._effects_by_group: Dict[str, List[EffectRowDef]] = {}
        for row in self.effect_rows:
            self._effects_by_group.setdefault(row.effect_group_id, []).append(row)

        self._ability_by_id: Dict[str, AbilityDef] = {a.ability_id: a for a in self.ability_defs}

    # =========================================================
    # Public API
    # =========================================================

    def on_trigger(
        self,
        trigger_event: TriggerEvent,
        *,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
    ) -> None:
        """
        Entry point called by battle_simulator.

        ctx:
            runtime context (per trigger)
            - runtime_mod: Dict[str, float]
            - partner_id / partner_stack_count / owner_class / partner_class ...

        ability_context:
            persistent battle context
            - extra_ctx: Dict[str, Any]
            - statuses: List[StatusInstance]
            - partner_abilities: Dict[str, List[str]]
            - partner_stack_curves: Dict[str, Dict[str, List[float]]]
        """
        ability_context.setdefault("extra_ctx", {})
        ability_context.setdefault("statuses", [])
        ability_context.setdefault("partner_abilities", {})
        ability_context.setdefault("partner_stack_curves", {})

        # Decide which abilities are active for this trigger
        for ability in self._iter_active_abilities(trigger_event, ctx, ability_context):
            if not self._check_conditions(ability, ctx, ability_context):
                continue
            self._exec_effect_group(ability, ctx, ability_context)

    # =========================================================
    # Ability filtering
    # =========================================================

    def _iter_active_abilities(
        self,
        trigger_event: TriggerEvent,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
    ) -> Iterable[AbilityDef]:
        """
        IMPORTANT:
        - We only execute Partner-bound abilities of the currently equipped partner_id.
        - This makes the system truly "table-driven": PartnerAbility decides what runs.
        - ❌ 未實作：Character / Equipment / Card / Monster source_type 的 Ability
          在此完全不會被迭代到，即使 Excel 有填資料也不會觸發。
          需要額外建立各 source_type 的索引結構（如 character_abilities dict）並在此加入對應查找分支。
        - ❌ 未實作：apply_phase 未被檢查，PRE_BATTLE 與 RUNTIME 的 Ability 行為完全相同。
        """
        partner_id = ctx.get("partner_id") or ability_context.get("partner_id")
        if not partner_id:
            return []

        partner_id = str(partner_id)

        partner_abilities: Dict[str, List[str]] = ability_context.get("partner_abilities", {}) or {}
        active_ids = partner_abilities.get(partner_id, [])

        # Keep order stable:
        # 1) filter by trigger_event
        # 2) sort by priority desc, then id
        defs: List[AbilityDef] = []
        for aid in active_ids:
            a = self._ability_by_id.get(aid)
            if not a or not a.enabled:
                continue
            if a.trigger_event != trigger_event:
                continue
            defs.append(a)

        defs.sort(key=lambda x: (-int(x.priority), x.ability_id))
        return defs

    # =========================================================
    # Condition evaluation
    # =========================================================

    def _check_conditions(
        self,
        ability: AbilityDef,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
    ) -> bool:
        if not ability.condition_group_id:
            return True

        group = self.condition_groups.get(ability.condition_group_id)
        if not group:
            return True

        rows = self._conditions_by_group.get(group.condition_group_id, [])
        results: List[bool] = []

        for row in rows:
            result = self._eval_condition_row(row, ctx, ability_context)
            results.append(result)

        # ConditionLogic values are string enums; be tolerant
        if str(getattr(group, "logic", "AND")) == "AND":
            return all(results)
        return any(results)

    def _eval_condition_row(
        self,
        row: ConditionRowDef,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
    ) -> bool:
        if row.condition_type == ConditionType.OwnerClassEqualsPartnerClass:
            owner_class = ctx.get("owner_class")
            partner_class = ctx.get("partner_class")
            return owner_class is not None and owner_class == partner_class

        # Unsupported condition
        return False

    # =========================================================
    # Effect execution
    # =========================================================

    def _exec_effect_group(
        self,
        ability: AbilityDef,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
    ) -> None:
        group = self.effect_groups.get(ability.effect_group_id)
        if not group:
            return

        rows = self._effects_by_group.get(group.effect_group_id, [])
        for row in rows:
            self._exec_effect_row(ability, row, ctx, ability_context)

    # --------------------------
    # Value helpers
    # --------------------------

    def _clamp_index(self, idx: int, n: int) -> int:
        if n <= 0:
            return 0
        if idx < 0:
            return 0
        if idx >= n:
            return n - 1
        return idx

    def _resolve_partner_stack_value(
        self,
        *,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
        stat_type_id: str,
    ) -> float:
        """
        Read stack value by:
        - partner_id
        - partner_stack_count (from CombatInputPanel)
        - partner_stack_curves[partner_id][stat_type_id] -> list[float]
        """
        partner_id = ctx.get("partner_id") or ability_context.get("partner_id")
        if not partner_id:
            return 0.0
        partner_id = str(partner_id)

        curves: Dict[str, Dict[str, List[float]]] = ability_context.get("partner_stack_curves", {}) or {}
        by_partner = curves.get(partner_id, {})
        values = by_partner.get(stat_type_id)
        if not values:
            return 0.0

        stack_count = int(ctx.get("partner_stack_count", ability_context.get("partner_stack_count", 0)) or 0)
        i = self._clamp_index(stack_count, len(values))
        try:
            return float(values[i])
        except Exception:
            return 0.0

    def _resolve_value(
        self,
        *,
        row: EffectRowDef,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
        default: float = 0.0,
    ) -> float:
        """
        Resolve numeric value for effect row:
        - ValueRefType.None_ -> use row.value2
        - ValueRefType.PartnerStack -> use partner stack curves by row.value_ref_id (StatTypeId)
        """
        if row.value_ref_type == ValueRefType.PartnerStack:
            stat_type_id = row.value_ref_id
            if not stat_type_id:
                return default
            return self._resolve_partner_stack_value(
                ctx=ctx, ability_context=ability_context, stat_type_id=str(stat_type_id)
            )

        # default: constant
        if row.value2 is None:
            return default
        try:
            return float(row.value2)
        except Exception:
            return default

    # --------------------------
    # Row executor
    # --------------------------

    def _exec_effect_row(
        self,
        ability: AbilityDef,
        row: EffectRowDef,
        ctx: Dict[str, Any],
        ability_context: Dict[str, Any],
    ) -> None:
        effect_type = row.effect_type

        # Ensure holders exist
        ability_context.setdefault("extra_ctx", {})
        ability_context.setdefault("statuses", [])
        ctx.setdefault("runtime_mod", {})

        extra_ctx: Dict[str, Any] = ability_context["extra_ctx"]
        runtime_mod: Dict[str, Any] = ctx["runtime_mod"]

        # -----------------------------------------------------
        # Status-based effects (Douglas legacy)
        # -----------------------------------------------------
        if effect_type == AbilityEffectType.AddStatus:
            if not row.value1:
                return
            status_type = StatusType(row.value1)
            duration = int(row.value2 or 0)

            status = StatusInstance(
                status_type=status_type,
                remaining_turns=duration,
                params={},
                source_ability_id=ability.ability_id,
            )
            ability_context["statuses"].append(status)
            return

        if effect_type == AbilityEffectType.SetStatusParam:
            key = row.value1
            if not key:
                return

            value = self._resolve_value(row=row, ctx=ctx, ability_context=ability_context, default=0.0)

            for status in ability_context["statuses"]:
                if status.source_ability_id != ability.ability_id:
                    continue

                status.params[key] = value

                # MVP: AttackUp -> player_damage_multiplier
                if status.status_type == StatusType.AttackUp:
                    runtime_mod["player_damage_multiplier"] = (
                        float(runtime_mod.get("player_damage_multiplier", 1.0)) + float(value)
                    )
            return

        # -----------------------------------------------------
        # Persistent battle state (extra_ctx)
        # -----------------------------------------------------
        if effect_type == AbilityEffectType.SetExtraValue:
            key = row.value1
            if not key:
                return
            value = self._resolve_value(row=row, ctx=ctx, ability_context=ability_context, default=0.0)
            extra_ctx[str(key)] = value
            return

        if effect_type == AbilityEffectType.AddExtraValue:
            key = row.value1
            if not key:
                return
            value = self._resolve_value(row=row, ctx=ctx, ability_context=ability_context, default=0.0)
            prev = extra_ctx.get(str(key), 0)
            try:
                extra_ctx[str(key)] = float(prev) + float(value)
            except Exception:
                # if prev isn't numeric, overwrite
                extra_ctx[str(key)] = value
            return

        # -----------------------------------------------------
        # Runtime mods
        # -----------------------------------------------------
        if effect_type == AbilityEffectType.SetRuntimeMod:
            key = row.value1
            if not key:
                return
            value = self._resolve_value(row=row, ctx=ctx, ability_context=ability_context, default=0.0)
            runtime_mod[str(key)] = value
            return

        # -----------------------------------------------------
        # Arwen special: consume points on hit -> reduce incoming damage
        # -----------------------------------------------------
        if effect_type == AbilityEffectType.ConsumeExtraPointAndSetIncomingDamageMul:
            points_key = row.value1
            if not points_key:
                return

            # damage_mul can be constant or PartnerStack
            damage_mul = self._resolve_value(row=row, ctx=ctx, ability_context=ability_context, default=1.0)
            incoming_key = row.value_ref_id or "incoming_damage_multiplier"

            current = extra_ctx.get(points_key, 0)
            try:
                current_n = int(float(current))
            except Exception:
                current_n = 0

            if current_n > 0:
                extra_ctx[points_key] = current_n - 1
                runtime_mod[incoming_key] = float(damage_mul)
            else:
                runtime_mod[incoming_key] = 1.0
            return

        # Unknown effect type -> no-op
        return
