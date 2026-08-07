from __future__ import annotations

import argparse
import json

from qrfacile_app.services.wine_knowledge_registry import load_wine_knowledge_registry
from qrfacile_app.services.wine_rule_catalog import load_wine_rule_catalog
from qrfacile_app.services.wine_rule_validator import validate_wine_rule_catalog


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m qrfacile_app.rules")
    parser.add_argument("command", choices=("validate",))
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    catalog = load_wine_rule_catalog()
    knowledge = load_wine_knowledge_registry()
    report = validate_wine_rule_catalog(catalog, knowledge)

    if args.as_json:
        payload = {
            "catalog_version": catalog.version,
            "knowledge_version": knowledge.version,
            **report.to_dict(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Catalog Version: {catalog.version}")
        print(f"Knowledge Version: {knowledge.version}")
        print(f"Rules: {report.rule_count}")
        print(f"Active: {report.active_rule_count}")
        print(f"Blocking: {report.blocking_rule_count}")
        print(f"Dependencies: {'OK' if not any(i.code.startswith('dependency') or i.code in {'unknown_dependency', 'self_dependency', 'duplicate_dependency'} for i in report.issues) else 'ERROR'}")
        print(f"Knowledge Links: {'OK' if not any('knowledge' in i.code for i in report.issues) else 'ERROR'}")
        print(f"Weights: {'OK' if not any(i.code in {'missing_weight', 'negative_weight', 'pass_weight', 'weight_order'} for i in report.issues) else 'ERROR'}")
        print(f"Status: {'READY' if report.ready else 'INVALID'}")
        for issue in report.issues:
            target = f" [{issue.rule_id}]" if issue.rule_id else ""
            print(f"- {issue.code}{target}: {issue.message}")

    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
