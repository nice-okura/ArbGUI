"""
Streamlit UI for unified-arb-engine (UAG).

Uses only standard library and streamlit. REST calls fetch live data when available.
"""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Tuple

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Theme colors
PRIMARY_BG = "#0f172a"
CARD_BG = "#111827"
TEXT_COLOR = "#e5e7eb"
ACCENT_GREEN = "#22c55e"
ACCENT_RED = "#ef4444"
DIVIDER = "#1f2937"

# Selectable options
AVAILABLE_EXCHANGES = ["bitbank", "bittrade", "zaif", "gmocoin"]
AVAILABLE_SYMBOLS = ["MONA/JPY", "LTC/JPY", "XRP/JPY"]


# ----------------------------------------------------------------------
# Mock data generators
# ----------------------------------------------------------------------
def fetch_mock_orderbook(api_base_url: str, exchange: str, symbol: str) -> Dict[str, Any]:
    """Return dummy orderbook-like data for the given exchange and symbol."""
    base_price = random.uniform(80, 80_000)
    step = base_price * 0.0005
    bids = [{"price": round(base_price - step * (i + 1), 2), "amount": round(random.uniform(0.1, 5), 3)} for i in range(5)]
    asks = [{"price": round(base_price + step * (i + 1), 2), "amount": round(random.uniform(0.1, 5), 3)} for i in range(5)]
    best_bid = bids[0]["price"]
    best_ask = asks[0]["price"]
    mid_price = round((best_bid + best_ask) / 2, 2)
    spread = round(best_ask - best_bid, 2)
    return {
        "exchange": exchange,
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "bids": bids,
        "asks": asks,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "spread": spread,
        # TODO: 実APIと接続
    }


def fetch_mock_opportunities(
    api_base_url: str,
    exchanges: List[str],
    symbols: List[str],
    limit: int = 15,
    min_spread_bps: float = 0.0,
    min_profit_jpy: float = 0.0,
) -> List[Dict[str, Any]]:
    """Generate mock arbitrage opportunities with simple filters."""
    results: List[Dict[str, Any]] = []
    if not exchanges or not symbols:
        return results

    max_trials = limit * 10
    for _ in range(max_trials):
        if len(results) >= limit:
            break
        buy_ex, sell_ex = random.sample(exchanges, k=2) if len(exchanges) >= 2 else (exchanges[0], exchanges[0])
        symbol = random.choice(symbols)
        base_price = random.uniform(50, 80_000)
        spread_bps = random.uniform(5, 80)
        buy_price = round(base_price * (1 - spread_bps / 20000), 2)
        sell_price = round(base_price * (1 + spread_bps / 20000), 2)
        expected_profit = round((sell_price - buy_price) * random.uniform(0.5, 3.0), 2)
        notional = round(random.uniform(50_000, 200_000), 0)
        if spread_bps < min_spread_bps or expected_profit < min_profit_jpy:
            continue
        results.append(
            {
                "時刻": datetime.utcnow().strftime("%H:%M:%S"),
                "通貨": symbol,
                "買い取引所": buy_ex,
                "売り取引所": sell_ex,
                "買値": buy_price,
                "売値": sell_price,
                "スプレッド(bps)": round(spread_bps, 2),
                "スプレッド(円)": round(sell_price - buy_price, 2),
                "想定サイズ": int(notional),
                "推定利益": expected_profit,
                # TODO: 実APIと接続
            }
        )
    return results


def fetch_mock_portfolio(api_base_url: str, exchanges: List[str]) -> Dict[str, Any]:
    """Return dummy portfolio summary and breakdown per exchange."""
    if not exchanges:
        exchanges = ["bitbank", "bittrade", "zaif"]
    symbols = ["BTC", "MONA", "LTC"]
    positions: List[Dict[str, Any]] = []
    total_value = 0.0
    for ex in exchanges:
        for symbol in symbols:
            amount = round(random.uniform(0.05, 3.5), 4)
            price = round(random.uniform(1_000, 7_000_000), 2)
            value = round(amount * price, 2)
            total_value += value
            positions.append(
                {
                    "取引所": ex,
                    "通貨": symbol,
                    "数量": amount,
                    "価格(JPY)": price,
                    "評価額(JPY)": value,
                }
            )
    return {
        "updated_at": datetime.utcnow().isoformat(),
        "total_value_jpy": round(total_value, 2),
        "positions": positions,
        # TODO: 実APIと接続
    }


