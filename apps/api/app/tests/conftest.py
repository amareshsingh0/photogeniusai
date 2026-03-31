"""
Pytest configuration for app tests.

Adds apps/api to Python path so imports work correctly.
"""

import sys
from pathlib import Path

# Add apps/api to Python path
api_dir = Path(__file__).resolve().parent.parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))
