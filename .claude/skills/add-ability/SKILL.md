---
name: add-ability
description: 引導使用者逐步填寫新 Partner Ability 所需的所有 Excel 欄位，並輸出完整填表清單
---

引導使用者新增一個 Partner Ability，從頭到尾確認所有需要填寫的欄位，最後輸出一份完整的填表清單。

## 流程

### Step 1：確認夥伴
詢問使用者：
- 要為哪個夥伴（PartnerId）新增 Ability？
- 確認此 PartnerId 已存在於 `Partner.xlsx / PartnerLevelStat`

### Step 2：定義 Ability 基本資料（AbilityCatalog）
依序詢問：
1. **觸發時機（TriggerEvent）**：從以下選項選一個
   - `BattleStart` / `FirstTurnStart` / `TurnStart` / `TurnEnd` / `OnPlayCard` / `OnEnemyAttack`
2. **是否有觸發條件**：有的話進入 Step 3，沒有跳到 Step 4
3. **Priority**：通常填 0，有多個 Ability 需要順序時才調整
4. 建議 AbilityId 格式：`AB_Partner_{PartnerId}_{簡短描述}`

### Step 3：定義條件（ConditionMenu）
詢問：
- 使用哪種 ConditionType？目前只支援：
  - `OwnerClassEqualsPartnerClass`（角色職業 == 夥伴職業，無需額外參數）
- 建議 ConditionGroupId 格式：`CG_{描述}`
- Logic：`AND` 或 `OR`（單一條件時填 AND 即可）

### Step 4：定義效果（EffectMenu）
詢問想要的效果類型，並逐一確認參數：

**AddStatus + SetStatusParam（如 AttackUp）**：
- 狀態名稱：`AttackUp`（目前唯一可用）
- 持續回合數（Value2）
- 加成數值來源：常數（填具體數值）或 PartnerStackCurve（填 StatTypeId）

**SetExtraValue / AddExtraValue（跨回合持久狀態）**：
- key 名稱（任意字串，如 `my_points`）
- 數值

**SetRuntimeMod（當次觸發倍率）**：
- key：`player_damage_multiplier` / `healing_multiplier` / `incoming_damage_multiplier`
- 數值（如 1.2 = 傷害 +20%）

**ConsumeExtraPointAndSetIncomingDamageMul（消耗點數減傷，Arwen 模式）**：
- 點數 key 名稱
- 承傷倍率（如 0.9 = 減傷 10%）

建議 EffectGroupId 格式：`EG_{描述}`

### Step 5：是否需要 PartnerStackCurve
如果 Step 4 選擇了 PartnerStack 數值來源：
- 詢問 Stack 0～4 各層的數值
- StatTypeId 建議格式：`Partner{PartnerId}{效果描述}`

### Step 6：輸出填表清單
整理成以下格式，讓使用者對照 Excel 逐欄填寫：

```
【AbilityMenu.xlsx / AbilityCatalog】
  AbilityId:        AB_Partner_XXX_YYY
  ApplyPhase:       RUNTIME
  TriggerEvent:     FirstTurnStart
  ConditionGroupId: CG_XXX（或空白）
  EffectGroupId:    EG_XXX
  Priority:         0
  SourceType:       Partner
  Enabled:          TRUE

【AbilityMenu.xlsx / PartnerAbility】
  PartnerId:  XXX
  AbilityId:  AB_Partner_XXX_YYY

【ConditionMenu.xlsx / ConditionGroup】（如有條件）
  ConditionGroupId: CG_XXX
  Logic:            AND

【ConditionMenu.xlsx / ConditionRow】（如有條件）
  ConditionGroupId: CG_XXX
  ConditionType:    OwnerClassEqualsPartnerClass

【EffectMenu.xlsx / EffectGroup】
  EffectGroupId: EG_XXX
  ExecMode:      Sequential

【EffectMenu.xlsx / EffectRow】（每個效果一列）
  EffectGroupId:  EG_XXX
  EffectType:     AddStatus
  Value1:         AttackUp
  Value2:         1
  ...

【Partner.xlsx / PartnerStatStack】（如有 PartnerStack 曲線）
  PartnerId:    XXX
  StatTypeId:   PartnerXXXAttackIncrease
  Stack0Value:  0.0
  Stack1Value:  0.05
  ...
```

最後提示使用者填完後可執行 `/check-data` 驗證資料完整性。