def build_mock_time_series(points: int = 12) -> Tuple[List[str], List[float]]:
    """Create a simple time series for small charts."""
    now = datetime.utcnow()
    labels = [(now - timedelta(minutes=5 * i)).strftime("%H:%M") for i in reversed(range(points))]
    values = [round(random.uniform(0.95, 1.05) * 1_000_000, 2) for _ in range(points)]
    return labels, values


# ----------------------------------------------------------------------
# API helpers
# ----------------------------------------------------------------------
def request_json(url: str, timeout_sec: float = 5.0) -> Tuple[int, Any | None]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8")
            return status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (urllib.error.URLError, ValueError):
        return 0, None


def normalize_base_url(api_base_url: str) -> str:
    return api_base_url.rstrip("/")


def fetch_orderbook(api_base_url: str, exchange: str, symbol: str, depth: int = 5) -> Dict[str, Any] | None:
    base = normalize_base_url(api_base_url)
    symbol_path = urllib.parse.quote(symbol, safe="")
    url = f"{base}/api/v1/orderbooks/{urllib.parse.quote(exchange)}/{symbol_path}?depth={depth}"
    status, data = request_json(url)
    if status != 200 or not isinstance(data, dict):
        return None
    return data


def fetch_opportunities(
    api_base_url: str,
    min_spread_pct: float = 0.0,
    min_profit_jpy: float = 0.0,
) -> List[Dict[str, Any]]:
    base = normalize_base_url(api_base_url)
    params = urllib.parse.urlencode(
        {"min_spread_pct": min_spread_pct, "min_profit_jpy": min_profit_jpy}
    )
    url = f"{base}/api/v1/opportunities?{params}"
    status, data = request_json(url)
    if status != 200 or not isinstance(data, list):
        return []
    return data


def fetch_portfolio(api_base_url: str) -> Dict[str, Any] | None:
    base = normalize_base_url(api_base_url)
    url = f"{base}/api/v1/portfolio"
    status, data = request_json(url)
    if status != 200 or not isinstance(data, dict):
        return None
    return data


# ----------------------------------------------------------------------
# Data mapping helpers
# ----------------------------------------------------------------------
def format_time_label(timestamp: str, with_date: bool = False) -> str:
    try:
        ts = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone(timedelta(hours=9)))
        return dt.strftime("%Y-%m-%d %H:%M:%S" if with_date else "%H:%M:%S")
    except ValueError:
        return timestamp


