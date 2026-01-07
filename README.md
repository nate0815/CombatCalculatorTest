# CombatCalculatorTest

一個用於 **角色與卡牌數值驗證** 的 Python 靜態戰鬥計算工具。  
目前專注於 **戰鬥前可確定的數值計算（Phase 1）** 與 **卡牌靜態效果計算（Phase 2）**，作為數值設計與驗證用的輔助工具。

---

## 🎯 專案目標

- 將複雜的數值規則從 Excel 表格中抽離
- 以 **可重現、可追蹤、可擴充** 的方式驗證數值公式
- 明確區分「角色基礎數值」與「卡牌效果計算」的責任邊界
- 作為後續戰鬥模擬（回合制 / 抽牌 / 機率）的基礎

---

## 🧱 整體架構概念

本專案採用 **兩階段（Phase-based）計算設計**：

### Phase 1：角色靜態數值（Static Character Stats）
- 計算所有「戰鬥開始前就能確定」的角色數值
- 輸出結果為 `CharacterSnapshot`
- 不涉及卡牌、回合或隨機性

### Phase 2：卡牌靜態效果（Static Card Calculation）
- 基於 `CharacterSnapshot` 計算卡牌的靜態輸出
- 僅處理倍率與效果數值
- 不處理抽牌、回合流程或實際戰鬥模擬

---

## 📁 專案結構

CombatCalculatorTest/
├─ Data/ # Excel 資料表（數值來源）
├─ common/ # 共用工具（log、驗證等）
├─ card_repository.py # 卡牌資料存取層
├─ combat_static_calculator.py # Phase 1：角色靜態數值計算
├─ card_static_calculator.py # Phase 2：卡牌靜態效果計算
├─ models.py # 資料結構定義（dataclass）
├─ main.py # 程式進入點
├─ .gitignore
└─ README.md



---

## 📄 檔案用途說明

### `Data/`
- 存放所有 Excel 資料表
- 作為數值的「單一來源（Source of Truth）」
- 不包含任何運算邏輯

---

### `common/`
- 共用工具與輔助模組
- 預期包含：
  - logging
  - 資料 schema 驗證
  - 輔助工具函式
- 不應依賴任何戰鬥或卡牌邏輯

---

### `models.py`
- 定義跨模組傳遞的資料結構（dataclass）
- 目前核心結構：
  - `CharacterSnapshot`：  
    Phase 1 的輸出，代表角色的靜態最終數值
- 設計原則：
  - 僅負責資料結構定義
  - 不放計算邏輯

---

### `card_repository.py`
- 卡牌資料存取層（Repository Pattern）
- 負責：
  - 讀取卡牌相關 Excel
  - 整理欄位與索引
  - 提供查詢介面給計算模組
- 不負責任何卡牌公式

---

### `combat_static_calculator.py`
- **Phase 1 核心模組**
- 聚合角色所有靜態數值來源（目前版本不含潛力）
- 輸出：
  - `CharacterSnapshot`
- 設計定位：
  - Phase 1 的 Orchestrator
  - 為所有後續計算提供穩定基底

---

### `card_static_calculator.py`
- **Phase 2 模組**
- 根據：
  - `CharacterSnapshot`
  - 卡牌靜態參數
- 計算卡牌的靜態效果或倍率結果
- 不處理：
  - 抽牌
  - 回合
  - 隨機性

---

### `main.py`
- 程式進入點（Entry Point）
- 負責：
  - 組合流程
  - 呼叫 Phase 1 / Phase 2
  - 控制輸出與測試案例
- 不包含任何數值公式

---

## ▶️ 使用方式（概念）

```bash
python main.py

可在 main.py 中指定測試角色與卡牌

執行後會印出或記錄：
Phase 1 的角色靜態數值
Phase 2 的卡牌靜態計算結果
（實際輸出內容依目前測試實作為準）
