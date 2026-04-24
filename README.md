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

### Counter 機制逐步說明

每個怪物技能有獨立的 Counter 計數器，從 `CounterMax` 倒數至 0：

```
【初始化】
  counter_now = CounterMax（如 3）
  ready = False

【玩家每次出牌時】
  foreach 技能（CounterMode=Enabled, CounterStartTrigger=OnPlayerPlayCard）:
    counter_now -= 1
    if counter_now <= 0: ready = True   ← 標記就緒，本回合不執行

【玩家回合結束，進入敵方回合】
  foreach 怪物的 ready 技能:
    if EnemyPhaseActionRule=ActIfNotActedThisTurn AND 已行動過: 跳過
    執行技能（Attack / AddShield）
    enemy.acted_this_turn = True
    if ReloadTiming=AfterEnemyAttackPhase:
      ready = False
      counter_now = CounterMax   ← 重置，下一輪重新計數
```

**範例（CounterMax=3 的攻擊技能）：**

| 回合 | 玩家出牌數 | counter_now | ready | 敵方行動 |
|------|-----------|-------------|-------|---------|
| T1 | 3 張 | 3→2→1→0 | ✅ | 攻擊玩家，重置為 3 |
| T2 | 1 張 | 3→2 | ❌ | 不行動 |
| T3 | 2 張 | 2→1→0 | ✅ | 攻擊玩家，重置為 3 |

> **注意**：Counter 歸零後技能在**敵方回合**才執行，不會在玩家出牌當下觸發。

---

## 卡牌選取機制

> ⚠️ **目前為簡化版本：無牌組 / 手牌系統。**

每回合，程式從全隊所有卡牌中以**隨機等機率**抽取一張出牌：

```python
card = random.choice(party_cards)  # party_cards = 全隊卡牌列表
```

以下系統**尚未實作**：

| 功能 | 狀態 |
|------|------|
| 牌組（Deck）管理 | ❌ 未實作 |
| 手牌（Hand）管理 | ❌ 未實作 |
| AP 費用限制 | ❌ `ApCost` 欄位已讀取但不影響選牌 |
| 卡牌覺醒效果差異 | ❌ `EpiphanyTier` 已讀取但不影響選牌 |
| 指定牌組（CombatInputPanel.CardList[]） | ❌ 欄位預留但未接入 |

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

| 類型 | 說明 | 狀態 |
|------|------|------|
| `OwnerClassEqualsPartnerClass` | 角色職業 == 夥伴職業 | ✅ 已實作 |

> 新增 ConditionType 的方式見下方「擴充指南」。

### 目前支援的 EffectType

| 類型 | 說明 | 狀態 |
|------|------|------|
| `AddStatus` | 新增狀態（含持續回合數） | ✅ 已實作 |
| `SetStatusParam` | 設定狀態參數（如 AttackUp 的加成數值） | ✅ 已實作 |
| `SetExtraValue` | 寫入 extra_ctx 的持久化數值 | ✅ 已實作 |
| `AddExtraValue` | 累加 extra_ctx 的持久化數值 | ✅ 已實作 |
| `SetRuntimeMod` | 寫入 runtime_mod（影響當次觸發的傷害/治癒倍率） | ✅ 已實作 |
| `ConsumeExtraPointAndSetIncomingDamageMul` | 消耗點數並設定承傷倍率（Arwen 專用） | ✅ 已實作 |

### 目前支援的 StatusType

| 狀態 | 說明 | 狀態 |
|------|------|------|
| `AttackUp` | 增加本回合輸出傷害倍率（透過 `player_damage_multiplier`） | ✅ 已實作 |
| DefenseUp / 其他 | — | ❌ 尚未定義，新增須同時擴充 `StatusType` enum 與 `get_damage_multiplier()` 邏輯 |

### apply_phase 說明

| 值 | 說明 | 狀態 |
|---|------|------|
| `RUNTIME` | 戰鬥中由 TriggerEvent 觸發（目前唯一運作路徑） | ✅ 已實作 |
| `PRE_BATTLE` | 戰鬥初始化時套用一次 | ❌ 已定義於資料模型，**但 AbilitySystem 執行時未檢查此欄位** |

### 數值來源（Value Resolution）

Effect 的數值可以來自：
- **常數**（`ValueRefType.None_`）：直接使用 `value2` 欄位
- **PartnerStackCurve**（`ValueRefType.PartnerStack`）：依 `partner_stack_count` 從曲線表查值

---

## Ability 執行引擎（ability_system.py）

```python
AbilitySystem.on_trigger(
    trigger_event,    # TriggerEvent enum
    ctx={             # 每次觸發的 runtime context
        "partner_id": ...,
        "partner_stack_count": ...,
        "owner_class": ...,
        "partner_class": ...,
        "runtime_mod": {},    # 傷害/治癒倍率，每次觸發後重置
    },
    ability_context={ # 整場戰鬥持久的 context
        "extra_ctx": {},              # 跨回合持久狀態
        "statuses": [],               # 狀態清單
        "partner_abilities": {},      # partner_id → [ability_id]
        "partner_stack_curves": {},   # partner_id → StatTypeId → [float]
    },
)
```

