# battle_reporter.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json
import re

import pandas as pd


# Excel cell text limit
_EXCEL_CELL_CHAR_LIMIT = 32767

# Excel formula-like prefixes (can trigger "formula" parsing / injection)
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def make_default_report_name(prefix: str = "battle_report") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.xlsx"


def _sanitize_excel_text(value: Any) -> Any:
    """
    Make value safe for Excel:
    - Convert non-primitive to string (JSON if dict/list)
    - Prevent formula interpretation: if text starts with =,+,-,@ then prefix with '
    - Truncate long strings to Excel cell limit
    """
    if value is None:
        return ""

    # Keep numbers / bool as-is
    if isinstance(value, (int, float, bool)):
        return value

    # Dict/List -> JSON string
    if isinstance(value, (dict, list)):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except Exception:
            value = str(value)

    # Everything else -> string
    if not isinstance(value, str):
        value = str(value)

    # Normalize newlines (helps XML stability)
    value = value.replace("\r\n", "\n").replace("\r", "\n")

    # Prevent Excel interpreting as formula
    if value.startswith(_FORMULA_PREFIXES):
        value = "'" + value

    # Truncate to Excel cell limit
    if len(value) > _EXCEL_CELL_CHAR_LIMIT:
        head = value[:20000]
        tail = value[-5000:]
        value = f"{head}\n...TRUNCATED...\n{tail}"
        value = value[:_EXCEL_CELL_CHAR_LIMIT]

    return value


@dataclass
class AbilityBattleMetrics:
    # Generic
    ability_triggered: bool = False
    ability_trigger_message: Optional[str] = None

    # Douglas / outgoing damage
    damage_before_multiplier: Optional[float] = None
    damage_after_multiplier: Optional[float] = None
    damage_mul_apply_count: int = 0

    # Arwen / healing bonus
    heal_before_multiplier: Optional[float] = None
    heal_after_multiplier: Optional[float] = None
    heal_mul_apply_count: int = 0

    # Arwen / points & mitigation
    arwen_points_init: Optional[int] = None
    arwen_points_last: Optional[int] = None
    arwen_consume_count: int = 0
    incoming_mitigation_apply_count: int = 0
    last_incoming_mul: Optional[float] = None


