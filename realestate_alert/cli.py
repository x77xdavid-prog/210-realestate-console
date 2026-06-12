from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from realestate_alert.config import load_config
from realestate_alert.finance import PurchaseEstimateInput, estimate_purchase
from realestate_alert.filtering import matches_listing
from realestate_alert.registry import analyze_registry_file, export_registry_targets
from realestate_alert.service import run_once
from realestate_alert.sources import JsonFileSource
from realestate_alert.store import ListingStore
from realestate_alert.verify import verify_address
from realestate_alert.web_server import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="realestate-alert")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db")
    init_db.add_argument("--config", required=True)

    run_once_parser = subparsers.add_parser("run-once")
    run_once_parser.add_argument("--config", required=True)

    watch = subparsers.add_parser("watch")
    watch.add_argument("--config", required=True)

    serve_web = subparsers.add_parser("serve-web")
    serve_web.add_argument("--config", required=True)
    serve_web.add_argument("--host", default="127.0.0.1")
    serve_web.add_argument("--port", type=int, default=8765)
    serve_web.add_argument("--web-root", default="web")

    registry_targets = subparsers.add_parser("export-registry-targets")
    registry_targets.add_argument("--config", required=True)
    registry_targets.add_argument("--output", default="data/registry-targets.csv")

    analyze_registry = subparsers.add_parser("analyze-registry")
    analyze_registry.add_argument("--file", required=True)

    verify_addr = subparsers.add_parser("verify-address")
    verify_addr.add_argument("--address", required=True)
    verify_addr.add_argument("--months", type=int, default=6)

    estimate = subparsers.add_parser("estimate-purchase")
    estimate.add_argument("--purchase-price", type=int, required=True)
    estimate.add_argument("--loan-amount", type=int, required=True)
    estimate.add_argument("--cash-available", type=int, required=True)
    estimate.add_argument("--acquisition-tax-rate", type=float, required=True)
    estimate.add_argument("--brokerage-rate", type=float, required=True)
    estimate.add_argument("--legal-fee", type=int, default=0)
    estimate.add_argument("--other-costs", type=int, default=0)

    args = parser.parse_args(argv)
    if args.command == "init-db":
        config = load_config(Path(args.config))
        ListingStore(config.database_path).initialize()
        print(f"DB initialized: {config.database_path}")
        return 0
    if args.command == "run-once":
        config = load_config(Path(args.config))
        result = run_once(config)
        print(f"fetched={result.fetched_count} matched={result.matched_count} notified={len(result.notified)}")
        return 0
    if args.command == "watch":
        config = load_config(Path(args.config))
        while True:
            result = run_once(config)
            print(f"fetched={result.fetched_count} matched={result.matched_count} notified={len(result.notified)}")
            time.sleep(config.interval_seconds)
    if args.command == "serve-web":
        serve(
            config_path=Path(args.config),
            web_root=Path(args.web_root),
            host=args.host,
            port=args.port,
        )
        return 0
    if args.command == "export-registry-targets":
        config = load_config(Path(args.config))
        listings = []
        for source_config in config.sources:
            if source_config.type != "json_file" or source_config.path is None:
                continue
            listings.extend(JsonFileSource(source_config.path).fetch())
        matched = [listing for listing in listings if matches_listing(config.criteria, listing)]
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = Path(args.config).parent / output_path
        export_registry_targets(matched, output_path)
        print(f"exported={len(matched)} path={output_path}")
        return 0
    if args.command == "analyze-registry":
        result = analyze_registry_file(Path(args.file))
        print(json.dumps(_registry_result_to_dict(result), ensure_ascii=False, indent=2))
        return 0
    if args.command == "verify-address":
        report = verify_address(args.address, market_months=args.months)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "estimate-purchase":
        result = estimate_purchase(
            PurchaseEstimateInput(
                purchase_price=args.purchase_price,
                loan_amount=args.loan_amount,
                cash_available=args.cash_available,
                acquisition_tax_rate=args.acquisition_tax_rate,
                brokerage_rate=args.brokerage_rate,
                legal_fee=args.legal_fee,
                other_costs=args.other_costs,
            )
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0
    return 1


def _registry_result_to_dict(result) -> dict:
    return {
        "status": result.status.value,
        "owner_names": result.owner_names,
        "risk_keywords": result.risk_keywords,
    }