執行流程：
1. 從 `partner_abilities[partner_id]` 找出符合 `trigger_event` 的 Ability
2. 依 priority 降序排列
3. 評估 Condition Group（AND/OR）
4. 執行 Effect Group，修改 `extra_ctx` 或 `runtime_mod`

> ⚠️ **目前限制**：只有 `source_type = Partner` 的 Ability 有完整執行路徑。Character / Equipment / Card / Monster 的 source_type 已定義於 `ability_models.py`，但 AbilitySystem 執行時完全忽略，不會觸發。

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

## 實作狀態總覽

> 下表記錄各功能的完成狀態，供開發者快速掌握哪些已可用、哪些仍需補完。

### 核心戰鬥系統

| 功能 | 狀態 | 說明 |
|------|------|------|
| Phase 1 靜態數值計算 | ✅ 完整 | 角色等級插值、夥伴基礎加成 |
| Phase 2 戰鬥迴圈 | ✅ 完整 | 回合制，含玩家/敵方階段 |
| 卡牌出牌（隨機選取） | ✅ 運作中 | 僅 `random.choice`，無牌組/手牌管理 |
| 怪物 Counter 機制 | ✅ 完整 | 倒數計時、就緒、執行、重置 |
| 怪物技能：Attack | ✅ 完整 | — |
| 怪物技能：AddShield | ✅ 完整 | — |
| 怪物技能：Buff / Debuff | ❌ 未實作 | `MonsterSkillType` 已定義，無執行邏輯 |
| 玩家卡牌：Damage | ✅ 完整 | — |
| 玩家卡牌：Heal | ✅ 完整 | — |
| 玩家卡牌：Shield | ⚠️ 部分 | 數值計算存在，護盾吸收傷害邏輯未驗證 |
| 玩家卡牌：Buff / Debuff | ❌ 未實作 | `EffectType` 已定義，無執行邏輯 |
| AP 費用系統 | ❌ 未實作 | `ApCost` 欄位已讀取但不影響出牌 |
| 牌組 / 手牌管理 | ❌ 未實作 | 目前為全隊卡牌隨機選取 |

### Ability 系統

| 功能 | 狀態 | 說明 |
|------|------|------|
| Partner Ability（全流程） | ✅ 完整 | 資料驅動，無需改程式即可新增 |
| Character Ability | ❌ 未實作 | `SourceType.Character` 已定義，執行時被忽略 |
| Equipment Ability | ❌ 未實作 | `SourceType.Equipment` 已定義，執行時被忽略 |
| Card Ability | ❌ 未實作 | `SourceType.Card` 已定義，執行時被忽略 |
| Monster Ability | ❌ 未實作 | `SourceType.Monster` 已定義，執行時被忽略 |
| apply_phase: RUNTIME | ✅ 完整 | 所有 Partner Ability 的觸發路徑 |
| apply_phase: PRE_BATTLE | ❌ 未實作 | 已定義於資料模型，AbilitySystem 不檢查此欄位 |
| TriggerEvent: BattleStart | ✅ 完整 | — |
| TriggerEvent: FirstTurnStart | ✅ 完整 | — |
| TriggerEvent: TurnStart / TurnEnd | ✅ 完整 | — |
| TriggerEvent: OnPlayCard | ✅ 完整 | — |
| TriggerEvent: OnEnemyAttack | ✅ 完整 | — |
| ConditionType: OwnerClassEqualsPartnerClass | ✅ 完整 | — |
| 其他 ConditionType | ❌ 未實作 | 新增需修改程式 |
| StatusType: AttackUp | ✅ 完整 | 影響 `player_damage_multiplier` |
| StatusType: DefenseUp / 其他 | ❌ 未實作 | 尚未定義，需同時擴充 enum 與計算邏輯 |

### 輸入資料

| 欄位 / 功能 | 狀態 | 說明 |
|------------|------|------|
| CharacterId / Level | ✅ 使用中 | — |
| PartnerId / PartnerLevel / PartnerStackCount | ✅ 使用中 | — |
| IsPartnerBonusApplied | ⚠️ 部分 | 讀取後傳入 context，但 Phase 1 計算**固定套用**夥伴加成，此旗標未實際控制計算行為 |
| AffectionLevel | ❌ 未使用 | 欄位讀取並儲存，但不影響任何計算（`Affection.xlsx` 也尚未接入） |
| FragmentIdList / EquipmentIdList / CardList 等 | ❌ 未啟用 | 欄位預留，不影響模擬 |
| MonsterRank | ❌ 未使用 | 欄位讀取並儲存，不影響怪物選取或戰鬥邏輯 |

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

## Claude Code Skills

本專案提供 `/run-sim`、`/check-data`、`/add-ability`、`/battle-report` 四個 slash command，詳見 [SKILLS.md](SKILLS.md)。

---

## 備註

本專案目前為實驗與原型用途，架構設計以可讀性與擴充性為優先。後續可逐步演進為完整戰鬥核心系統。