def build_opportunity_rows(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for opp in opportunities:
        buy_amount = opp.get("buy_available_amount")
        sell_amount = opp.get("sell_available_amount")
        min_amount = min(buy_amount, sell_amount) if buy_amount and sell_amount else None
        buy_price = opp.get("buy_price")
        sell_price = opp.get("sell_price")
        spread_pct = opp.get("spread_pct")
        spread_bps = round(spread_pct * 100, 2) if isinstance(spread_pct, (int, float)) else None
        spread_jpy = opp.get("spread_jpy")
        est_size_jpy = (
            round(min_amount * min(buy_price, sell_price), 0)
            if min_amount and buy_price and sell_price
            else None
        )
        expected_profit_jpy = round(spread_jpy * min_amount, 2) if min_amount and spread_jpy else None
        rows.append(
            {
                "時刻": format_time_label(str(opp.get("timestamp", ""))),
                "通貨": opp.get("symbol", ""),
                "買い取引所": opp.get("buy_exchange", ""),
                "売り取引所": opp.get("sell_exchange", ""),
                "買値": buy_price,
                "売値": sell_price,
                "スプレッド(bps)": spread_bps,
                "スプレッド(円)": spread_jpy,
                "想定サイズ": int(est_size_jpy) if isinstance(est_size_jpy, (int, float)) else "—",
                "推定利益": expected_profit_jpy if expected_profit_jpy is not None else "—",
                "_buy_exchange": opp.get("buy_exchange"),
                "_sell_exchange": opp.get("sell_exchange"),
                "_buy_price": buy_price,
                "_sell_price": sell_price,
            }
        )
    return rows


def build_portfolio_positions(portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    positions: List[Dict[str, Any]] = []
    balances = portfolio.get("balances", {})
    for ex, ex_balances in balances.items():
        if not isinstance(ex_balances, dict):
            continue
        for currency, balance in ex_balances.items():
            if not isinstance(balance, dict):
                continue
            positions.append(
                {
                    "取引所": ex,
                    "通貨": currency,
                    "数量": balance.get("total", 0.0),
                    "価格(JPY)": balance.get("price_jpy"),
                    "評価額(JPY)": balance.get("value_jpy"),
                }
            )
    return positions


# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------
def load_styles() -> None:
    """Load external CSS and apply color placeholders."""
    css_path = Path("styles.css")
    css = css_path.read_text(encoding="utf-8")
    for key, value in {
        "__PRIMARY_BG__": PRIMARY_BG,
        "__CARD_BG__": CARD_BG,
        "__TEXT_COLOR__": TEXT_COLOR,
        "__ACCENT_GREEN__": ACCENT_GREEN,
        "__ACCENT_RED__": ACCENT_RED,
        "__DIVIDER__": DIVIDER,
    }.items():
        css = css.replace(key, value)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_dark_table(records: List[Dict[str, Any]], columns: List[str], height: int = 360) -> None:
    """Render a simple dark-themed table via HTML."""
    header_html = "".join([f"<th>{col}</th>" for col in columns])
    rows_html = ""
    for idx, row in enumerate(records):
        cells = "".join([f"<td>{row.get(col, '')}</td>" for col in columns])
        row_class = "even" if idx % 2 == 0 else "odd"
        rows_html += f"<tr class='{row_class}'>{cells}</tr>"
    table_html = f"""
    <div class="dark-table-wrapper" style="max-height:{height}px; overflow:auto;">
      <table class="dark-table">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


def render_dark_line_chart(labels: List[str], values: List[float], height: int = 280) -> None:
    """Render a dark-themed line chart using Vega-Lite spec."""
    data = [{"時刻": t, "評価額": v} for t, v in zip(labels, values)]
    spec = {
        "data": {"values": data},
        "mark": {"type": "line", "color": "#60a5fa", "strokeWidth": 2},
        "encoding": {
            "x": {"field": "時刻", "type": "ordinal", "axis": {"title": "時刻"}},
            "y": {"field": "評価額", "type": "quantitative", "axis": {"title": "評価額"}},
        },
        "config": {
            "background": PRIMARY_BG,
            "view": {"stroke": None},
            "axis": {
                "labelColor": TEXT_COLOR,
                "titleColor": TEXT_COLOR,
                "grid": True,
                "gridColor": DIVIDER,
                "domainColor": DIVIDER,
                "tickColor": DIVIDER,
            },
        },
    }
    st.vega_lite_chart(spec, width="stretch", height=height)


def render_dark_pie_chart(labels: List[str], values: List[float], amounts: List[float], height: int = 320) -> None:
    """Render a dark-themed pie chart using Vega-Lite spec."""
    data = [{"ラベル": l, "評価額": v, "数量": a} for l, v, a in zip(labels, values, amounts)]
    spec = {
        "data": {"values": data},
        "layer": [
            {
                "mark": {"type": "arc", "outerRadius": 120},
                "encoding": {
                    "theta": {"field": "評価額", "type": "quantitative"},
                    "color": {
                        "field": "ラベル",
                        "type": "nominal",
                        "scale": {"scheme": "tableau10"},
                        "legend": {"labelColor": TEXT_COLOR, "titleColor": TEXT_COLOR},
                    },
                    "tooltip": [
                        {"field": "ラベル", "type": "nominal", "title": "通貨"},
                        {"field": "数量", "type": "quantitative", "title": "数量", "format": ",.2f"},
                        {"field": "評価額", "type": "quantitative", "title": "評価額(JPY)", "format": ",.0f"},
                    ],
                },
            },
            {
                "mark": {"type": "text", "radius": 140, "color": TEXT_COLOR, "fontSize": 12},
                "encoding": {
                    "theta": {"field": "評価額", "type": "quantitative"},
                    "text": {"field": "数量", "type": "quantitative", "format": ",.2f"},
                    "color": {"value": TEXT_COLOR},
                },
            },
        ],
        "config": {"background": PRIMARY_BG, "view": {"stroke": None}, "arc": {"stroke": PRIMARY_BG, "strokeWidth": 1}},
    }
    st.vega_lite_chart(spec, width="stretch", height=height)


def render_orderbook_table(orderbook: Dict[str, Any], highlight: Dict[str, Any] | None = None) -> None:
    """Render a vertical orderbook: asks on top, mid/spread center, bids below."""
    asks = list(reversed(orderbook["asks"]))  # highest ask at top
    bids = orderbook["bids"]  # best bid first
    highlight_role = highlight.get("role") if highlight else None
    highlight_price = highlight.get("price") if highlight else None
    ask_hit_idx = None
    bid_hit_idx = None
    if highlight_price is not None:
        if highlight_role == "buy" and asks:
            ask_hit_idx = min(range(len(asks)), key=lambda i: abs(asks[i].get("price", 0) - highlight_price))
        if highlight_role == "sell" and bids:
            bid_hit_idx = min(range(len(bids)), key=lambda i: abs(bids[i].get("price", 0) - highlight_price))

    def build_ask_rows(levels: List[Dict[str, Any]]) -> str:
        rows = []
        for lvl in levels:
            idx = len(rows)
            is_hit = ask_hit_idx is not None and idx == ask_hit_idx
            hit_class = " highlight" if is_hit else ""
            rows.append(
                f"<tr class='red-row{hit_class}'>"
                f"<td class='cell amount red left col-amount'>{lvl.get('amount','')}</td>"
                f"<td class='cell price red center col-price'>{lvl.get('price','')}</td>"
                f"<td class='cell amount spacer col-amount'>&nbsp;</td>"
                f"</tr>"
            )
        return "".join(rows)

    def build_bid_rows(levels: List[Dict[str, Any]]) -> str:
        rows = []
        for lvl in levels:
            idx = len(rows)
            is_hit = bid_hit_idx is not None and idx == bid_hit_idx
            hit_class = " highlight" if is_hit else ""
            rows.append(
                f"<tr class='green-row{hit_class}'>"
                f"<td class='cell amount spacer col-amount'>&nbsp;</td>"
                f"<td class='cell price green center col-price'>{lvl.get('price','')}</td>"
                f"<td class='cell amount green right col-amount'>{lvl.get('amount','')}</td>"
                f"</tr>"
            )
        return "".join(rows)

    asks_html = build_ask_rows(asks)
    bids_html = build_bid_rows(bids)
    mid_price = orderbook["mid_price"]
    spread = orderbook["spread"]
    best_bid = orderbook["best_bid"]
    best_ask = orderbook["best_ask"]

    table_html = dedent(
        f"""
        <div class="orderbook-card vertical">
            <div class="orderbook-header-vertical">
                <span class="left">売り厚</span>
                <span class="center">価格</span>
                <span class="right">買い厚</span>
            </div>
            <table class="orderbook-table-vertical">
                <colgroup>
                    <col style="width: 30%">
                    <col style="width: 40%">
                    <col style="width: 30%">
                </colgroup>
                <tbody>
                    {asks_html}
                    <tr class="mid-row">
                        <td class="cell mid-cell" colspan="3">
                            <div class="mid-wrapper">
                                <div class="mid-price">最終約定 (mid): {mid_price}</div>
                                <div class="mid-spread">spread: {spread} / best bid: {best_bid} / best ask: {best_ask}</div>
                            </div>
                        </td>
                    </tr>
                    {bids_html}
                </tbody>
            </table>
        </div>
        """
    )
    st.markdown(table_html, unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Main app
# ----------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="UAG 可視化モック", layout="wide")
    load_styles()
    st.title("Unified-Arb-Engine 可視化モック")

    # session caches
    st.session_state.setdefault("orderbook_cache", {})
    st.session_state.setdefault("orderbook_cache_ver", {})
    st.session_state.setdefault("opp_cache", {})
    st.session_state.setdefault("opp_cache_ver", {})

    with st.sidebar:
        st.header("共通設定")
        api_base_url = st.text_input("API ベース URL", value="http://localhost:8000")
        exchanges = st.multiselect("取引所選択", AVAILABLE_EXCHANGES, default=AVAILABLE_EXCHANGES)
        symbols = st.multiselect("通貨ペア選択", AVAILABLE_SYMBOLS, default=AVAILABLE_SYMBOLS)
        refresh_sec = st.number_input("自動更新間隔 (秒)", min_value=1, max_value=300, value=15, step=1)
        auto_refresh = st.checkbox("自動更新 ON/OFF", value=True)
        st.divider()
        st.caption("APIに接続して表示します（未取得時は空表示）。")

    refresh_tick = st_autorefresh(interval=int(refresh_sec * 1000), key="auto_refresh") if auto_refresh else 0
    tab_dashboard, tab_orderbook, tab_arbitrage, tab_portfolio = st.tabs(
        ["ダッシュボード", "板情報", "アービトラ機会", "ポートフォリオ"]
    )

    with tab_dashboard:
        st.subheader("サマリー")
        portfolio_data = fetch_portfolio(api_base_url) or {"total_value_jpy": 0.0}
        opportunities = fetch_opportunities(api_base_url)
        opp_count = len(opportunities)
        opp_data = build_opportunity_rows(opportunities)[:12]
        c1, c2, c3 = st.columns(3)
        c1.metric("総ポートフォリオ評価額 (JPY)", f"{portfolio_data['total_value_jpy']:,}")
        c2.metric("稼働中取引所数", len(exchanges) if exchanges else 0)
        c3.metric("アービトラ機会数", opp_count)
        st.subheader("アービトラ機会一覧")
        render_dark_table(
            opp_data,
            ["時刻", "通貨", "買い取引所", "売り取引所", "買値", "売値", "スプレッド(bps)", "スプレッド(円)", "想定サイズ", "推定利益"],
            height=360,
        )
        st.subheader("簡易パフォーマンス推移")
        labels, values = build_mock_time_series()
        render_dark_line_chart(labels, values, height=280)

    with tab_orderbook:
        st.subheader("板情報")
        if not exchanges or not symbols:
            st.info("サイドバーで取引所と通貨ペアを選択してください。")
        else:
            for sym in symbols:
                st.markdown(f"### {sym}")
                opp_cache = st.session_state["opp_cache"]
                opp_cache_ver = st.session_state["opp_cache_ver"]
                opp_key = sym
                if opp_cache_ver.get(opp_key) != refresh_tick:
                    all_opps = fetch_opportunities(api_base_url)
                    filtered = [opp for opp in all_opps if opp.get("symbol") == sym]
                    opp_cache[opp_key] = build_opportunity_rows(filtered)[:5]
                    opp_cache_ver[opp_key] = refresh_tick
                top_opps = opp_cache.get(opp_key, [])
                highlight_state_key = f"highlight_{sym}"
                st.caption("アビトラ機会（プルダウンで選択してハイライト）")
                if top_opps:
                    default_idx = st.session_state.get(highlight_state_key, {}).get("row", 0)
                    option_labels = [
                        f"{i+1}: {opp['買い取引所']}買({opp['買値']}) → {opp['売り取引所']}売({opp['売値']}) | spread {opp['スプレッド(bps)']}bps / 利益 {opp['推定利益']}"
                        for i, opp in enumerate(top_opps)
                    ]
                    selected_idx = st.selectbox(
                        "ハイライト対象",
                        options=list(range(len(top_opps))),
                        format_func=lambda i: option_labels[i],
                        index=min(default_idx, len(top_opps) - 1),
                        key=f"opp-select-{sym}",
                    )
                    st.session_state[highlight_state_key] = {"row": selected_idx, **top_opps[selected_idx]}
                cols = st.columns(len(exchanges))
                available: List[Tuple[str, Dict[str, Any]]] = []
                for ex in exchanges:
                    ob_cache = st.session_state["orderbook_cache"]
                    ob_cache_ver = st.session_state["orderbook_cache_ver"]
                    ob_key = f"{ex}:{sym}"
                    if ob_cache_ver.get(ob_key) != refresh_tick:
                        ob_cache[ob_key] = fetch_orderbook(api_base_url, ex, sym, depth=5)
                        ob_cache_ver[ob_key] = refresh_tick
                    ob = ob_cache[ob_key]
                    if ob:
                        available.append((ex, ob))
                if not available:
                    st.caption("板情報が取得できませんでした。")
                    st.divider()
                    continue
                cols = st.columns(len(available))
                for col, (ex, ob) in zip(cols, available):
                    highlight = None
                    h_state = st.session_state.get(highlight_state_key, {})
                    if h_state:
                        if ex == h_state.get("買い取引所"):
                            highlight = {"role": "buy", "price": h_state.get("買値")}
                        elif ex == h_state.get("売り取引所"):
                            highlight = {"role": "sell", "price": h_state.get("売値")}
                    with col:
                        updated_at = format_time_label(str(ob["timestamp"]), with_date=True)
                        st.markdown(f"**{ob['exchange']}**  (更新: {updated_at})")
                        render_orderbook_table(ob, highlight=highlight)
                st.divider()

    with tab_arbitrage:
        st.subheader("アービトラ機会")
        f1, f2 = st.columns(2)
        min_spread = f1.slider("最低スプレッド (bps)", min_value=-10.0, max_value=100.0, value=5.0, step=0.5)
        min_profit = f2.slider("最低利益 (JPY)", min_value=0, max_value=50000, value=500, step=100)
        min_spread_pct = max(min_spread, 0.0) / 100.0
        opportunities = fetch_opportunities(
            api_base_url, min_spread_pct=min_spread_pct, min_profit_jpy=float(min_profit)
        )
        opportunities = build_opportunity_rows(opportunities)
        render_dark_table(
            opportunities,
            ["時刻", "通貨", "買い取引所", "売り取引所", "買値", "売値", "スプレッド(bps)", "スプレッド(円)", "想定サイズ", "推定利益"],
            height=500,
        )

    with tab_portfolio:
        st.subheader("ポートフォリオ")
        portfolio_data = fetch_portfolio(api_base_url)
        if not portfolio_data:
            st.warning("ポートフォリオ情報が取得できません。")
        else:
            c1, c2 = st.columns(2)
            c1.metric("総評価額 (JPY)", f"{portfolio_data['total_value_jpy']:,}")
            positions = build_portfolio_positions(portfolio_data)
            c2.metric("保有銘柄数", len(positions))
            st.write("取引所別ポートフォリオ")
            exchanges_list = sorted(list({p["取引所"] for p in positions}))
            assets = sorted(list({p["通貨"] for p in positions}))
            total_port_value = portfolio_data.get("total_value_jpy") or 0.0
            matrix_rows: List[Dict[str, Any]] = []
            asset_values: List[float] = []
            asset_amounts: List[float] = []
            for asset in assets:
                row: Dict[str, Any] = {"通貨": asset}
                asset_positions = [p for p in positions if p["通貨"] == asset]
                total_amount = sum(p["数量"] for p in asset_positions)
                total_value_asset = sum(p["評価額(JPY)"] or 0.0 for p in asset_positions)
                price = round(total_value_asset / total_amount, 2) if total_amount > 0 and total_value_asset else 0.0
                for ex in exchanges_list:
                    amt = next((p["数量"] for p in asset_positions if p["取引所"] == ex), 0.0)
                    row[ex] = "—" if amt == 0 else f"{amt:,.4f}"
                row["総数量"] = f"{total_amount:,.4f}"
                row["Price(JPY)"] = "—" if price == 0 else f"{price:,.2f}"
                row["Value(JPY)"] = "—" if total_value_asset == 0 else f"{total_value_asset:,.2f}"
                share = (total_value_asset / total_port_value * 100) if total_port_value and total_value_asset else None
                row["Share"] = f"{share:,.1f}%" if share is not None else "—"
                matrix_rows.append(row)
                asset_values.append(total_value_asset)
                asset_amounts.append(total_amount)
            matrix_columns = ["通貨"] + exchanges_list + ["総数量", "Price(JPY)", "Value(JPY)", "Share"]
            render_dark_table(matrix_rows, matrix_columns, height=420)
            st.write(f"総評価額 (JPY): {total_port_value:,.0f}")
            st.write("簡易ポートフォリオ構成（円グラフ）")
            if any(asset_values):
                render_dark_pie_chart(assets, asset_values, asset_amounts, height=340)
            else:
                st.info("評価額情報が取得できないため、円グラフは省略しています。")


if __name__ == "__main__":
    main()
