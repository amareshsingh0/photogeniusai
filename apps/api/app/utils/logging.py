"""Structured logging. Configure level via LOG_LEVEL env."""

import logging
import os
import sys

_level = getattr(logging, (os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO)
logging.basicConfig(level=_level, format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stdout)
log = logging.getLogger("photogenius")
