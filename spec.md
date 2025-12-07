# Streamlit GUI システム仕様書（初期版）

## 1. システム概要

### 1.1 目的

本システムは unified-arb-engine（以下 UAG）が提供する情報をローカル環境で可視化するための Streamlit GUI を構築する。以下のデータをリアルタイムで参照可能にすることを目的とする。

- 各取引所・各通貨ペアの板情報（Orderbook）
- 検知されたアービトラージ機会（Opportunities）
- アービトラ機会ごとの推定利益
- 取引所・通貨ごとのポートフォリオ（Portfolio）

初期リリースでは参照専用とし、将来的に GUI から発注操作を追加できる構成とする。

### 1.2 構成

- **バックエンド（UAG）**  
  FastAPI 等で以下の REST API を提供する：  
  `/v1/orderbook/...`, `/v1/opportunities`, `/v1/portfolio`
- **フロントエンド（Streamlit）**  
  `http://localhost:8501` で動作。UAG の API をポーリングして表示を更新する。

---

## 2. 画面全体仕様

### 2.1 サイドバー（共通設定）

- API ベース URL 入力（例：`http://localhost:8000`）
- 取引所選択（複数）
- 通貨ペア選択（複数）
- 自動更新間隔（秒）
- 自動更新 ON/OFF

---

## 3. 画面タブ仕様

### 3.1 タブ 1：ダッシュボード

**目的**  
システム全体状況を俯瞰する。

**表示内容**

- サマリーカード
  - 総ポートフォリオ評価額
  - 稼働中取引所数
  - 現在のアビトラ機会数
- 最新アビトラ機会テーブル
  - 時刻 / 通貨
  - 買い取引所 / 売り取引所
  - 買値 / 売値
  - スプレッド（bps / 円）
  - 推定利益
- アビトラ発生状況の簡易グラフ（任意）

---

### 3.2 タブ 2：板情報ビュー（Orderbook Viewer）

**目的**  
選択した取引所・通貨ペアの板情報をリアルタイム表示する。

**表示内容**

- `{exchange} - {symbol}` のヘッダー（最終更新時刻付き）
- 買い板テーブル（価格 / 数量）
- 売り板テーブル（価格 / 数量）
- best bid / best ask / mid / spread

更新は自動更新間隔に応じてポーリングする（1〜3 秒推奨）。

---

### 3.3 タブ 3：アービトラ機会ビュー

**目的**  
UAG が検知したアビトラ機会を一覧で確認する。

**表示内容**

- フィルタ（最低スプレッド / 最低利益）
- アビトラ機会テーブル
  - 時刻
  - 通貨
  - 買い取引所 / 売り取引所
  - 買値 / 売値
  - スプレッド（bps / 円）
  - 想定サイズ
  - 推定利益
- 履歴（最大 N 件）の表示とグラフ（任意）

---

### 3.4 タブ 4：ポートフォリオビュー

**目的**  
各取引所の資産状況を一覧で確認する。

**表示内容**

- 総資産サマリー
  - 総評価額（JPY）
  - FIAT/USDT などの残高
  - 暗号資産合計
- 取引所別ポートフォリオ表
  - 取引所 / 通貨 / 数量 / 評価額
- 通貨詳細テーブル

更新間隔は 10〜30 秒推奨。

---

## 4. API 期待仕様（フロント視点）

### 4.1 板情報 API

`GET /v1/orderbook/{exchange}/{symbol}/latest`

```json
{
  "exchange": "bitbank",
  "symbol": "XRP/JPY",
  "timestamp": "2025-12-07T12:34:56.789",
  "bids": [{ "price": "320.5", "amount": "100" }],
  "asks": [{ "price": "321.0", "amount": "80" }],
  "best_bid": "320.5",
  "best_ask": "321.0",
  "mid_price": "320.75",
  "spread": "0.5"
}
```

### 4.2 アビトラ API

GET /v1/opportunities/latest`

```json
[
  {
    "timestamp": "2025-12-07T12:34:56.000",
    "base_symbol": "XRP",
    "buy_exchange": "bitbank",
    "sell_exchange": "bittrade",
    "buy_price": "320.5",
    "sell_price": "321.5",
    "spread_bps": "31.2",
    "estimated_size_jpy": "20000",
    "expected_profit_jpy": "140"
  }
]
```

### 4.3 ポートフォリオ API

`GET /v1/portfolio`

```json
{
  "updated_at": "2025-12-07T12:35:00.000",
  "total_value_jpy": "1050000",
  "exchanges": {
    "bitbank": {
      "BTC": {"amount": "0.02", "value_jpy": "700000"},
      "XRP": {"amount": "500", "value_jpy": "160000"}
    }
  }
}
```

## 5. 更新方式

Streamlit の自動更新（st_autorefresh 等）でポーリング方式を採用

板・アビトラ：1〜3 秒

ポートフォリオ：10〜30 秒

サイドバーで ON/OFF と間隔変更を可能にする

## 6. 将来拡張（初期スコープ外）

GUI から発注（単発注文・アビトラ自動発注）

UAG の start/stop 制御

WebSocket によるリアルタイムPush方式