# main.py
from __future__ import annotations

import argparse
import logging
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional


# -----------------------------
# Logging
# -----------------------------
def setup_logging(mode: str) -> logging.Logger:
    """
    mode:
      - "standalone": console log 精簡（INFO）
      - "detailed"  : console log 詳細（DEBUG）
    """
    logger = logging.getLogger("combat")
    logger.setLevel(logging.DEBUG)  # root level keep DEBUG; handlers decide output

    # Avoid duplicate handlers in repeated runs (e.g., VSCode run)
    if logger.handlers:
        return logger

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if mode == "detailed" else logging.INFO)
    fmt = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


# -----------------------------
# Safe helpers
# -----------------------------
def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {"value": obj}


def _call_first_available(obj: Any, method_names: list[str], *args, **kwargs) -> Any:
    """
    在 obj 上依序嘗試呼叫 method_names 中的第一個存在的方法。
    """
    for name in method_names:
        fn = getattr(obj, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    raise AttributeError(f"{type(obj).__name__} has none of methods: {method_names}")


# -----------------------------
# Main flow
# -----------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Combat Simulator Entry")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="Data",
        help="資料表資料夾（預設 Data）",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Output",
        help="輸出資料夾（預設 Output）",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["standalone", "detailed"],
        default="standalone",
        help="輸出模式：standalone(精簡) / detailed(詳細)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="模擬次數（預設 1；若你的 battle_simulator 支援 Monte Carlo 可加大）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="隨機種子（預設 0；若你的 simulator 有用到）",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(args.mode)
    logger.info(f"Data Dir   : {data_dir.resolve()}")
    logger.info(f"Output Dir : {output_dir.resolve()}")
    logger.info(f"Mode       : {args.mode}")
    logger.info(f"Runs       : {args.runs}")

    # -----------------------------
    # Import project modules
    # -----------------------------
    try:
        # 你之前新增/使用過的模組名稱（依你 repo 的趨勢）
        from runtime_input_repository import RuntimeInputRepository  # type: ignore
    except Exception as e:
        logger.error("❌ 無法 import RuntimeInputRepository（runtime_input_repository.py）")
        logger.error(str(e))
        return 2

    try:
        from battle_simulator import BattleSimulator  # type: ignore
    except Exception as e:
        logger.error("❌ 無法 import BattleSimulator（battle_simulator.py）")
        logger.error(str(e))
        return 2

    # Reporter 不是必須，但有就用
    BattleReporter = None
    try:
        from battle_reporter import BattleReporter as _BattleReporter  # type: ignore

        BattleReporter = _BattleReporter
    except Exception:
        BattleReporter = None

    # -----------------------------
    # Load runtime inputs
    # -----------------------------
    try:
        runtime_repo = RuntimeInputRepository(base_dir=data_dir)  # 常見寫法
    except TypeError:
        # fallback: 有些人會用 data_dir 參數名
        runtime_repo = RuntimeInputRepository(data_dir=data_dir)

    # 取得輸入設定（你可能叫 CombatInputPanel / RuntimeInput / BattleInput 之類）
    # 這裡用 fallback，盡量貼近你之前的命名習慣
    try:
        runtime_inputs = _call_first_available(
            runtime_repo,
            ["load_all", "get_all", "load", "read_all"],
        )
    except Exception as e:
        logger.error("❌ 讀取 Runtime Input 失敗：請確認 runtime_input_repository.py 的方法命名")
        logger.error(str(e))
        return 3

    # runtime_inputs 可能是一筆 dict、或 list of dataclass/dict
    if isinstance(runtime_inputs, dict):
        runtime_inputs_list = [runtime_inputs]
    elif isinstance(runtime_inputs, list):
        runtime_inputs_list = runtime_inputs
    else:
        # 其他型別先包起來
        runtime_inputs_list = [runtime_inputs]

    logger.info(f"Loaded runtime inputs: {len(runtime_inputs_list)}")

    # -----------------------------
    # Run simulations
    # -----------------------------
    try:
        simulator = BattleSimulator(base_dir=data_dir, logger=logger)  # 常見寫法
    except TypeError:
        # fallback: 可能叫 data_dir 或 repo 注入
        try:
            simulator = BattleSimulator(data_dir=data_dir, logger=logger)
        except TypeError:
            simulator = BattleSimulator(data_dir=data_dir)

    all_results = []
    for idx, battle_input in enumerate(runtime_inputs_list, start=1):
        bi = battle_input
        bi_dict = _to_dict(bi)
        logger.info(f"--- Battle Case {idx}/{len(runtime_inputs_list)} ---")
        if args.mode == "detailed":
            logger.debug(f"Input: {bi_dict}")

        # 你剛剛的結論：IsPartnerBonusApplied 已移除
        # => 這裡不依賴任何 input flag，直接讓 simulator / ability system 用 code 判斷職業相同與否
        # （因此這邊也不做任何額外欄位加工）

        # 讓 simulator 自己跑：可能方法叫 simulate / run / run_once / simulate_many
        try:
            result = _call_first_available(
                simulator,
                ["simulate_many", "simulate", "run", "run_many", "run_once"],
                bi,
                args.runs,
                args.seed,
            )
        except TypeError:
            # 有些 simulate_many 只吃 (input, runs) 或 (input)；做幾個 fallback
            try:
                result = _call_first_available(
                    simulator,
                    ["simulate_many", "run_many"],
                    bi,
                    args.runs,
                )
            except Exception:
                result = _call_first_available(
                    simulator,
                    ["simulate", "run", "run_once"],
                    bi,
                )
        except Exception as e:
            logger.error(f"❌ Battle Case {idx} 模擬失敗")
            logger.error(str(e))
            return 4

        all_results.append(result)

        if args.mode == "detailed":
            logger.debug(f"Result({idx}): {_to_dict(result)}")

    # -----------------------------
    # Output report (optional)
    # -----------------------------
    if BattleReporter is not None:
        try:
            reporter = BattleReporter(output_dir=output_dir, logger=logger)  # 常見寫法
        except TypeError:
            reporter = BattleReporter(output_dir=output_dir)

        # 寫檔方法：export / write / save / build
        try:
            _call_first_available(
                reporter,
                ["export", "write", "save", "build_report"],
                all_results,
            )
            logger.info("✅ Report exported.")
        except Exception as e:
            logger.error("⚠️ Reporter 存檔失敗（但模擬已完成）")
            logger.error(str(e))
    else:
        logger.info("Reporter not found. Skip exporting report.")

    logger.info("✅ Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
