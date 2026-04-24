---
name: check-data
description: 驗證 Data/ 目錄下的 Excel 檔案是否符合 DATA_SPEC.md 規範，回報缺漏或格式錯誤
---

逐一檢查 `Data/` 目錄下的 Excel 檔案，驗證結構與內容是否符合 DATA_SPEC.md 的規範。

## 檢查項目

### 1. 檔案存在性
確認以下檔案都存在於 `Data/`：
- `CombatInputPanel.xlsx`
- `Character.xlsx`
- `Partner.xlsx`
- `Card.xlsx`
- `Monster.xlsx`
- `AbilityMenu.xlsx`（若有使用 Ability 系統）
- `ConditionMenu.xlsx`（若有使用條件）
- `EffectMenu.xlsx`（若有使用效果）

### 2. 工作表存在性
對每個存在的檔案，確認必要的工作表（sheet）都存在：
- `CombatInputPanel.xlsx` → sheet: `CombatInputPanel`
- `Character.xlsx` → sheets: `CharacterIndex`, `CharacterBaseStatByLevel`
- `Partner.xlsx` → sheets: `PartnerLevelStat`, `PartnerStatStack`
- `Card.xlsx` → sheets: `Card`, `CardEffect`
- `Monster.xlsx` → sheets: `MonsterIndex`, `MonsterBaseStat`, `MonsterSkill`
- `AbilityMenu.xlsx` → sheets: `AbilityCatalog`, `PartnerAbility`

### 3. 必填欄位存在性
對每個工作表，確認必填欄位（✅ 標記的）都存在於欄位列中。

### 4. 跨表 ID 一致性
- `CombatInputPanel.CharacterId` 都存在於 `Character.CharacterIndex.CharacterId`
- `CombatInputPanel.PartnerId` 都存在於 `Partner.PartnerLevelStat.PartnerId`
- `Card.CharacterId` 都存在於 `Character.CharacterIndex.CharacterId`
- `MonsterSkill.MonsterId` 都存在於 `Monster.MonsterIndex.MonsterId`
- `MonsterBaseStat.MonsterId` 都存在於 `Monster.MonsterIndex.MonsterId`
- `PartnerAbility.PartnerId` 都存在於 `Partner.PartnerLevelStat.PartnerId`
- `PartnerAbility.AbilityId` 都存在於 `AbilityMenu.AbilityCatalog.AbilityId`

### 5. 數值合理性
- `CombatInputPanel.PartnerStackCount` 必須在 0～4 之間
- `CombatInputPanel.IsPartnerBonusApplied` 只能是 0 或 1
- `Monster.MonsterIndex.MonsterWeight` 必須 >= 1
- `MonsterSkill.CounterMax` 必須 > 0

## 輸出格式

以分類清單呈現：
- ✅ 通過的項目（簡短列出）
- ⚠️ 警告（可能不影響執行但值得注意）
- ❌ 錯誤（會導致模擬失敗）

最後一行給出「可以執行 /run-sim」或「請先修正 N 個錯誤」的明確結論。
