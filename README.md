# CombatCalculatorTest

本專案為一個戰鬥模擬器，用於測試角色、卡牌、怪物以及 Ability（能力）系統在模擬戰鬥流程下的行為。目標是提供可客製化的戰鬥邏輯、事件記錄與報表輸出。

---

## 專案目標

* 建立可重複執行的戰鬥模擬流程
* 驗證卡牌、怪物、Partner Ability 等系統互動
* 提供清楚的戰鬥事件紀錄與報表輸出
* 作為後續完整戰鬥系統的驗證與原型基礎

---

## 專案結構（概要）

```
.
├── ability_models.py
├── ability_system.py
├── battle_simulator.py
├── battle_reporter.py
├── card_repository.py
├── card_static_calculator.py
├── combat_static_calculator.py
├── main.py
├── models.py
├── monster_repository.py
├── runtime_input_repository.py
├── Data/            # Excel 資料來源
├── Reports/         # 戰鬥輸出報表
└── README.md
```

---

## 執行環境需求

* Python 3.10+
* 套件需求：

```bash
pip install pandas openpyxl
```

---

## 資料來源（Data Folder）

請確保 `Data/` 目錄下包含以下 Excel 檔案：

* `Card.xlsx`：卡牌資料與效果
* `Character.xlsx`：角色基礎數值
* `Monster.xlsx`：怪物資料
* `Partner.xlsx`：Partner 與 Ability 資料（若有）
* `CombatInputPanel.xlsx`：模擬輸入參數

---

## 快速開始

在專案根目錄執行：

```bash
python main.py
```

執行後將：

1. 載入靜態角色與卡牌資料
2. 建立 Ability System
3. 依輸入設定重複模擬戰鬥
4. 將結果輸出至 `Reports/`

---

## 戰鬥模擬流程總覽

戰鬥模擬大致流程如下：

1. Phase 1：角色靜態計算（Character Snapshot）
2. Phase 2：戰鬥模擬（Turn-based）
3. Ability 於指定 Trigger Event 觸發
4. Card / Monster 行為執行
5. 勝敗判定與結果輸出

---

## Ability 系統說明

### Ability 定義（ability_models.py）

Ability 系統由「觸發時機、條件、效果」三層結構組成。

#### 核心結構

* `AbilityDef`

  * ability_id
  * trigger_event
  * priority
  * condition_groups
  * effect_groups

* `TriggerEvent`

  * BattleStart
  * FirstTurnStart
  * TurnStart
  * TurnEnd

---

### Condition 系統

* `ConditionGroupDef`

  * group_logic：AND / OR
  * rows：ConditionRowDef[]

* `ConditionRowDef`

  * condition_type
  * params

目前範例支援的 Condition 包含：

* `OwnerClassEqualsPartnerClass`

Condition 會在 Ability 觸發時被評估，若成立才會進入 Effect 階段。

---

### Effect 系統

* `EffectGroupDef`

  * rows：EffectRowDef[]

* `EffectRowDef`

  * effect_type
  * params

Effect 用於實際修改戰鬥狀態，例如：

* 新增 Status
* 設定狀態參數
* 寫入 runtime_mod（供戰鬥計算使用）

---

## Ability 執行引擎（ability_system.py）

`AbilitySystem` 負責在戰鬥流程中執行 Ability：

```text
AbilitySystem.on_trigger(
    trigger_event,
    battle_index,
    turn,
    ctx,
    emit
)
```

執行流程：

1. 找出符合 TriggerEvent 的 Ability
2. 依 priority 排序
3. 評估 Condition Groups
4. 執行 Effect Groups
5. 將結果寫入 ctx.runtime_mod

---

## 戰鬥模擬器（battle_simulator.py）

負責整體戰鬥流程：

* 玩家階段

  * 抽牌
  * 出牌
  * 卡牌效果結算

* 怪物階段

  * Counter 判斷
  * 行為執行

* Turn 與 Battle 結束判定

Ability Trigger（如 FirstTurnStart）會在對應時機呼叫 AbilitySystem。

---

## Battle Reporter（battle_reporter.py）

負責紀錄與輸出戰鬥結果：

* 戰鬥摘要
* 回合事件
* 能力觸發紀錄

輸出位置：

```
Reports/
```

---

## Repository 類模組

### Card Repository

* `card_repository.py`
* `card_static_calculator.py`

用途：

* 讀取卡牌資料
* 建立卡牌靜態數值
* 提供戰鬥中使用的卡牌物件

---

### Monster Repository

* `monster_repository.py`

用途：

* 載入怪物資料
* 提供怪物行為與數值

---

## Runtime Input

`runtime_input_repository.py` 負責讀取模擬時的輸入參數，例如：

* 模擬次數
* 指定角色 / Partner
* 測試用開關

---

## MVP Ability 範例（Douglas）

目前內建一個最小可行 Ability 範例：

* Partner：Douglas
* Trigger：FirstTurnStart
* Condition：OwnerClass == PartnerClass
* Effect：

  * 新增 AttackUp 狀態
  * 持續 1 回合
  * 加成數值依 Partner Stack Curve 計算

此範例主要用於驗證 Ability 系統的完整流程。

---

## 擴充方向建議

* Ability / Condition / Effect 改由 Excel 驅動
* 新增更多 TriggerEvent
* Ability 與卡牌、怪物深度互動
* 擴充 Status 與數值疊加規則

---

## 常見問題

### 如何新增 Ability 觸發時機？

1. 在 `TriggerEvent` Enum 新增項目
2. 在戰鬥流程對應時機呼叫 `AbilitySystem.on_trigger`

---

### Ability 如何影響傷害計算？

Ability Effect 可寫入 `ctx.runtime_mod`，戰鬥傷害計算階段會讀取該資料並套用加成。

---

## 備註

本專案目前為實驗與原型用途，架構設計以可讀性與擴充性為優先。

後續可逐步演進為完整戰鬥核心系統。
