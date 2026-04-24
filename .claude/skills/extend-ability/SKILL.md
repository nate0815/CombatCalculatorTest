---
name: extend-ability
description: 逐步引導程式人員完成 Ability 系統的程式碼擴充，包含新增 ConditionType、EffectType、StatusType、TriggerEvent 或 SourceType 支援
---

引導使用者完成 Ability 系統的程式碼擴充。先詢問要擴充的類型，再逐步說明每個需要修改的檔案與寫法。

## Step 1：確認擴充類型

詢問使用者想要做哪種擴充：

1. **新增 ConditionType** — 新的觸發條件（如「角色 HP 低於 50%」）
2. **新增 EffectType** — 新的技能效果（如「直接回復固定 HP」）
3. **新增 StatusType** — 新的狀態效果（如「DefenseUp 減傷加成」）
4. **新增 TriggerEvent** — 新的觸發時機（如「怪物死亡時」）
5. **擴充 SourceType** — 讓 Character / Equipment / Card / Monster 的 Ability 也能執行

確認後依對應章節逐步執行。

---

## 擴充類型 1：新增 ConditionType

**說明**：新增一個判斷條件，讓 Ability 只在特定情況下觸發。

### 檔案 1：`ability_models.py`

在 `ConditionType` enum 新增項目：

```python
class ConditionType(str, Enum):
    OwnerClassEqualsPartnerClass = "OwnerClassEqualsPartnerClass"
    # 在此新增，例如：
    PlayerHpBelowThreshold = "PlayerHpBelowThreshold"
```

### 檔案 2：`ability_system.py`

在 `_eval_condition_row()`（約第 170 行）新增判斷分支：

```python
def _eval_condition_row(self, row, ctx, ability_context) -> bool:
    if row.condition_type == ConditionType.OwnerClassEqualsPartnerClass:
        ...

    # 新增在此，例如：
    if row.condition_type == ConditionType.PlayerHpBelowThreshold:
        threshold = float(row.arg1 or 0.5)           # Param1 = HP 比例門檻（預設 0.5）
        hp_now = float(ctx.get("player_hp_now", 1))
        hp_max = float(ctx.get("player_hp_max", 1))
        return (hp_now / hp_max) < threshold

    return False  # 未知條件 → 不觸發
```

**ctx 中可用的 key**（由 `battle_simulator.py` 的 `_trigger_ability` 傳入）：
- `partner_id`、`partner_stack_count`
- `owner_class`、`partner_class`
- `runtime_mod`（Dict）

> 如需新的 ctx key，需同時在 `battle_simulator.py` 的 `_trigger_ability` 呼叫處補上對應值。

### 檔案 3：`ConditionMenu.xlsx`

在 `ConditionRow` 工作表填入新 condition_type 字串，`Param1`～`Param4` 填對應參數。

### 最後：更新文件

在 `DATA_SPEC.md` 的 ConditionType 表格新增一列，標記狀態為 ✅。

---

## 擴充類型 2：新增 EffectType

**說明**：新增一種技能效果，觸發後執行自訂邏輯。

### 檔案 1：`ability_models.py`

在 `AbilityEffectType` enum 新增項目：

```python
class AbilityEffectType(str, Enum):
    AddStatus = "AddStatus"
    ...
    # 新增，例如：
    HealFlat = "HealFlat"
```

在同檔案 `EffectRowDef` 的 docstring 補上新 EffectType 的參數說明：

```python
"""
- HealFlat:
    value1 = （不使用）
    value2 = 回復量（float）
"""
```

### 檔案 2：`ability_system.py`

在 `_exec_effect_row()`（約第 279 行）的最後一個 `return` 之前新增處理邏輯：

```python
if effect_type == AbilityEffectType.HealFlat:
    heal_amount = self._resolve_value(row=row, ctx=ctx, ability_context=ability_context)
    # 寫入 runtime_mod，讓 battle_simulator 在結算時讀取
    runtime_mod["flat_heal_amount"] = float(runtime_mod.get("flat_heal_amount", 0)) + heal_amount
    return

# Unknown effect type -> no-op
return
```

### 檔案 3：`battle_simulator.py`

在對應時機的卡牌效果結算區塊，讀取並消費新的 runtime_mod key：

```python
flat_heal = float(runtime_mod.pop("flat_heal_amount", 0))
if flat_heal > 0:
    party.team_hp_now = min(party.team_hp_max, party.team_hp_now + flat_heal)
    self._event(...)
```

### 檔案 4：`EffectMenu.xlsx`

在 `EffectRow` 工作表使用新的 effect_type 字串填寫資料。

### 最後：更新文件

在 `DATA_SPEC.md` 的 EffectType 表格新增一列，標記狀態為 ✅。
在 `README.md` 的「目前支援的 EffectType」表格同步更新。

---

## 擴充類型 3：新增 StatusType

**說明**：新增一種持續回合的狀態效果（如 DefenseUp），讓角色在狀態生效期間改變某項數值。

### 檔案 1：`ability_models.py`

在 `StatusType` enum 新增項目：

```python
class StatusType(str, Enum):
    AttackUp = "AttackUp"
    # 新增，例如：
    DefenseUp = "DefenseUp"
```

若新狀態有專屬參數 key，在 `StatusParamKey` enum 也新增：

```python
class StatusParamKey(str, Enum):
    increase = "increase"
    # 新增，例如：
    reduction = "reduction"   # DefenseUp 的減傷比例
```

### 檔案 2：`models.py`

在 `PartyRuntimeState` 新增讀取新狀態的邏輯。

