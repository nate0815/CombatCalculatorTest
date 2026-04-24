# 資料填寫規範（Data Specification）

本文件說明 `Data/` 目錄下各 Excel 檔案的填寫規範，供負責維護資料的人員使用。

> **重要原則**
> - 所有 ID 欄位（如 `CharacterId`、`MonsterId`）在同一份表格內必須**唯一**，且跨表引用時需**完全一致**（區分大小寫）。
> - 空白欄位請保持空白（不要填 0 或 N/A），程式會自動以預設值處理。
> - 不需要填寫的欄位留空即可，不影響運行。

---

## 目錄

1. [CombatInputPanel.xlsx](#1-combatinputpanelxlsx)
2. [Character.xlsx](#2-characterxlsx)
3. [Partner.xlsx](#3-partnerxlsx)
4. [Card.xlsx](#4-cardxlsx)
5. [Monster.xlsx](#5-monsterxlsx)
6. [AbilityMenu.xlsx](#6-abilitymenuXlsx)
7. [ConditionMenu.xlsx](#7-conditionmenuXlsx)
8. [EffectMenu.xlsx](#8-effectmenuXlsx)
9. [其他表格（尚未啟用）](#9-其他表格尚未啟用)

---

## 1. CombatInputPanel.xlsx

**用途**：指定本次模擬要使用的角色與配置。每一列代表一名參戰角色。

### 工作表：CombatInputPanel

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `CharacterId` | 文字 | ✅ | 角色 ID，需與 `Character.xlsx / CharacterIndex` 的 `CharacterId` 一致 |
| `Level` | 整數 | ✅ | 角色等級，需在 `CharacterBaseStatByLevel` 中有對應資料 |
| `PartnerId` | 文字 | ✅ | 夥伴 ID，需與 `Partner.xlsx / PartnerLevelStat` 的 `PartnerId` 一致 |
| `PartnerLevel` | 整數 | ✅ | 夥伴等級 |
| `PartnerStackCount` | 整數 | ✅ | 夥伴好感度堆疊層數，對應 `PartnerStatStack` 的 Stack 欄位（0～4） |
| `IsPartnerBonusApplied` | 0 / 1 | ✅ | 是否套用夥伴數值加成（1 = 套用，0 = 不套用） |
| `AffectionLevel` | 整數 | ✅ | 好感度等級（欄位讀取並儲存，但**目前不影響任何計算**；`Affection.xlsx` 尚未接入） |
| `FragmentIdList[]` | 文字 | ⬜ | 記憶碎片 ID（尚未啟用，可留空） |
| `FragmentLevelList[]` | 整數 | ⬜ | 記憶碎片等級（尚未啟用，可留空） |
| `FragmentRandomStatList[]` | 文字 | ⬜ | 碎片隨機詞條類型（尚未啟用，可留空） |
| `FragmentRandomValueList[]` | 數字 | ⬜ | 碎片隨機詞條數值（尚未啟用，可留空） |
| `EquipmentIdList[]` | 文字 | ⬜ | 裝備 ID（尚未啟用，可留空） |
| `CardList[]` | 文字 | ⬜ | 指定卡牌清單（尚未啟用，可留空） |
| `CardAwakeList[]` | 文字 | ⬜ | 卡牌覺醒設定（尚未啟用，可留空） |
| `PotentialNodeList[]` | 文字 | ⬜ | 潛能節點（尚未啟用，可留空） |
| `PotentialLevelList[]` | 整數 | ⬜ | 潛能節點等級（尚未啟用，可留空） |
| `Note` | 文字 | ⬜ | 備註，不影響計算 |

**填寫範例：**
```
CharacterId | Level | PartnerId  | PartnerLevel | PartnerStackCount | IsPartnerBonusApplied | AffectionLevel
Yuki        | 10    | Partner001 | 50           | 4                 | 1                     | 1
```

---

## 2. Character.xlsx

**用途**：定義所有角色的基本資料與各等級數值。

### 工作表：CharacterIndex

每一列代表一名角色。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `CharacterId` | 文字 | ✅ | 角色唯一 ID（英數，建議使用角色名稱，如 `Yuki`） |
| `NameKey` | 文字 | ⬜ | 顯示名稱（暫未使用，可留空） |
| `Rarity` | 文字 | ⬜ | 稀有度（暫未使用，可留空） |
| `Class` | 文字 | ✅ | 角色職業，需與 `Partner.xlsx / PartnerStatStack` 的 `Class` 一致。目前有效值：`Striker`、`Controller`、`Vanguard` |
| `AttributeType` | 文字 | ⬜ | 屬性類型（暫未使用，可留空） |
| `IsPlayable` | TRUE / FALSE | ✅ | 是否為可使用角色（通常填 `TRUE`） |
| `DefaultDeckId` | 文字 | ⬜ | 預設牌組 ID（暫未使用，可留空） |
| `PotentialTreeId` | 文字 | ⬜ | 潛能樹 ID（暫未使用，可留空） |

---

### 工作表：CharacterBaseStatByLevel

每一列代表某角色在某等級的數值。若跳過中間等級，程式會自動**線性插值**計算。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `CharacterId` | 文字 | ✅ | 角色 ID，需與 `CharacterIndex` 一致 |
| `Level` | 整數 | ✅ | 等級 |
| `Attack` | 數字 | ✅ | 攻擊力基礎值 |
| `Defense` | 數字 | ✅ | 防禦力基礎值 |
| `Health` | 數字 | ✅ | 生命值基礎值 |
| `IsAscensionLevel` | TRUE / FALSE | ⬜ | 是否為突破等級（預留欄位，填 `FALSE` 即可） |

> **插值說明**：只需填寫關鍵等級（如 1、10、20、50），中間等級由程式自動線性插值。超出最大等級時使用最大等級的數值。

---

## 3. Partner.xlsx

**用途**：定義所有夥伴的等級數值與技能堆疊曲線。

### 工作表：PartnerLevelStat

每一列代表某夥伴在某等級的加成數值。支援線性插值，填法同 `CharacterBaseStatByLevel`。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `PartnerId` | 文字 | ✅ | 夥伴唯一 ID（如 `Partner001`） |
| `Name（參考用）` | 文字 | ⬜ | 夥伴名稱，僅供參考，不影響計算 |
| `Level` | 整數 | ✅ | 等級 |
| `Attack` | 數字 | ✅ | 攻擊力加成（加在角色最終數值上） |
| `Defense` | 數字 | ✅ | 防禦力加成 |
| `Health` | 數字 | ✅ | 生命值加成 |

---

### 工作表：PartnerStatStack

定義夥伴的堆疊能力曲線（對應好感度堆疊層數 0～4）。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `PartnerId` | 文字 | ✅ | 夥伴 ID |
| `Name（參考用）` | 文字 | ⬜ | 夥伴名稱，僅供參考 |
| `Class` | 文字 | ✅ | 夥伴職業，需與 `Character.xlsx / CharacterIndex.Class` 的職業名稱一致 |
| `StatTypeId` | 文字 | ✅ | 能力類型 ID，對應 `EffectMenu.xlsx / EffectRow` 中 `ValueRefId` 欄的引用（如 `PartnerAttackIncrease`） |
| `Stack0Value` | 數字 | ✅ | 堆疊 0 層時的數值 |
| `Stack1Value` | 數字 | ✅ | 堆疊 1 層時的數值 |
| `Stack2Value` | 數字 | ✅ | 堆疊 2 層時的數值 |
| `Stack3Value` | 數字 | ✅ | 堆疊 3 層時的數值 |
| `Stack4Value` | 數字 | ✅ | 堆疊 4 層時的數值 |

> **說明**：`CombatInputPanel` 的 `PartnerStackCount` 填幾，就讀 `Stack{n}Value`。範圍限定在 0～4，超出上限時取最大值。

---

## 4. Card.xlsx

**用途**：定義所有卡牌的屬性與效果。

### 工作表：Card

每一列代表一張卡牌。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `CardId` | 文字 | ✅ | 卡牌唯一 ID（建議格式：`Card_{角色}_{序號}_{覺醒層數}`，如 `Card_Yuki_01_0`） |
| `CharacterId` | 文字 | ✅ | 所屬角色 ID，需與 `Character.xlsx / CharacterIndex` 一致 |
| `GroupId` | 文字 | ⬜ | 卡牌組別（同一組為同一張牌的不同版本，如 `Card_Yuki_01`） |
| `EpiphanyTier` | 整數 | ⬜ | 覺醒層數（0 = 未覺醒） |
| `ApCost` | 整數 | ✅ | 費用（欄位讀取並儲存，**目前不影響出牌選取**；AP 費用系統尚未實作，可暫填 1） |

---

### 工作表：CardEffect

每一列代表一張卡牌的一個效果。一張卡牌可有多個效果（用 `EffectIndex` 區分）。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `CardId` | 文字 | ✅ | 卡牌 ID，需與 `Card` 工作表一致 |
| `EffectIndex` | 整數 | ✅ | 效果序號（同一張牌從 0 開始遞增） |
| `EffectType` | 文字 | ✅ | 效果類型，見下方有效值 |
| `ScaleStat` | 文字 | ✅ | 效果數值以哪個屬性為基底：`ATK`（攻擊）、`DEF`（防禦）、`HP`（最大生命） |
| `Multiplier` | 數字 | ✅ | 倍率（最終數值 = ScaleStat × Multiplier + FlatValue） |
| `FlatValue` | 數字 | ⬜ | 固定加成值（不填預設為 0） |
| `CardLifecycle` | 文字 | ⬜ | 卡牌壽命規則：`Normal`（一般）、`Exhaust`（用掉即廢）、`Ethereal`（本回合用完消失）。不填預設 `Normal` |
| `AfterPlayMove` | 文字 | ⬜ | 出牌後動作：`Discard`（棄牌）。可留空 |
| `OnEndTurnAction` | 文字 | ⬜ | 回合結束動作（暫未使用，可留空） |
| `Target` | 文字 | ⬜ | 目標：`EnemySingle`（攻擊最前排敵人）、`PlayerSelf`（玩家自身）。可留空 |

**EffectType 有效值：**

| 值 | 說明 | 狀態 |
|----|------|------|
| `Damage` | 對敵人造成傷害，數值以 ScaleStat × Multiplier 計算 | ✅ 完整 |
| `Heal` | 回復玩家隊伍生命，數值同上 | ✅ 完整 |
| `Shield` | 產生護盾（數值計算存在，但護盾吸收傷害的邏輯尚未驗證完整） | ⚠️ 部分 |
| `Buff` | 施加增益狀態 | ❌ 未實作（`EffectType` 已定義，無執行邏輯） |
| `Debuff` | 施加減益狀態 | ❌ 未實作（`EffectType` 已定義，無執行邏輯） |

---

## 5. Monster.xlsx

**用途**：定義所有怪物的資料與技能行為。

### 工作表：MonsterIndex

怪物基本資料，每一列代表一種怪物。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `MonsterId` | 文字 | ✅ | 怪物唯一 ID（如 `Monster01`） |
| `MonsterRank` | 文字 | ⬜ | 怪物等級別（如 `Normal`、`Elite`、`Boss`，欄位讀取並儲存，**目前不影響怪物選取或戰鬥邏輯**） |
| `MonsterWeight` | 整數 | ✅ | 隨機出現權重，數字越大越容易被選到（最小填 1） |

---

### 工作表：MonsterBaseStat

怪物的基礎數值。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `MonsterId` | 文字 | ✅ | 怪物 ID，需與 `MonsterIndex` 一致 |
| `Level` | 整數 | ✅ | 等級（目前固定填 1） |
| `Attack` | 數字 | ✅ | 基礎攻擊力（**注意**：若 `MonsterSkill` 的 `Value > 0`，此欄位不會被技能使用，僅作 fallback） |
| `Defense` | 數字 | ✅ | 基礎防禦力（暫未影響計算） |
| `Health` | 數字 | ✅ | 最大生命值 |

---

### 工作表：MonsterSkill

怪物的技能設定，每一列代表一個技能。一隻怪物可有多個技能。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `SkillId` | 文字 | ✅ | 技能唯一 ID（建議格式：`{MonsterId}_{序號}`，如 `Monster01_1`） |
| `MonsterId` | 文字 | ✅ | 所屬怪物 ID，需與 `MonsterIndex` 一致 |
| `SkillType` | 文字 | ✅ | 技能類型，見下方有效值 |
| `Value` | 數字 | ✅ | 技能數值（攻擊傷害或護盾量）。**若 > 0 則直接使用此值**；若填 0 或留空，才會讀取 `MonsterBaseStat.Attack` |
| `CounterMax` | 整數 | ✅ | Counter 起始值，代表玩家需出幾張牌才能讓此技能就緒。填 3 表示玩家出第 3 張牌後技能 Ready |
| `ReloadTiming` | 文字 | ✅ | 技能使用後何時重置 Counter，目前填 `AfterEnemyAttackPhase` |
| `CounterMode` | 文字 | ✅ | Counter 啟用狀態：`Enabled`（啟用）、`Disabled`（停用） |
| `CounterStartTrigger` | 文字 | ✅ | Counter 開始計數的時機：填 `OnPlayerPlayCard`（玩家出牌時） |
| `EnemyPhaseActionRule` | 文字 | ✅ | 敵方行動規則：填 `ActIfNotActedThisTurn`（本回合未行動才執行） |
| `Target` | 文字 | ✅ | 技能目標：`Player`（攻擊玩家）、`Self`（作用於自身） |

**SkillType 有效值：**

| 值 | 說明 | 狀態 |
|----|------|------|
| `Attack` | 攻擊玩家，傷害 = `Value`（或 fallback `MonsterBaseStat.Attack`） | ✅ 完整 |
| `AddShield` | 對自身增加護盾，護盾量 = `Value` | ✅ 完整 |
| `Buff` | 施加增益 | ❌ 未實作（`MonsterSkillType` 已定義，無執行邏輯） |
| `Debuff` | 施加減益 | ❌ 未實作（`MonsterSkillType` 已定義，無執行邏輯） |

> **Counter 運作說明（逐步）**：
>
> Counter 是**倒數計時器**，代表「玩家再出幾張牌就觸發」：
>
> 1. **戰鬥開始**：`counter_now = CounterMax`，`ready = False`
> 2. **玩家每次出牌**（CounterStartTrigger=`OnPlayerPlayCard`）：
>    - `counter_now -= 1`
>    - 若 `counter_now <= 0`：將 `ready` 標記為 `True`（本回合不執行）
> 3. **進入敵方回合**：檢查每個 ready 的技能
>    - 若 `EnemyPhaseActionRule=ActIfNotActedThisTurn` 且該怪本回合已行動：跳過
>    - 否則執行技能，`acted_this_turn = True`
> 4. **技能執行後**（ReloadTiming=`AfterEnemyAttackPhase`）：
>    - `ready = False`，`counter_now = CounterMax`（重置）
>
> **填寫範例（CounterMax=3 的攻擊技能）**：
>
> | 回合 | 玩家出牌數 | counter_now 變化 | 敵方行動 |
> |------|-----------|-----------------|---------|
> | T1 | 3 張 | 3 → 2 → 1 → 0 (ready) | 攻擊，重置 counter=3 |
> | T2 | 1 張 | 3 → 2 | 不行動 |
> | T3 | 2 張 | 2 → 1 → 0 (ready) | 攻擊，重置 counter=3 |
>
> **ReloadTiming 說明**：
>
> | 值 | 說明 | 狀態 |
> |----|------|------|
> | `AfterEnemyAttackPhase` | 技能執行後立即重置（目前唯一支援的值） | ✅ 完整 |

---

## 6. AbilityMenu.xlsx

**用途**：定義所有 Ability（夥伴技能）的完整資料。包含三個工作表。

### 工作表：AbilityCatalog

每一列代表一個 Ability 定義。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `AbilityId` | 文字 | ✅ | Ability 唯一 ID（建議格式：`AB_{SourceType}_{PartnerId}_{描述}`，如 `AB_Partner_Douglas_StrikerBuff`） |
| `ApplyPhase` | 文字 | ✅ | 套用階段：`RUNTIME`（戰鬥中由 TriggerEvent 觸發）或 `PRE_BATTLE`（戰鬥初始化時套用一次）。**注意：`PRE_BATTLE` 已定義於資料模型，但 AbilitySystem 執行時不檢查此欄位，目前僅 `RUNTIME` 有效。** |
| `TriggerEvent` | 文字 | ✅ | 觸發時機，見下方有效值 |
| `ConditionGroupId` | 文字 | ⬜ | 條件群組 ID，對應 `ConditionMenu.xlsx / ConditionGroup`。留空表示無條件觸發 |
| `EffectGroupId` | 文字 | ✅ | 效果群組 ID，對應 `EffectMenu.xlsx / EffectGroup` |
| `Priority` | 整數 | ✅ | 執行優先度，數字大的先執行。相同時依 AbilityId 字母順序排列。通常填 `0` |
| `SourceType` | 文字 | ✅ | 來源類型，見下方有效值 |
| `Enabled` | TRUE / FALSE | ✅ | 是否啟用此 Ability |
| `Note` | 文字 | ⬜ | 備註說明，不影響計算 |

**SourceType 有效值：**

| 值 | 說明 | 狀態 |
|----|------|------|
| `Partner` | 夥伴技能（目前唯一有完整執行路徑的來源） | ✅ 完整 |
| `Character` | 角色技能 | ❌ 未實作（已定義，執行時被忽略） |
| `Equipment` | 裝備技能 | ❌ 未實作（已定義，執行時被忽略） |
| `Card` | 卡牌技能 | ❌ 未實作（已定義，執行時被忽略） |
| `Monster` | 怪物技能（Ability 系統） | ❌ 未實作（已定義，執行時被忽略） |

**TriggerEvent 有效值：**

| 值 | 說明 |
|----|------|
| `BattleStart` | 戰鬥開始時（每場一次） |
| `FirstTurnStart` | 第一回合開始時（每場一次） |
| `TurnStart` | 每回合開始時 |
| `OnPlayCard` | 玩家每次出牌時 |
| `TurnEnd` | 每回合結束時 |
| `OnEnemyAttack` | 敵人攻擊玩家時 |

---

### 工作表：PartnerAbility

將 Ability 綁定至特定夥伴。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `PartnerId` | 文字 | ✅ | 夥伴 ID，需與 `Partner.xlsx / PartnerLevelStat` 一致 |
| `AbilityId` | 文字 | ✅ | Ability ID，需與 `AbilityCatalog` 一致 |
| `Note` | 文字 | ⬜ | 備註，不影響計算 |

> 一個夥伴可綁定多個 Ability（新增多列），一個 Ability 也可以綁定至多個夥伴。

---

## 7. ConditionMenu.xlsx

**用途**：定義 Ability 的觸發條件。當所有條件滿足，Ability 才會執行 Effect。

### 工作表：ConditionGroup

條件群組的邏輯設定。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `ConditionGroupId` | 文字 | ✅ | 群組唯一 ID（建議格式：`CG_{描述}`，如 `CG_ClassMatch`） |
| `Logic` | 文字 | ✅ | 群組內多個條件的關係：`AND`（全部成立才觸發）、`OR`（任一成立即觸發） |

---

### 工作表：ConditionRow

群組內的個別條件。每一列代表一個條件，同一群組可有多列。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `ConditionGroupId` | 文字 | ✅ | 所屬群組 ID，需與 `ConditionGroup` 一致 |
| `ConditionType` | 文字 | ✅ | 條件類型，見下方有效值 |
| `Param1` ～ `Param4` | 文字 | ⬜ | 條件參數（部分條件類型需要填寫，見說明） |

**ConditionType 有效值：**

| 值 | 說明 | 需要的 Param | 狀態 |
|----|------|-------------|------|
| `OwnerClassEqualsPartnerClass` | 角色職業 == 夥伴職業（從 ctx 自動讀取，無需額外 Param） | 無 | ✅ 完整 |

> 新增 ConditionType 需同時修改 `ability_models.py`（ConditionType enum）與 `ability_system.py`（`_eval_condition_row()` 新增判斷邏輯）。

---

## 8. EffectMenu.xlsx

**用途**：定義 Ability 觸發後的實際效果。

### 工作表：EffectGroup

效果群組的執行設定。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `EffectGroupId` | 文字 | ✅ | 群組唯一 ID（建議格式：`EG_{描述}`，如 `EG_AttackUp16_1Turn`） |
| `ExecMode` | 文字 | ✅ | 執行模式：填 `Sequential`（依序執行，目前僅支援此值） |

---

### 工作表：EffectRow

群組內的個別效果。每一列代表一個效果，同一群組可有多列（依序執行）。

| 欄位 | 型態 | 必填 | 說明 |
|------|------|------|------|
| `EffectGroupId` | 文字 | ✅ | 所屬群組 ID，需與 `EffectGroup` 一致 |
| `EffectType` | 文字 | ✅ | 效果類型，見下方說明 |
| `Value1` | 文字/數字 | ✅ | 主要參數（依 EffectType 而定，見說明） |
| `Value2` | 數字 | ⬜ | 次要參數（依 EffectType 而定，見說明） |
| `Value3` | 數字 | ⬜ | 第三參數（目前大多不使用，填 0 或留空） |
| `ValueRefType` | 文字 | ⬜ | 數值來源類型：留空或 `None_` = 使用 `Value2` 常數；`PartnerStack` = 從夥伴堆疊曲線讀值 |
| `ValueRefId` | 文字 | ⬜ | 當 `ValueRefType = PartnerStack` 時，填對應 `Partner.xlsx / PartnerStatStack` 的 `StatTypeId`（如 `PartnerAttackIncrease`） |
| `TargetScope` | 文字 | ⬜ | 效果作用目標：`Owner`（角色自身）。可留空 |
| `DurationType` | 文字 | ⬜ | 持續類型：`TurnCount`（依回合數）。可留空 |
| `DurationValue` | 整數 | ⬜ | 持續回合數（搭配 `DurationType = TurnCount` 使用） |

**EffectType 詳細說明：**

| EffectType | Value1 | Value2 | ValueRefType / ValueRefId | 說明 | 狀態 |
|------------|--------|--------|--------------------------|------|------|
| `AddStatus` | 狀態名稱（如 `AttackUp`） | 持續回合數 | — | 為角色施加狀態，持續 Value2 回合 | ✅ |
| `SetStatusParam` | 狀態參數名稱（如 `increase`） | 常數數值 | `PartnerStack` + StatTypeId | 設定狀態的參數值 | ✅ |
| `SetExtraValue` | extra_ctx 的 key 名稱 | 常數數值 | 同上 | 寫入跨回合持久狀態（新值覆蓋舊值） | ✅ |
| `AddExtraValue` | extra_ctx 的 key 名稱 | 常數數值 | 同上 | 累加到跨回合持久狀態 | ✅ |
| `SetRuntimeMod` | runtime_mod 的 key 名稱（如 `player_damage_multiplier`） | 常數數值 | 同上 | 設定本次觸發的傷害/治癒倍率 | ✅ |
| `ConsumeExtraPointAndSetIncomingDamageMul` | 點數 key 名稱（如 `arwen_points`） | 承傷倍率（如 `0.9`） | — | 消耗 1 點，並將承傷倍率設為 Value2。點數耗盡後效果停止 | ✅ |

**AddStatus 可用的狀態名稱（StatusType）：**

| 狀態名稱 | 說明 | 狀態 |
|---------|------|------|
| `AttackUp` | 增加玩家傷害倍率（透過 `player_damage_multiplier`） | ✅ 完整 |
| `DefenseUp` 等其他狀態 | — | ❌ 未實作（需擴充 `ability_models.py` 的 `StatusType` enum 與計算邏輯）|

**runtime_mod 可用的 key：**

| Key | 說明 |
|-----|------|
| `player_damage_multiplier` | 玩家輸出傷害倍率（1.0 = 無加成） |
| `healing_multiplier` | 玩家治癒量倍率（1.0 = 無加成） |
| `incoming_damage_multiplier` | 玩家承傷倍率（1.0 = 無減傷；0.9 = 減傷 10%） |

---

## 9. 其他表格（尚未啟用）

以下 Excel 檔案已建立表格結構，但**目前尚未接入模擬計算**，資料填寫不影響模擬結果。

| 檔案 | 說明 |
|------|------|
| `Affection.xlsx` | 好感度各等級的數值加成 |
| `Equipment.xlsx` | 裝備資料與詞條效果 |
| `MemoryFragment.xlsx` | 記憶碎片資料與隨機詞條規則 |
| `Potential.xlsx` | 潛能樹節點與效果 |
| `PreBattleRule.xlsx` | 戰鬥前規則（如先手條件等） |

---

## 附錄：欄位實作狀態速查

> 供填表人員快速確認哪些欄位真正影響計算結果。✅ 影響計算 ⚠️ 部分 ❌ 不影響計算（填或不填結果一樣）

| 檔案 | 欄位 | 影響計算 | 備註 |
|------|------|---------|------|
| CombatInputPanel | CharacterId / Level | ✅ | — |
| CombatInputPanel | PartnerId / PartnerLevel / PartnerStackCount | ✅ | — |
| CombatInputPanel | IsPartnerBonusApplied | ⚠️ | 讀取但 Phase 1 固定套用加成，旗標未實際控制 |
| CombatInputPanel | AffectionLevel | ❌ | 讀取並儲存，Affection.xlsx 尚未接入 |
| CombatInputPanel | FragmentIdList / EquipmentIdList / CardList 等 | ❌ | 欄位預留，不影響模擬 |
| Character | CharacterId / Class / IsPlayable | ✅ | — |
| Character | CharacterBaseStatByLevel（Attack/Defense/Health） | ✅ | 支援線性插值 |
| Character | NameKey / Rarity / AttributeType / DefaultDeckId / PotentialTreeId | ❌ | 暫未使用 |
| Partner | PartnerLevelStat（Attack/Defense/Health） | ✅ | 支援線性插值 |
| Partner | PartnerStatStack（Stack0Value～Stack4Value） | ✅ | 用於 PartnerStack ValueRefType |
| Card | CardId / CharacterId / EffectType / ScaleStat / Multiplier | ✅ | — |
| Card | ApCost / EpiphanyTier / GroupId | ❌ | 讀取並儲存，不影響出牌 |
| Card | Shield / Buff / Debuff EffectType | ⚠️ / ❌ | Shield 部分、Buff/Debuff 未實作 |
| Monster | MonsterId / MonsterWeight | ✅ | Weight 影響怪物隨機選取 |
| Monster | MonsterRank | ❌ | 讀取並儲存，不影響戰鬥 |
| Monster | MonsterBaseStat（Attack/Health） | ✅ | Attack 作為傷害 fallback |
| Monster | MonsterBaseStat（Defense） | ❌ | 讀取但防禦計算尚未實作 |
| Monster | MonsterSkill（Attack/AddShield + Counter 欄位） | ✅ | — |
| Monster | MonsterSkill（Buff/Debuff SkillType） | ❌ | 已定義，無執行邏輯 |
| AbilityMenu | SourceType=Partner 的 Ability | ✅ | — |
| AbilityMenu | SourceType=Character/Equipment/Card/Monster | ❌ | 已定義，執行時被忽略 |
| AbilityMenu | ApplyPhase=RUNTIME | ✅ | — |
| AbilityMenu | ApplyPhase=PRE_BATTLE | ❌ | 已定義，未被檢查執行 |

---

*本文件對應程式版本：`refactor-log-output` 分支。*
