# ② Claude Code実装指示書
# われまち農縁団OS

---

# 0. システムの目的

われまち農縁団OSは、

- 農業
- 料理
- 栽培計画
- 会計
- 資材調達
- 日誌
- チャット
- 知識創発

を循環させるためのシステムである。

最終目的は、

「農業×料理×会計×知識創発×コミュニティ」

の Company Brain を育てることである。

---

# 1. 基本アーキテクチャ

## 中心

Notion

## 周辺

- Claude Code
- ベクトルDB
- 会計アプリ
- Amazon
- 楽天
- モノタロウ
- Google Drive
- GitHub

---

# 2. データベース

## BasicBooks

基本書

### 属性

- id
- title
- author
- chapter
- quote
- summary
- tags
- source_type
- color

---

## WisePeople

賢人コーナー

### 属性

- id
- name
- concept
- quote
- source
- tags
- source_type
- color

---

## FarmDiary

農業日誌

### 属性

- date
- weather
- crop
- work_done
- observation
- question
- hypothesis
- advice
- source_type
- color

---

## Recipes

料理コーナー

### 属性

- recipe_name
- vegetable
- ingredients
- season
- notes
- source_type
- color

---

## CultivationPlans

栽培計画

### 属性

- month
- crop
- sowing_date
- planting_date
- harvest_period
- companion_plants
- required_materials
- source_type
- color

---

## ChatLogs

チャットコーナー

### 属性

- question
- answer
- related_topics
- source_type
- color

---

## AccountingData

会計データ

### 属性

- date
- category
- item
- supplier
- amount
- source_type

---

## Purchases

資材調達

### 属性

- item
- purpose
- amazon_price
- rakuten_price
- monotaro_price
- recommended_vendor
- purchase_status

---

## NetworkNodes

### 属性

- label
- type
- source_type
- color

---

## NetworkEdges

### 属性

- from_node
- to_node
- relationship
- weight

---

# 3. エージェント構成

---

## 農業日誌Agent

役割

- 日誌登録
- 質問抽出
- 基本書検索
- アドバイス生成

出力

- 気づき
- 仮説
- 次の実験

---

## 料理Agent

役割

- レシピ生成
- 原価率考慮
- カフェメニュー提案

出力

- レシピ
- 保存法
- 原価メモ

---

## 栽培計画Agent

役割

- 月別栽培計画
- コンパニオンプランツ提案
- 必要資材抽出

---

## 会計Agent

役割

- 領収書整理
- 原価率計算
- 粗利分析
- 商品別分析

---

## 資材調達Agent

役割

- 価格比較
- 購入候補提示

禁止事項

- AIが勝手に購入しない

---

## ネットワークAgent

役割

- ノード生成
- エッジ生成
- Mermaid出力
- CSV出力
- ベクトル図生成

色

- pink：創発知
- blue：賢人知
- purple：重なった知
- gray：数値データ

---

## 記事作成Agent

出力形式

```text
【創発知】

【賢人知】

【響き合う仮説】

【次に試すこと】
```

---

# 4. ベクトル検索

対象

- 基本書
- 賢人知
- 農業日誌
- チャット履歴
- 料理記録

候補

- Chroma
- LanceDB
- pgvector

---

# 5. RAG回答ルール

必ず以下に分ける。

```text
【創発知】

【賢人知】

【響き合う仮説】

【次に試すこと】
```

---

# 6. ネットワーク図

色

- pink：創発知
- blue：賢人知
- purple：重なった知
- gray：数値

出力

- Mermaid
- CSV
- Network Graph

---

# 7. 会計連携

将来連携

- freee
- マネーフォワード
- 弥生会計

最初はCSV運用でよい。

---

# 8. 資材調達

比較対象

- Amazon
- 楽天
- モノタロウ
- 農業専門店

AIは購入しない。

最終判断は人間。

---

# 9. 開発順序

## Phase1

ローカル版

- 日誌
- 料理
- 栽培計画
- チャット
- Mermaid

---

## Phase2

Notion連携

---

## Phase3

ベクトル検索

---

## Phase4

会計連携

---

## Phase5

資材調達

---

## Phase6

記事生成

---

# 10. 推奨技術

- Python
- Streamlit
- SQLite
- Pandas
- Mermaid
- CSV

後に

- Notion API
- Chroma
- Supabase
- freee API

へ発展させる。