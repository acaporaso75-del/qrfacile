#!/usr/bin/env python3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qrfacile_app.services.transactional_email import load_smtp_config


def main() -> int:
    config = load_smtp_config()
    if config is None:
        print("TRANSACTIONAL_EMAIL_CONFIG_ERROR missing_or_invalid_configuration")
        return 2
    print(f"TRANSACTIONAL_EMAIL_CONFIG_OK transport={config.transport} port={config.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
