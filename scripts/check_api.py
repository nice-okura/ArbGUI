#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Tuple


def fetch_json(url: str, timeout: float = 5.0) -> Tuple[int, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8")
            return status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        return exc.code, body


def ensure_keys(obj: Dict[str, Any], keys: Iterable[str]) -> List[str]:
    missing = [k for k in keys if k not in obj]
    return missing


def ensure_list(obj: Any) -> bool:
    return isinstance(obj, list)


def print_result(ok: bool, label: str, detail: str = "") -> None:
    status = "OK" if ok else "NG"
    if detail:
        print(f"[{status}] {label}: {detail}")
    else:
        print(f"[{status}] {label}")


def test_arbgui(base_url: str, exchange: str, symbol: str) -> int:
    failures = 0
    symbol_path = urllib.parse.quote(symbol, safe="")

    orderbook_url = f"{base_url}/v1/orderbook/{exchange}/{symbol_path}/latest"
    status, data = fetch_json(orderbook_url)
    if status != 200 or not isinstance(data, dict):
        print_result(False, "orderbook latest", f"status={status}")
        failures += 1
    else:
        required = [
            "exchange",
            "symbol",
            "timestamp",
            "bids",
            "asks",
            "best_bid",
            "best_ask",
            "mid_price",
            "spread",
        ]
        missing = ensure_keys(data, required)
        print_result(not missing, "orderbook latest keys", ",".join(missing))
        failures += 1 if missing else 0

    opp_url = f"{base_url}/v1/opportunities/latest"
    status, data = fetch_json(opp_url)
    if status != 200 or not ensure_list(data):
        print_result(False, "opportunities latest", f"status={status}")
        failures += 1
    else:
        if data:
            required = [
                "timestamp",
                "base_symbol",
                "buy_exchange",
                "sell_exchange",
                "buy_price",
                "sell_price",
                "spread_bps",
                "estimated_size_jpy",
                "expected_profit_jpy",
            ]
            missing = ensure_keys(data[0], required) if isinstance(data[0], dict) else required
            print_result(not missing, "opportunities keys", ",".join(missing))
            failures += 1 if missing else 0
        else:
            print_result(True, "opportunities latest", "empty list")

    portfolio_url = f"{base_url}/v1/portfolio"
    status, data = fetch_json(portfolio_url)
    if status != 200 or not isinstance(data, dict):
        print_result(False, "portfolio", f"status={status}")
        failures += 1
    else:
        required = ["updated_at", "total_value_jpy", "exchanges"]
        missing = ensure_keys(data, required)
        print_result(not missing, "portfolio keys", ",".join(missing))
        failures += 1 if missing else 0

    return failures


def test_openapi(base_url: str, exchange: str, symbol: str) -> int:
    failures = 0
    symbol_qs = urllib.parse.quote(symbol, safe="")
    symbol_path = urllib.parse.quote(symbol, safe="")

    health_url = f"{base_url}/api/v1/health"
    status, data = fetch_json(health_url)
    ok = status == 200 and isinstance(data, dict) and "status" in data
    print_result(ok, "health", f"status={status}")
    failures += 0 if ok else 1

    orderbook_url = (
        f"{base_url}/api/v1/orderbooks?"
        f"exchange={urllib.parse.quote(exchange)}&symbol={symbol_qs}&depth=5"
    )
    status, data = fetch_json(orderbook_url)
    if status != 200 or not ensure_list(data):
        print_result(False, "orderbooks list", f"status={status}")
        failures += 1
    else:
        if data:
            required = ["exchange", "symbol", "timestamp", "bids", "asks"]
            missing = ensure_keys(data[0], required) if isinstance(data[0], dict) else required
            print_result(not missing, "orderbooks keys", ",".join(missing))
            failures += 1 if missing else 0
        else:
            print_result(True, "orderbooks list", "empty list")

    orderbook_one_url = f"{base_url}/api/v1/orderbooks/{urllib.parse.quote(exchange)}/{symbol_path}?depth=5"
    status, data = fetch_json(orderbook_one_url)
    if status != 200 or not isinstance(data, dict):
        print_result(False, "orderbooks single", f"status={status}")
        failures += 1
    else:
        required = ["exchange", "symbol", "timestamp", "bids", "asks"]
        missing = ensure_keys(data, required)
        print_result(not missing, "orderbooks single keys", ",".join(missing))
        failures += 1 if missing else 0

    orderbook_hist_url = f"{base_url}/api/v1/orderbooks/history?limit=5"
    status, data = fetch_json(orderbook_hist_url)
    if status != 200 or not ensure_list(data):
        print_result(False, "orderbooks history", f"status={status}")
        failures += 1
    else:
        if data:
            required = ["exchange", "symbol", "timestamp", "bids", "asks"]
            missing = ensure_keys(data[0], required) if isinstance(data[0], dict) else required
            print_result(not missing, "orderbooks history keys", ",".join(missing))
            failures += 1 if missing else 0
        else:
            print_result(True, "orderbooks history", "empty list")

    opp_url = f"{base_url}/api/v1/opportunities"
    status, data = fetch_json(opp_url)
    if status != 200 or not ensure_list(data):
        print_result(False, "opportunities", f"status={status}")
        failures += 1
    else:
        if data:
            required = [
                "symbol",
                "buy_exchange",
                "sell_exchange",
                "buy_price",
                "sell_price",
                "spread_jpy",
                "spread_pct",
                "timestamp",
            ]
            missing = ensure_keys(data[0], required) if isinstance(data[0], dict) else required
            print_result(not missing, "opportunities keys", ",".join(missing))
            failures += 1 if missing else 0
        else:
            print_result(True, "opportunities", "empty list")

    opp_hist_url = f"{base_url}/api/v1/opportunities/history?limit=5"
    status, data = fetch_json(opp_hist_url)
    if status != 200 or not ensure_list(data):
        print_result(False, "opportunities history", f"status={status}")
        failures += 1
    else:
        if data:
            required = [
                "symbol",
                "buy_exchange",
                "sell_exchange",
                "buy_price",
                "sell_price",
                "spread_jpy",
                "spread_pct",
                "timestamp",
            ]
            missing = ensure_keys(data[0], required) if isinstance(data[0], dict) else required
            print_result(not missing, "opportunities history keys", ",".join(missing))
            failures += 1 if missing else 0
        else:
            print_result(True, "opportunities history", "empty list")

    portfolio_url = f"{base_url}/api/v1/portfolio"
    status, data = fetch_json(portfolio_url)
    if status != 200 or not isinstance(data, dict):
        print_result(False, "portfolio", f"status={status}")
        failures += 1
    else:
        required = ["balances", "total_value_jpy", "last_updated"]
        missing = ensure_keys(data, required)
        print_result(not missing, "portfolio keys", ",".join(missing))
        failures += 1 if missing else 0

    exec_summary_url = f"{base_url}/api/v1/executions/summary"
    status, data = fetch_json(exec_summary_url)
    if status != 200 or not isinstance(data, dict):
        print_result(False, "executions summary", f"status={status}")
        failures += 1
    else:
        required = [
            "active_orders",
            "recent_executions",
            "total_trades",
            "successful_trades",
            "failed_trades",
            "total_profit_jpy",
        ]
        missing = ensure_keys(data, required)
        print_result(not missing, "executions summary keys", ",".join(missing))
        failures += 1 if missing else 0

    exec_hist_url = f"{base_url}/api/v1/executions/history?limit=5"
    status, data = fetch_json(exec_hist_url)
    if status != 200 or not ensure_list(data):
        print_result(False, "executions history", f"status={status}")
        failures += 1
    else:
        if data:
            required = [
                "id",
                "opportunity",
                "buy_order_id",
                "sell_order_id",
                "status",
                "created_at",
                "one_sided_risk",
            ]
            missing = ensure_keys(data[0], required) if isinstance(data[0], dict) else required
            print_result(not missing, "executions history keys", ",".join(missing))
            failures += 1 if missing else 0
        else:
            print_result(True, "executions history", "empty list")

    stats_url = f"{base_url}/api/v1/stats"
    status, data = fetch_json(stats_url)
    if status != 200 or not isinstance(data, dict):
        print_result(False, "stats", f"status={status}")
        failures += 1
    else:
        required = [
            "total_orderbooks",
            "orderbook_history_size",
            "current_opportunities",
            "opportunity_history_size",
            "active_orders",
            "execution_history_size",
            "total_trades",
            "successful_trades",
            "failed_trades",
            "total_profit_jpy",
        ]
        missing = ensure_keys(data, required)
        print_result(not missing, "stats keys", ",".join(missing))
        failures += 1 if missing else 0

    all_url = f"{base_url}/api/v1/data/all"
    status, data = fetch_json(all_url)
    if status != 200 or not isinstance(data, dict):
        print_result(False, "data all", f"status={status}")
        failures += 1
    else:
        required = ["orderbooks", "opportunities", "execution_summary", "timestamp"]
        missing = ensure_keys(data, required)
        print_result(not missing, "data all keys", ",".join(missing))
        failures += 1 if missing else 0

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Simple API check for ArbGUI or OpenAPI spec.")
    parser.add_argument("--base-url", default="http://0.0.0.0:8000", help="API base URL")
    parser.add_argument("--mode", choices=["arbgui", "openapi"], default="arbgui", help="Which contract to check")
    parser.add_argument("--exchange", default="bitbank", help="Exchange name to query")
    parser.add_argument("--symbol", default="XRP/JPY", help="Symbol to query (e.g., XRP/JPY)")
    args = parser.parse_args()

    if args.mode == "arbgui":
        failures = test_arbgui(args.base_url.rstrip("/"), args.exchange, args.symbol)
    else:
        failures = test_openapi(args.base_url.rstrip("/"), args.exchange, args.symbol)

    if failures:
        print(f"\nFAILED: {failures} check(s) failed.")
        return 1
    print("\nSUCCESS: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
