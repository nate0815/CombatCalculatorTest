# battle_reporter.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json

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


class BattleReporter:
    """
    Excel Report Sheets:
    - Summary: one row per battle result
    - Config: key/value pairs for this run
    - EventLog: raw events (optional, potentially huge)
    """

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
        """
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

        # NOTE:
        # pandas FutureWarning: DataFrame.applymap is deprecated -> use DataFrame.map instead.
        # We still keep _sanitize_excel_text for safety.
        df_summary = pd.DataFrame(self._summary_rows).map(_sanitize_excel_text)
        df_config = pd.DataFrame(merged_config_rows).map(_sanitize_excel_text)

        if self.enable_event_log:
            df_event = pd.DataFrame(self._events).map(_sanitize_excel_text)
        else:
            df_event = pd.DataFrame()

        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            # Summary
            if df_summary.empty:
                pd.DataFrame(
                    columns=["battle_index", "winner", "turns", "player_hp_end", "enemies_alive"]
                ).to_excel(writer, sheet_name="Summary", index=False)
            else:
                df_summary.to_excel(writer, sheet_name="Summary", index=False)

            # Config
            if df_config.empty:
                pd.DataFrame(columns=["key", "value"]).to_excel(writer, sheet_name="Config", index=False)
            else:
                df_config.to_excel(writer, sheet_name="Config", index=False)

            # EventLog
            if self.enable_event_log:
                if df_event.empty:
                    pd.DataFrame(
                        columns=["ts", "battle_index", "turn", "actor", "event_type", "message", "extra"]
                    ).to_excel(writer, sheet_name=self.event_log_sheet_name, index=False)
                else:
                    df_event.to_excel(writer, sheet_name=self.event_log_sheet_name, index=False)

        return str(out_path)
