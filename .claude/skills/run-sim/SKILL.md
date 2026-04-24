---
name: run-sim
description: 執行戰鬥模擬（python main.py），回報執行結果、錯誤訊息與輸出報表路徑
---

執行 `python main.py`，並整理輸出結果。

步驟：
1. 在專案根目錄執行 `python main.py`，擷取 stdout 與 stderr
2. 判斷執行是否成功（exit code 0 = 成功）
3. 如果失敗，顯示完整錯誤訊息並指出可能原因（資料檔缺失、欄位錯誤等）
4. 如果成功：
   - 回報模擬了幾場戰鬥
   - 列出新產生的報表路徑（`Reports/battle_report_*.xlsx`）
   - 摘要 console 輸出中的關鍵數字（如 turns、winner 分布）
5. 如果 Reports/ 有新檔案，提示使用者可以執行 `/battle-report` 查看詳細統計
