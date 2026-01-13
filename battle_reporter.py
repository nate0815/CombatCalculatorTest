# battle_reporter.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from models import LogLevel


@dataclass
class BattleSummaryRow:
    battle_index: int
    winner: str
    turns: int
    player_hp_end: float
    enemies_alive: int


class BattleReporter:
    """
    Writes battle outputs to an Excel report.

    Goal for current phase:
    - Keep full console logs in BattleSimulator (host machine).
    - Excel report only needs Summary/Config for now (NO EventLog).
    """

    def __init__(
        self,
        report_dir: Optional[Path] = None,
        report_name: Optional[str] = None,
        enable_event_log: bool = False,
        log_level: LogLevel = LogLevel.INFO,  # kept for backward compatibility with main.py
    ) -> None:
        self.report_dir = report_dir
        self.report_name = report_name
        self.enable_event_log = enable_event_log
        self.log_level = log_level  # not used, but kept so old code won't crash

        self._summary_rows: List[BattleSummaryRow] = []
        self._events: List[Dict[str, Any]] = []

    def add_summary(self, battle_index: int, winner: str, turns: int, player_hp_end: float, enemies_alive: int) -> None:
        self._summary_rows.append(
            BattleSummaryRow(
                battle_index=battle_index,
                winner=winner,
                turns=turns,
                player_hp_end=float(player_hp_end),
                enemies_alive=int(enemies_alive),
            )
        )

    def add_event(self, payload: Dict[str, Any]) -> None:
        # EventLog disabled by default for this phase
        if not self.enable_event_log:
            return
        self._events.append(dict(payload))

    def flush_to_excel(
        self,
        report_dir: Optional[Path] = None,
        report_name: Optional[str] = None,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Path]:
        """
        Write report if report_dir & report_name available.
        Returns output path, or None if not configured.
        """
        out_dir = report_dir or self.report_dir
        out_name = report_name or self.report_name
        if out_dir is None or out_name is None:
            return None

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / out_name

        df_summary = pd.DataFrame([asdict(r) for r in self._summary_rows])
        df_config = pd.DataFrame([extra_config or {}])

        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df_summary.to_excel(writer, index=False, sheet_name="Summary")
            df_config.to_excel(writer, index=False, sheet_name="Config")

            # EventLog sheet only if enabled
            if self.enable_event_log:
                df_events = pd.DataFrame(self._events)
                df_events.to_excel(writer, index=False, sheet_name="EventLog")

        return out_path


def make_default_report_name(prefix: str = "BattleReport") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.xlsx"
