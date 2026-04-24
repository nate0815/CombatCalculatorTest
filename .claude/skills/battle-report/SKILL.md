---
name: battle-report
description: 讀取 Reports/ 目錄下最新的戰鬥報表，產生勝率、回合數、HP 等統計摘要
---

找到並分析 `Reports/` 目錄下最新的戰鬥報表 Excel，輸出易讀的統計摘要。

## 步驟

### 1. 找到報表
- 掃描 `Reports/` 目錄，找出最新的 `battle_report_*.xlsx`（依檔名時間戳排序）
- 如果目錄是空的，提示使用者先執行 `/run-sim`

### 2. 讀取 Config sheet
回報本次模擬的基本設定：
- 模擬場數（battle_count）
- Log level
- Ability 是否啟用（ability_enabled）
- 其他有記錄的設定值

### 3. 分析 Summary sheet（每場一列）
計算並輸出以下統計：

**勝負**
- 玩家勝率（winner = "Player" 的比例）
- 敵方勝率
- 平均回合數、最短 / 最長回合數

**玩家生命**
- 勝利場次的平均剩餘 HP（player_hp_end）
- 失敗場次：0（全滅）

**敵人**
- 勝利時平均殲滅敵人數
- 失敗時平均殘存敵人數（enemies_alive）

**Ability（如有記錄）**
- Ability 觸發次數分布（ability_triggered）
- 有傷害倍率加成的場次比例（damage_after_multiplier > 原始傷害）

**Arwen 專屬（如欄位存在）**
- 平均初始防護點數（arwen_points_init）
- 平均消耗次數（arwen_consume_count）

### 4. 輸出格式

```
📊 戰鬥報表摘要
報表：Reports/battle_report_YYYYMMDD_HHMMSS.xlsx
模擬場數：N 場

【設定】
  ...

【勝負】
  玩家勝率：XX%（N 勝 / N 敗）
  平均回合數：X.X（最短 X，最長 X）

【玩家生命】
  勝利場均剩餘 HP：XXX / XXXX（XX%）

【敵人】
  ...

【Ability（如有）】
  ...
```

如果 EventLog sheet 存在且有資料，補充一行「EventLog 含 N 筆事件，可進一步分析」。
