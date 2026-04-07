"""
Configuration JSON loader utilities.

Usage:
    from app.config import load_beast_standards, load_aesthetic_codes

    standards = load_beast_standards()
    aesthetics = load_aesthetic_codes()
"""
import json
import os
from pathlib import Path
from typing import Dict, List

_CONFIG_DIR = Path(__file__).parent


def load_json_config(filename: str) -> Dict:
    """Load JSON config file from config directory."""
    filepath = _CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# Lazy loaders for each config file
def load_beast_standards() -> Dict:
    """Load 10 Beast Standard gates configuration."""
    return load_json_config('beast_standards.json')


def load_aesthetic_codes() -> Dict:
    """Load 8 Aesthetic zeitgeist codes (2026-Q2)."""
    return load_json_config('aesthetic_codes.json')


def load_platform_contracts() -> Dict:
    """Load platform-specific rules (Instagram, TikTok, etc.)."""
    return load_json_config('platform_contracts.json')


def load_generational_signals() -> Dict:
    """Load generational signals (Gen Z, Millennials, etc.)."""
    return load_json_config('generational_signals.json')


def load_composition_archetypes() -> Dict:
    """Load 7 composition archetypes."""
    return load_json_config('composition_archetypes.json')


def load_type_scales() -> Dict:
    """Load 5 type scale configurations."""
    return load_json_config('type_scales.json')


def load_quality_dimensions() -> Dict:
    """Load 12 quality dimension weights."""
    return load_json_config('quality_dimensions.json')
