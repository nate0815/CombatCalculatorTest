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
    ability_triggered: bool = False
    ability_before_multiplier: Optional[float] = None
    ability_after_multiplier: Optional[float] = None
    ability_statuses: Optional[int] = None
    ability_damage_mul_apply_count: int = 0
    ability_trigger_message: Optional[str] = None


class BattleReporter:
    """
    Excel Report Sheets:
    - Summary: one row per battle result
    - Config: key/value pairs for this run
    - EventLog: raw events (optional, potentially huge)

    New in this version:
    - Auto-capture ability debug signals from EventLog and write into Summary
      (ability_before_multiplier / ability_after_multiplier / statuses / apply_count).
    """

    # Regex patterns for parsing log text
    _re_before = re.compile(r"Before trigger:\s*player_damage_multiplier=([0-9]*\.?[0-9]+)")
    _re_after = re.compile(r"After trigger:\s*player_damage_multiplier=([0-9]*\.?[0-9]+)\s*\(statuses=([0-9]+)\)")
    _re_apply = re.compile(r"Apply player_damage_multiplier=([0-9]*\.?[0-9]+)\s+to damage value")
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

        # NEW: per-battle ability metrics captured from events
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

        NEW:
        - Parses ability-related messages to capture metrics for Summary.
        """
        # Always parse ability metrics even if event log disabled
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
        """
        Capture key ability information from the event stream.
        This is purposely tolerant: it relies on message text patterns rather than event_type enums.
        """
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

        # Before trigger
        m = self._re_before.search(msg)
        if m:
            try:
                met.ability_before_multiplier = float(m.group(1))
            except Exception:
                pass
            return

        # After trigger
        m = self._re_after.search(msg)
        if m:
            try:
                met.ability_after_multiplier = float(m.group(1))
            except Exception:
                pass
            try:
                met.ability_statuses = int(m.group(2))
            except Exception:
                pass
            return

        # Apply multiplier to damage
        m = self._re_apply.search(msg)
        if m:
            met.ability_damage_mul_apply_count += 1
            # If after multiplier missing, try fill from this line
            if met.ability_after_multiplier is None:
                try:
                    met.ability_after_multiplier = float(m.group(1))
                except Exception:
                    pass
            return

        # Triggered by ...
        if self._re_triggered.search(msg):
            met.ability_triggered = True
            # store a short trigger message for reference
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
                    # ability columns
                    "ability_triggered",
                    "ability_before_multiplier",
                    "ability_after_multiplier",
                    "ability_statuses",
                    "ability_damage_mul_apply_count",
                    "ability_trigger_message",
                ]
            )
        else:
            # Enrich summary with ability metrics captured from event stream
            enriched: List[Dict[str, Any]] = []
            for r in self._summary_rows:
                bi = int(r.get("battle_index", 0))
                met = self._ability_by_battle.get(bi)

                rr = dict(r)
                rr.setdefault("ability_triggered", False)
                rr.setdefault("ability_before_multiplier", "")
                rr.setdefault("ability_after_multiplier", "")
                rr.setdefault("ability_statuses", "")
                rr.setdefault("ability_damage_mul_apply_count", 0)
                rr.setdefault("ability_trigger_message", "")

                if met is not None:
                    rr["ability_triggered"] = bool(met.ability_triggered)
                    rr["ability_before_multiplier"] = (
                        met.ability_before_multiplier if met.ability_before_multiplier is not None else ""
                    )
                    rr["ability_after_multiplier"] = (
                        met.ability_after_multiplier if met.ability_after_multiplier is not None else ""
                    )
                    rr["ability_statuses"] = (
                        met.ability_statuses if met.ability_statuses is not None else ""
                    )
                    rr["ability_damage_mul_apply_count"] = int(met.ability_damage_mul_apply_count)
                    rr["ability_trigger_message"] = met.ability_trigger_message or ""

                enriched.append(rr)

            df_summary = pd.DataFrame(enriched)

        # Config dataframe
        df_config = pd.DataFrame(merged_config_rows) if merged_config_rows else pd.DataFrame(columns=["key", "value"])

        # EventLog dataframe
        if self.enable_event_log:
            df_event = pd.DataFrame(self._events) if self._events else pd.DataFrame(
                columns=["ts", "battle_index", "turn", "actor", "event_type", "message", "extra"]
            )
        else:
            df_event = pd.DataFrame()

        # Sanitize (NOTE: pandas FutureWarning about applymap -> we use map)
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
