# CombatCalculatorTest

本專案為一個戰鬥模擬器，用於測試角色、卡牌、怪物以及 Ability（能力）系統在模擬戰鬥流程下的行為。目標是提供可客製化的戰鬥邏輯、事件記錄與報表輸出。

---

## 專案目標

* 建立可重複執行的戰鬥模擬流程
* 驗證卡牌、怪物、Partner Ability 等系統互動
* 提供清楚的戰鬥事件紀錄與報表輸出
* 作為後續完整戰鬥系統的驗證與原型基礎

---

## 專案結構

```
.
├── main.py                    # 入口點
├── models.py                  # 核心資料模型（Character、Card、Monster、LogLevel 等）
├── ability_models.py          # Ability 系統資料模型（AbilityDef、Condition、Effect）
├── ability_system.py          # Ability 執行引擎
├── ability_repository.py      # 從 Excel 載入 Ability 資料
├── battle_simulator.py        # 戰鬥模擬主迴圈
├── battle_reporter.py         # 戰鬥結果記錄與 Excel 報表輸出
├── card_repository.py         # 卡牌資料載入
├── card_static_calculator.py  # 卡牌靜態數值計算
├── combat_static_calculator.py# Phase 1 角色靜態數值計算
├── monster_repository.py      # 怪物資料載入
├── runtime_input_repository.py# 讀取模擬輸入參數
├── Data/                      # Excel 資料來源
└── Reports/                   # 戰鬥輸出報表（自動產生）
```

---

## 執行環境需求

* Python 3.10+
* 套件需求：

```bash
pip install pandas openpyxl
```

---

## 快速開始

```bash
python main.py
```

執行後依序進行：

1. 讀取 `Data/` 下所有 Excel 資料
2. Phase 1：計算角色靜態數值（含夥伴加成）
3. 建立 Ability System
4. 依輸入次數重複模擬戰鬥
5. 將結果輸出至 `Reports/`

---

## 資料來源（Data/）

| 檔案 | 用途 |
|------|------|
| `Character.xlsx` | 角色基礎數值（依等級，支援插值） |
| `Partner.xlsx` | 夥伴數值與 Stack Curve |
| `Card.xlsx` | 卡牌定義與效果（傷害/治癒/護盾等） |
| `Monster.xlsx` | 怪物 Index、基礎數值、技能（含 Counter 設定） |
| `CombatInputPanel.xlsx` | 模擬輸入：角色、夥伴、等級、模擬次數等 |
| `AbilityMenu.xlsx` | Ability 定義（AbilityDef、ConditionGroup/Row、EffectGroup/Row、PartnerAbility、PartnerStackCurve） |

> **Monster 技能說明**：怪物技能傷害優先使用 `MonsterSkill.Value`；若 `Value <= 0` 才 fallback 讀取 `MonsterBaseStat.Attack`。兩張表職責不同，請注意區分。

---

## 戰鬥流程總覽

```
Phase 1（靜態）
  角色基礎數值 + 夥伴加成 → CharacterSnapshot

Phase 2（動態，每場 Battle）
  BattleStart → Ability 觸發
  └─ 每回合（Turn）：
       玩家階段：出牌 → Ability 觸發 → Counter Tick → 效果結算
       勝利判定
       敵方階段：Ready 技能執行 → Counter Reload
       敗北判定
```

---

## Log Level 系統

`main.py` 執行時可選擇 log level，影響 EventLog 的輸出量：

| Level | 輸出內容 |
|-------|---------|
| `INFO` | 關鍵事件：玩家傷害/治癒、敵人攻擊、技能觸發、EnemyCounter Ready |
| `DEBUG` | INFO + Console 即時列印 |
| `TRACE` | DEBUG + EnemyCounter 每次 Tick 細節 |

> 大量模擬（1000+ 場）建議使用 `INFO`，EventLog 僅在需要逐回合追蹤時開啟。

**注意**：`ApplyDamageMul` / `ApplyHealMul` 事件只在倍率 ≠ 1.0 時才記錄，避免 Ability 未啟用時產生無意義 log。

---

## 報表輸出（Reports/）

每次執行產生一份 `battle_report_YYYYMMDD_HHMMSS.xlsx`，包含三個工作表：

### Summary
每場戰鬥一列，欄位包含：
- 基本結果：`battle_index`、`winner`、`turns`、`player_hp_end`、`enemies_alive`
- Ability 觸發摘要：`ability_triggered`、`damage_after_multiplier` 等
- Arwen 專屬：`arwen_points_init`、`arwen_consume_count` 等

### Config
本次模擬的輸入參數（battle_count、log_level、ability_enabled 等）與統計結果。

### EventLog（選用）
逐事件記錄，欄位為 `battle_index / turn / actor / event_type / message / extra`。  
`extra` 欄為結構化數值（JSON），不需 regex 解析，直接讀取 key 即可。

---

## Ability 系統

### 資料結構（ability_models.py）

```
AbilityDef
  ├── trigger_event    # 觸發時機（見下方清單）
  ├── source_type      # 來源類型（Partner / Character / Equipment / Card / Monster）
  ├── apply_phase      # PRE_BATTLE 或 RUNTIME
  ├── priority         # 執行順序（數字大的先執行）
  ├── condition_group  # 條件群組（AND/OR 邏輯）
  └── effect_group     # 效果群組（依序執行）
```

### TriggerEvent 清單