目前 `get_damage_multiplier()` 只處理 AttackUp，新增一個類似的方法，或在現有方法內擴充：

```python
def get_defense_multiplier(self) -> float:
    """回傳承傷倍率（1.0 = 無減傷；0.8 = 減傷 20%）"""
    mul = 1.0
    for s in self.statuses:
        if s.status_type == StatusType.DefenseUp:
            reduction = float(s.params.get(StatusParamKey.reduction.value, 0.0))
            mul *= (1.0 - reduction)
    return mul
```

### 檔案 3：`battle_simulator.py`

在敵方攻擊造成傷害的結算處，套用新的承傷邏輯：

```python
def_mul = party_runtime.get_defense_multiplier()
final_dmg = raw_dmg * def_mul
```

### 檔案 4：`ability_system.py`

在 `_exec_effect_row()` 的 `SetStatusParam` 分支，補上新狀態對應的 runtime_mod 轉換（若適用）：

```python
if status.status_type == StatusType.DefenseUp:
    runtime_mod["incoming_damage_multiplier"] = (
        1.0 - float(value)   # value = reduction 比例
    )
```

### 最後：更新文件

在 `README.md` 與 `DATA_SPEC.md` 的 StatusType 表格新增一列。

---

## 擴充類型 4：新增 TriggerEvent

**說明**：在戰鬥流程的新時機點觸發 Ability。

### 檔案 1：`ability_models.py`

在 `TriggerEvent` enum 新增項目：

```python
class TriggerEvent(str, Enum):
    BattleStart = "BattleStart"
    ...
    # 新增，例如：
    OnEnemyDeath = "OnEnemyDeath"
```

### 檔案 2：`battle_simulator.py`

找到對應的戰鬥時機（如怪物 HP 歸零後），呼叫 `_trigger_ability`：

```python
if enemy.is_dead():
    self._trigger_ability(
        battle_index=battle_index,
        turn=turn,
        trigger=TriggerEvent.OnEnemyDeath,
        extra_ctx=extra_ctx,
        runtime_mod=runtime_mod,
        source_desc=f"OnEnemyDeath monster={enemy.monster_id}",
    )
```

若新 TriggerEvent 需要額外的 ctx 資訊（如死亡的怪物 ID），在呼叫前補進 ctx dict：

```python
ctx["dead_monster_id"] = enemy.monster_id
```

### 檔案 3：`AbilityMenu.xlsx`

在 `AbilityCatalog` 的 TriggerEvent 欄填入新事件的字串。

### 最後：更新文件

在 `README.md` 與 `DATA_SPEC.md` 的 TriggerEvent 表格新增一列，標記狀態為 ✅。

---

## 擴充類型 5：擴充 SourceType（Character / Equipment / Card / Monster）

**說明**：讓非 Partner 來源的 Ability 也能被觸發執行。以 Character Ability 為例。

### 檔案 1：`ability_repository.py`

新增從 Excel 載入對應 source 的 Ability 綁定關係：

```python
# 仿照 partner_abilities 的載入方式
character_abilities: Dict[str, List[str]] = {}
df_char_ab = try_load_sheet("AbilityMenu.xlsx", "CharacterAbility")
if df_char_ab is not None:
    for _, r in df_char_ab.iterrows():
        cid = _norm(r.get("CharacterId"))
        aid = _norm(r.get("AbilityId"))
        if cid and aid:
            character_abilities.setdefault(str(cid), []).append(str(aid))
```

將 `character_abilities` 存入 `ability_context`：

```python
ability_context["character_abilities"] = character_abilities
```

### 檔案 2：`ability_system.py`

在 `_iter_active_abilities()` 新增 Character 查找分支（約第 113 行之後）：

```python
# 現有 Partner 分支
partner_id = ctx.get("partner_id") or ability_context.get("partner_id")
...
active_ids = partner_abilities.get(partner_id, [])

# 新增 Character 分支
character_id = ctx.get("character_id") or ability_context.get("character_id")
if character_id:
    character_abilities = ability_context.get("character_abilities", {})
    active_ids += character_abilities.get(str(character_id), [])
```

### 檔案 3：`battle_simulator.py`

在 `_trigger_ability` 的呼叫處補上 `character_id`（目前 ctx 未帶這個值）：

```python
self._trigger_ability(
    ...,
    # 補上 character_id，讓 ability_system 能查到 character_abilities
)
```

`_trigger_ability` 本體需將 `character_id` 寫入 ctx：

```python
ctx["character_id"] = active_character_id
```

### 檔案 4：`AbilityMenu.xlsx`

新增 `CharacterAbility` 工作表，欄位：`CharacterId`、`AbilityId`、`Note`。

### 最後：更新文件

- `README.md` 的實作狀態表：Character Ability 改為 ✅
- `DATA_SPEC.md` 的 SourceType 表格同步更新

---

## 完成後的通用檢查清單

每次擴充完成後，逐項確認：

- [ ] `ability_models.py` enum 已新增
- [ ] `ability_system.py` 執行邏輯已實作
- [ ] `battle_simulator.py` 呼叫時機 / ctx 已補齊（如適用）
- [ ] Excel 工作表欄位已對應填寫
- [ ] `README.md` 實作狀態表已更新（❌ → ✅）
- [ ] `DATA_SPEC.md` 對應表格已更新
- [ ] 執行 `/check-data` 確認資料格式無誤
- [ ] 執行 `/run-sim` 確認模擬可正常跑完
- [ ] 執行 `/battle-report` 確認新效果有反映在結果中
