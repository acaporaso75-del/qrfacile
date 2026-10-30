from __future__ import annotations

import os


# The application defaults to production when no environment is declared.
# Tests must opt into their non-production runtime before importing app modules.
os.environ.setdefault("APP_ENV", "test")