class BattleReporter:
    """
    Excel Report Sheets:
    - Summary: one row per battle result
    - Config: key/value pairs for this run
    - EventLog: raw events (optional, potentially huge)

    Auto-capture ability debug signals from EventLog (even if EventLog disabled)
    and write into Summary.

    This reporter is tolerant: it relies on message text patterns rather than strict enums.
    """

    # -------------------------
    # Regex patterns (tolerant)
    # -------------------------

    # Example (from battle_simulator.py):
    # [Ability] Before trigger: player_damage_multiplier=1.0 healing_multiplier=1.0
    _re_before = re.compile(
        r"Before trigger:\s*player_damage_multiplier=([0-9]*\.?[0-9]+)\s+healing_multiplier=([0-9]*\.?[0-9]+)"
    )

    # Example:
    # [Ability] After trigger: player_damage_multiplier=1.16 healing_multiplier=1.08 (extra_ctx_keys=[...])
    _re_after = re.compile(
        r"After trigger:\s*player_damage_multiplier=([0-9]*\.?[0-9]+)\s+healing_multiplier=([0-9]*\.?[0-9]+)"
    )

    # Example:
    # [Ability] Apply player_damage_multiplier=1.16 to damage value
    _re_apply_damage = re.compile(
        r"Apply player_damage_multiplier=([0-9]*\.?[0-9]+)\s+to damage value"
    )

    # Example:
    # [Ability] Apply healing_multiplier=1.08 to heal value
    _re_apply_heal = re.compile(
        r"Apply healing_multiplier=([0-9]*\.?[0-9]+)\s+to heal value"
    )

    # Arwen init:
    # [Arwen] Init points=3
    _re_arwen_init = re.compile(r"\[Arwen\]\s*Init points=([0-9]+)")

    # Arwen after attack:
    # [Arwen] After OnEnemyAttack: points=2 (mul=0.9)
    _re_arwen_after_hit = re.compile(
        r"\[Arwen\]\s*After OnEnemyAttack:\s*points=([0-9]+)\s*\(mul=([0-9]*\.?[0-9]+)\)"
    )

    _re_triggered = re.compile(r"\btriggered by\b", re.IGNORECASE)

    def __init__(
        self,
        # legacy args used by your main.py
        report_dir: Union[str, Path] = "Reports",
        report_name: Optional[str] = None,
        enable_event_log: bool = False,
        log_level: Any = None,  # legacy compatibility; not used here
        # optional controls
        event_log_sheet_name: str = "EventLog",
    ) -> None:
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.report_name = report_name
        self.enable_event_log = enable_event_log
        self.event_log_sheet_name = event_log_sheet_name

        self._summary_rows: List[Dict[str, Any]] = []
        self._config_rows: List[Dict[str, Any]] = []
        self._events: List[Dict[str, Any]] = []

        # Per-battle metrics captured from events
        self._ability_by_battle: Dict[int, AbilityBattleMetrics] = {}

    # =========================================================
    # Summary / Config
    # =========================================================

    def add_summary(
        self,
        battle_index: int,
        winner: str,
        turns: int,
        player_hp_end: float,
        enemies_alive: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        row: Dict[str, Any] = {
            "battle_index": int(battle_index),
            "winner": _sanitize_excel_text(winner),
            "turns": int(turns),
            "player_hp_end": float(player_hp_end),
            "enemies_alive": int(enemies_alive),
        }
        if extra:
            for k, v in extra.items():
                row[str(k)] = _sanitize_excel_text(v)
        self._summary_rows.append(row)

    def add_config(self, key: str, value: Any) -> None:
        self._config_rows.append(
            {"key": _sanitize_excel_text(key), "value": _sanitize_excel_text(value)}
        )

    # =========================================================
    # Event Log (raw)
    # =========================================================

    def add_event(self, payload: Dict[str, Any]) -> None:
        """
        payload recommended keys:
        - battle_index, turn, actor, event_type, message
        Any other keys will be JSON-packed into `extra` to keep columns stable.

        NOTE:
        - We always parse ability-related signals even if event log is disabled.
        """
        self._try_capture_ability_metrics(payload)

        if not self.enable_event_log:
            return

        core_keys = ["battle_index", "turn", "actor", "event_type", "message"]
        extra = dict(payload)
        for k in core_keys:
            extra.pop(k, None)

        extra_json = ""
        if extra:
            try:
                extra_json = json.dumps(extra, ensure_ascii=False)
            except Exception:
                extra_json = str(extra)

        self._events.append(
            {
                "ts": _sanitize_excel_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "battle_index": payload.get("battle_index"),
                "turn": payload.get("turn"),
                "actor": _sanitize_excel_text(payload.get("actor", "")),
                "event_type": _sanitize_excel_text(payload.get("event_type", "")),
                "message": _sanitize_excel_text(payload.get("message", "")),
                "extra": _sanitize_excel_text(extra_json),
            }
        )

    def _try_capture_ability_metrics(self, payload: Dict[str, Any]) -> None:
        bi_raw = payload.get("battle_index")
        if bi_raw is None:
            return

        try:
            battle_index = int(bi_raw)
        except Exception:
            return

        msg = payload.get("message", "")
        if msg is None:
            return
        msg = str(msg)

        met = self._ability_by_battle.get(battle_index)
        if met is None:
            met = AbilityBattleMetrics()
            self._ability_by_battle[battle_index] = met

        # Ability before
        m = self._re_before.search(msg)
        if m:
            try:
                met.damage_before_multiplier = float(m.group(1))
            except Exception:
                pass
            try:
                met.heal_before_multiplier = float(m.group(2))
            except Exception:
                pass
            return

        # Ability after
        m = self._re_after.search(msg)
        if m:
            try:
                met.damage_after_multiplier = float(m.group(1))
            except Exception:
                pass
            try:
                met.heal_after_multiplier = float(m.group(2))
            except Exception:
                pass
            return

        # Apply outgoing damage multiplier
        m = self._re_apply_damage.search(msg)
        if m:
            met.damage_mul_apply_count += 1
            if met.damage_after_multiplier is None:
                try:
                    met.damage_after_multiplier = float(m.group(1))
                except Exception:
                    pass
            return

        # Apply healing multiplier
        m = self._re_apply_heal.search(msg)
        if m:
            met.heal_mul_apply_count += 1
            if met.heal_after_multiplier is None:
                try:
                    met.heal_after_multiplier = float(m.group(1))
                except Exception:
                    pass
            return

        # Arwen init points
        m = self._re_arwen_init.search(msg)
        if m:
            try:
                met.arwen_points_init = int(m.group(1))
                met.arwen_points_last = int(m.group(1))
            except Exception:
                pass
            return

        # Arwen after hit points & mul
        m = self._re_arwen_after_hit.search(msg)
        if m:
            try:
                points_now = int(m.group(1))
                mul = float(m.group(2))
                met.last_incoming_mul = mul
                met.arwen_points_last = points_now

                # If mul < 1.0 → means mitigation applied (points consumed)
                if mul < 0.9999:
                    met.incoming_mitigation_apply_count += 1
                    met.arwen_consume_count += 1
            except Exception:
                pass
            return

        # Triggered by (generic)
        if self._re_triggered.search(msg):
            met.ability_triggered = True
            if met.ability_trigger_message is None:
                met.ability_trigger_message = msg[:200]
            return

    # =========================================================
    # Flush to Excel
    # =========================================================

    def flush_to_excel(
        self,
        extra_config: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ) -> str:
        if filename is None:
            filename = self.report_name or make_default_report_name(prefix="battle_report")

        out_path = self.report_dir / filename

        merged_config_rows: List[Dict[str, Any]] = list(self._config_rows)
        if extra_config:
            for k, v in extra_config.items():
                merged_config_rows.append(
                    {"key": _sanitize_excel_text(k), "value": _sanitize_excel_text(v)}
                )

        # -------------------------
        # Build Summary dataframe
        # -------------------------
        if not self._summary_rows:
            df_summary = pd.DataFrame(
                columns=[
                    "battle_index",
                    "winner",
                    "turns",
                    "player_hp_end",
                    "enemies_alive",
                    # ability columns (generic)
                    "ability_triggered",
                    "ability_trigger_message",
                    # outgoing dmg
                    "damage_before_multiplier",
                    "damage_after_multiplier",
                    "damage_mul_apply_count",
                    # healing
                    "heal_before_multiplier",
                    "heal_after_multiplier",
                    "heal_mul_apply_count",
                    # arwen
                    "arwen_points_init",
                    "arwen_points_last",
                    "arwen_consume_count",
                    "incoming_mitigation_apply_count",
                    "last_incoming_mul",
                ]
            )
        else:
            enriched: List[Dict[str, Any]] = []
            for r in self._summary_rows:
                bi = int(r.get("battle_index", 0))
                met = self._ability_by_battle.get(bi)

                rr = dict(r)

                # defaults
                rr.setdefault("ability_triggered", False)
                rr.setdefault("ability_trigger_message", "")

                rr.setdefault("damage_before_multiplier", "")
                rr.setdefault("damage_after_multiplier", "")
                rr.setdefault("damage_mul_apply_count", 0)

                rr.setdefault("heal_before_multiplier", "")
                rr.setdefault("heal_after_multiplier", "")
                rr.setdefault("heal_mul_apply_count", 0)

                rr.setdefault("arwen_points_init", "")
                rr.setdefault("arwen_points_last", "")
                rr.setdefault("arwen_consume_count", 0)
                rr.setdefault("incoming_mitigation_apply_count", 0)
                rr.setdefault("last_incoming_mul", "")

                if met is not None:
                    rr["ability_triggered"] = bool(met.ability_triggered)
                    rr["ability_trigger_message"] = met.ability_trigger_message or ""

                    rr["damage_before_multiplier"] = (
                        met.damage_before_multiplier
                        if met.damage_before_multiplier is not None
                        else ""
                    )
                    rr["damage_after_multiplier"] = (
                        met.damage_after_multiplier
                        if met.damage_after_multiplier is not None
                        else ""
                    )
                    rr["damage_mul_apply_count"] = int(met.damage_mul_apply_count)

                    rr["heal_before_multiplier"] = (
                        met.heal_before_multiplier
                        if met.heal_before_multiplier is not None
                        else ""
                    )
                    rr["heal_after_multiplier"] = (
                        met.heal_after_multiplier
                        if met.heal_after_multiplier is not None
                        else ""
                    )
                    rr["heal_mul_apply_count"] = int(met.heal_mul_apply_count)

                    rr["arwen_points_init"] = (
                        met.arwen_points_init if met.arwen_points_init is not None else ""
                    )
                    rr["arwen_points_last"] = (
                        met.arwen_points_last if met.arwen_points_last is not None else ""
                    )
                    rr["arwen_consume_count"] = int(met.arwen_consume_count)
                    rr["incoming_mitigation_apply_count"] = int(
                        met.incoming_mitigation_apply_count
                    )
                    rr["last_incoming_mul"] = (
                        met.last_incoming_mul if met.last_incoming_mul is not None else ""
                    )

                enriched.append(rr)

            df_summary = pd.DataFrame(enriched)

        # Config dataframe
        df_config = (
            pd.DataFrame(merged_config_rows)
            if merged_config_rows
            else pd.DataFrame(columns=["key", "value"])
        )

        # EventLog dataframe
        if self.enable_event_log:
            df_event = (
                pd.DataFrame(self._events)
                if self._events
                else pd.DataFrame(
                    columns=["ts", "battle_index", "turn", "actor", "event_type", "message", "extra"]
                )
            )
        else:
            df_event = pd.DataFrame()

        # Sanitize (pandas map)
        df_summary = df_summary.map(_sanitize_excel_text)
        df_config = df_config.map(_sanitize_excel_text)
        if self.enable_event_log and not df_event.empty:
            df_event = df_event.map(_sanitize_excel_text)

        # -------------------------
        # Write Excel
        # -------------------------
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df_summary.to_excel(writer, sheet_name="Summary", index=False)
            df_config.to_excel(writer, sheet_name="Config", index=False)
            if self.enable_event_log:
                df_event.to_excel(writer, sheet_name=self.event_log_sheet_name, index=False)

            # Basic sheet usability (freeze header row)
            try:
                wb = writer.book

                ws_sum = wb["Summary"]
                ws_sum.freeze_panes = "A2"
                ws_sum.auto_filter.ref = ws_sum.dimensions

                ws_cfg = wb["Config"]
                ws_cfg.freeze_panes = "A2"
                ws_cfg.auto_filter.ref = ws_cfg.dimensions

                if self.enable_event_log:
                    ws_ev = wb[self.event_log_sheet_name]
                    ws_ev.freeze_panes = "A2"
                    ws_ev.auto_filter.ref = ws_ev.dimensions
            except Exception:
                # Formatting is best-effort; should never break export
                pass

        return str(out_path)
