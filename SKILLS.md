# Claude Code Skills 使用說明

本專案提供五個 Claude Code slash command，加速常見的開發與測試工作流程。

> **前置條件**：需在 Claude Code 環境下使用（CLI、IDE 擴充套件或 claude.ai/code）。

---

## 目錄

1. [/run-sim](#run-sim)
2. [/check-data](#check-data)
3. [/add-ability](#add-ability)
4. [/battle-report](#battle-report)
5. [/extend-ability](#extend-ability)

---

## /run-sim

**用途**：執行一次完整的戰鬥模擬，回報執行結果與產出報表路徑。

**使用時機**：
- 修改資料後想快速確認模擬能否正常跑完
- 想知道這次模擬產生了哪份報表

**執行內容**：
1. 在專案根目錄執行 `python main.py`
2. 判斷執行成功或失敗
3. 失敗時：顯示完整錯誤訊息並指出可能原因
4. 成功時：回報模擬場數、新產生的報表路徑、console 輸出摘要
5. 提示可接著執行 `/battle-report` 查看統計

**範例輸出**：
```
✅ 模擬成功
模擬場數：100 場
報表：Reports/battle_report_20260424_153012.xlsx

建議執行 /battle-report 查看詳細統計。
```

---

## /check-data

**用途**：驗證 `Data/` 目錄下所有 Excel 檔案的結構與內容是否符合 DATA_SPEC.md 規範。

**使用時機**：
- 新增或修改 Excel 資料後，執行模擬前先確認格式正確
- 懷疑資料有誤（模擬結果怪異、程式報錯）時快速定位問題

**檢查項目**：
| 項目 | 說明 |
|------|------|
| 檔案存在性 | 必要的 Excel 檔案是否都在 `Data/` 下 |
| 工作表存在性 | 每個檔案的必要 sheet 是否都存在 |
| 必填欄位 | 各 sheet 的必填欄位是否都有 |
| 跨表 ID 一致性 | CharacterId / PartnerId / MonsterId 等跨表引用是否對得上 |
| 數值合理性 | PartnerStackCount 0～4、MonsterWeight ≥ 1 等範圍檢查 |

**輸出格式**：
```
✅ 通過：Character.xlsx 結構正確
✅ 通過：跨表 CharacterId 一致
⚠️ 警告：MonsterRank 為空（不影響執行）
❌ 錯誤：CombatInputPanel.PartnerId "Partner99" 在 Partner.xlsx 中找不到

共 1 個錯誤，請修正後再執行 /run-sim。
```

---

## /add-ability

**用途**：逐步引導填寫新 Partner Ability 所需的所有 Excel 欄位，最後輸出完整填表清單。

**使用時機**：
- 要為某個夥伴新增技能，但不確定需要填哪些 sheet、哪些欄位
- 想確保填表不會漏掉任何必要資料

**互動流程**：
1. 確認夥伴 ID（PartnerId）
2. 選擇觸發時機（TriggerEvent）
3. 設定觸發條件（ConditionType，可跳過）
4. 定義效果（EffectType 與參數）
5. 若需要數值曲線，填寫 PartnerStackCurve（Stack 0～4）

**輸出範例**：
```
【AbilityMenu.xlsx / AbilityCatalog】
  AbilityId:        AB_Partner_Douglas_StrikerBuff
  ApplyPhase:       RUNTIME
  TriggerEvent:     FirstTurnStart
  ConditionGroupId: CG_ClassMatch
  EffectGroupId:    EG_AttackUp16_1Turn
  Priority:         0
  SourceType:       Partner
  Enabled:          TRUE

【AbilityMenu.xlsx / PartnerAbility】
  PartnerId:  Douglas
  AbilityId:  AB_Partner_Douglas_StrikerBuff

【ConditionMenu.xlsx / ConditionGroup】
  ConditionGroupId: CG_ClassMatch
  Logic:            AND

【ConditionMenu.xlsx / ConditionRow】
  ConditionGroupId: CG_ClassMatch
  ConditionType:    OwnerClassEqualsPartnerClass

【EffectMenu.xlsx / EffectGroup】
  EffectGroupId: EG_AttackUp16_1Turn
  ExecMode:      Sequential

【EffectMenu.xlsx / EffectRow（第 1 列）】
  EffectType: AddStatus  /  Value1: AttackUp  /  Value2: 1

【EffectMenu.xlsx / EffectRow（第 2 列）】
  EffectType: SetStatusParam  /  Value1: increase
  ValueRefType: PartnerStack  /  ValueRefId: PartnerDouglasAttackIncrease

【Partner.xlsx / PartnerStatStack】
  PartnerId:    Douglas
  StatTypeId:   PartnerDouglasAttackIncrease
  Stack0Value:  0.0  /  Stack1Value: 0.04  / ... / Stack4Value: 0.16
```

填完後建議執行 `/check-data` 確認資料完整。

---

## /battle-report

**用途**：讀取 `Reports/` 目錄下最新的戰鬥報表，產生勝率、回合數、HP 等統計摘要。

**使用時機**：
- 模擬跑完後，快速掌握這批結果的整體表現
- 比較不同設定（角色、夥伴、等級）的模擬結果差異

**分析內容**：
| 指標 | 說明 |
|------|------|
| 勝負分布 | 玩家勝率 / 敵方勝率 |
| 回合數 | 平均、最短、最長 |
| 玩家剩餘 HP | 勝利場次的平均剩餘量 |
| 敵人殘存 | 失敗場次平均殘存敵人數 |
| Ability 觸發 | 有觸發 Ability 的場次比例與次數分布 |
| Arwen 防護 | 平均初始點數與消耗次數（如適用） |

**輸出範例**：
```
📊 戰鬥報表摘要
報表：Reports/battle_report_20260424_153012.xlsx
模擬場數：100 場

【設定】
  log_level: INFO  |  ability_enabled: True

【勝負】
  玩家勝率：73%（73 勝 / 27 敗）
  平均回合數：8.4（最短 3，最長 21）

【玩家生命】
  勝利場均剩餘 HP：1240 / 3000（41%）

【敵人】
  失敗場均殘存敵人：1.3 隻

【Ability】
  有觸發場次：68%
  平均觸發次數：2.1 次 / 場
```

---

## /extend-ability

**用途**：逐步引導程式人員完成 Ability 系統的程式碼擴充，涵蓋五種擴充類型。

**使用時機**：
- 需要新增目前不支援的觸發條件、技能效果、狀態類型
- 要讓 Character / Equipment / Card / Monster 的 Ability 也能執行
- 不確定擴充需要改哪些檔案、改哪個函式

**支援的擴充類型**：

| 選項 | 說明 | 涉及檔案 |
|------|------|---------|
| 新增 ConditionType | 新的觸發條件（如「HP 低於 50%」） | `ability_models.py`、`ability_system.py`、`ConditionMenu.xlsx` |
| 新增 EffectType | 新的技能效果（如「固定回復 HP」） | `ability_models.py`、`ability_system.py`、`battle_simulator.py`、`EffectMenu.xlsx` |
| 新增 StatusType | 新的持續狀態（如「DefenseUp 減傷」） | `ability_models.py`、`models.py`、`ability_system.py`、`battle_simulator.py` |
| 新增 TriggerEvent | 新的觸發時機（如「怪物死亡時」） | `ability_models.py`、`battle_simulator.py`、`AbilityMenu.xlsx` |
| 擴充 SourceType | 讓 Character / Equipment / Card / Monster Ability 可執行 | `ability_repository.py`、`ability_system.py`、`battle_simulator.py`、`AbilityMenu.xlsx` |

**流程**：
1. 詢問要做哪種擴充
2. 依序說明每個需要修改的檔案、位置與程式碼範本
3. 最後提供完成後的通用檢查清單（含 `/check-data`、`/run-sim`、`/battle-report`）

---

## 推薦工作流程

```
修改資料
    ↓
/check-data   ← 確認格式無誤
    ↓
/run-sim      ← 執行模擬
    ↓
/battle-report ← 查看結果
```

新增技能時（純資料，不改程式）：

```
/add-ability  ← 取得填表清單
    ↓
填寫 Excel
    ↓
/check-data   ← 驗證填寫正確
    ↓
/run-sim + /battle-report
```

擴充技能系統時（需改程式）：

```
/extend-ability  ← 選擇擴充類型，取得逐步修改指引
    ↓
修改程式碼 + 填寫 Excel
    ↓
/check-data + /run-sim + /battle-report
```