| 事件 | 時機 |
|------|------|
| `BattleStart` | 戰鬥開始 |
| `FirstTurnStart` | 第一回合開始 |
| `TurnStart` | 每回合開始 |
| `OnPlayCard` | 玩家出牌時 |
| `TurnEnd` | 每回合結束 |
| `OnEnemyAttack` | 敵人攻擊時 |

### 目前支援的 ConditionType

| 類型 | 說明 |
|------|------|
| `OwnerClassEqualsPartnerClass` | 角色職業 == 夥伴職業 |

### 目前支援的 EffectType

| 類型 | 說明 |
|------|------|
| `AddStatus` | 新增狀態（含持續回合數） |
| `SetStatusParam` | 設定狀態參數（如 AttackUp 的加成數值） |
| `SetExtraValue` | 寫入 extra_ctx 的持久化數值 |
| `AddExtraValue` | 累加 extra_ctx 的持久化數值 |
| `SetRuntimeMod` | 寫入 runtime_mod（影響當次觸發的傷害/治癒倍率） |
| `ConsumeExtraPointAndSetIncomingDamageMul` | 消耗點數並設定承傷倍率（Arwen 專用） |

### 數值來源（Value Resolution）

Effect 的數值可以來自：
- **常數**（`ValueRefType.None_`）：直接使用 `value2` 欄位
- **PartnerStackCurve**（`ValueRefType.PartnerStack`）：依 `partner_stack_count` 從曲線表查值

---

## Ability 執行引擎（ability_system.py）

```python
AbilitySystem.trigger(
    trigger_event,    # TriggerEvent enum
    extra_ctx,        # Dict，持久化戰鬥狀態（跨回合）
    runtime_mod,      # Dict，當次觸發的倍率（每次觸發重置）
)
```

執行流程：
1. 從 `partner_abilities[partner_id]` 找出符合 `trigger_event` 的 Ability
2. 依 priority 降序排列
3. 評估 Condition Group（AND/OR）
4. 執行 Effect Group，修改 `extra_ctx` 或 `runtime_mod`

> **目前限制**：只有 `source_type = Partner` 的 Ability 有完整執行路徑。Character / Equipment / Card / Monster 的 source type 已定義但尚未實作。

---

## 範例：現有 Partner Ability

### Douglas
- **Trigger**：`FirstTurnStart`
- **Condition**：角色職業 == Douglas 職業
- **Effect**：施加 `AttackUp` 狀態（持續 1 回合），加成值依 PartnerStackCurve 計算

### Arwen
- **Trigger**：`BattleStart` / `OnEnemyAttack`
- **Effect**：
  - 開戰時依敵人數量初始化防護點數（最多 3 點）
  - 每次受到攻擊消耗 1 點，承傷倍率降為 0.9

---

## 擴充指南

### 新增一個 Partner Ability（純資料，不改程式）

1. 在 `AbilityMenu.xlsx` 的 `AbilityDef` 表新增一列（填寫 trigger_event、source_type=Partner、priority 等）
2. 在 `ConditionGroup` / `ConditionRow` 表定義條件（若不需要條件則略過）
3. 在 `EffectGroup` / `EffectRow` 表定義效果
4. 在 `PartnerAbility` 表綁定 `partner_id → ability_id`
5. （若 Effect 需要數值曲線）在 `PartnerStackCurve` 表新增對應資料

### 新增 ConditionType

1. 在 `ability_models.py` 的 `ConditionType` enum 新增項目
2. 在 `ability_system.py` 的 `_eval_condition_row()` 新增對應判斷邏輯
3. 在 Excel `ConditionRow` 表使用新的 condition_type 字串

### 新增 EffectType

1. 在 `ability_models.py` 的 `AbilityEffectType` enum 新增項目
2. 在 `ability_system.py` 的 `_exec_effect_row()` 新增對應執行邏輯
3. 在 Excel `EffectRow` 表使用新的 effect_type 字串

### 擴充至 Character Ability（需改程式）

目前 Ability 執行路徑只支援 Partner。要擴充至 Character Ability 需要：

1. **資料層**（`ability_repository.py`）：新增 `CharacterAbility` sheet 載入，建立 `character_abilities: Dict[str, List[str]]`
2. **執行層**（`ability_system.py`）：`_iter_active_abilities()` 加入 `character_abilities` 查找分支
3. **Context**（`battle_simulator.py`）：`_trigger_ability()` 呼叫時在 ctx 補上 `character_id`

---

## 常見問題

### 怪物改了攻擊力但沒有效果？

確認修改的是 `MonsterSkill.Value` 欄位，而非 `MonsterBaseStat.Attack`。  
程式優先使用 `MonsterSkill.Value`；只有 `Value <= 0` 時才讀取 `MonsterBaseStat.Attack`。

### 如何確認 Ability 有正確觸發？

開啟 EventLog（log_level 設為 DEBUG 以上），查看 `actor=Ability, event_type=AfterTrigger` 的列，  
`extra` 欄的 JSON 包含觸發後的 `player_damage_multiplier` 與 `healing_multiplier`。

### 如何新增 TriggerEvent？

1. 在 `ability_models.py` 的 `TriggerEvent` enum 新增項目
2. 在 `battle_simulator.py` 對應時機呼叫 `_trigger_ability(..., trigger=TriggerEvent.新項目, ...)`

---

## 備註

本專案目前為實驗與原型用途，架構設計以可讀性與擴充性為優先。後續可逐步演進為完整戰鬥核心系統。
