"""
Admin Configuration API - Control .env Feature Flags

Allows admins to view and update feature flags without SSH access.
Security: Add authentication in production (DEV_USER pattern for now).
"""
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["admin"])


# ── Configuration Schema ─────────────────────────────────────────────────────

class FeatureFlag(BaseModel):
    """Single feature flag configuration."""
    key: str
    value: str
    category: str
    description: str
    type: str = "boolean"  # "boolean", "string", "number"
    options: List[str] = Field(default_factory=list)  # For dropdown values


class ConfigResponse(BaseModel):
    """Configuration response with all feature flags."""
    flags: List[FeatureFlag]
    env_file_path: str
    last_modified: str = ""


class ConfigUpdateRequest(BaseModel):
    """Update multiple feature flags."""
    updates: Dict[str, str]


# ── Feature Flag Definitions ─────────────────────────────────────────────────

FEATURE_FLAGS = [
    # Core Architecture
    {
        "key": "USE_MASTER_STRATEGIST",
        "category": "Core Architecture",
        "description": "Consolidated Triage + Brand Intel + Creative Director (3→1 agent)",
        "type": "boolean",
        "default": "true",
    },
    {
        "key": "USE_CLAUDE_ENGINE",
        "category": "Core Architecture",
        "description": "Use Claude Haiku 4.5 for prompt engine (vs Gemini)",
        "type": "boolean",
        "default": "true",
    },
    {
        "key": "USE_BEAST_2026_ROUTER",
        "category": "Core Architecture",
        "description": "Predictive routing + Best-of-N generation",
        "type": "boolean",
        "default": "true",
    },

    # Cost Optimizations
    {
        "key": "USE_PROMPT_CACHING",
        "category": "Cost Optimization",
        "description": "Claude prompt caching (70-90% input token savings)",
        "type": "boolean",
        "default": "true",
    },
    {
        "key": "USE_SMART_CACHE",
        "category": "Cost Optimization",
        "description": "Semantic + exact match caching (20-30% queries FREE)",
        "type": "boolean",
        "default": "true",
    },
    {
        "key": "USE_LLMLINGUA_COMPRESSION",
        "category": "Cost Optimization",
        "description": "LLMLingua-2 prompt compression (50% token reduction)",
        "type": "boolean",
        "default": "true",
    },

    # BEAST Features
    {
        "key": "USE_SEMANTIC_JUDGE",
        "category": "BEAST Features",
        "description": "LLM-as-Judge for variant selection (cross-provider)",
        "type": "boolean",
        "default": "true",
    },
    {
        "key": "USE_ADAPTIVE_THINKING",
        "category": "BEAST Features",
        "description": "Dynamic thinking budget (1024-2000 tokens based on complexity)",
        "type": "boolean",
        "default": "true",
    },
    {
        "key": "BEAST_ROUTER_TYPE",
        "category": "BEAST Features",
        "description": "Router model selection",
        "type": "string",
        "options": ["gemini_lite", "gemini_flash", "claude_haiku"],
        "default": "gemini_lite",
    },
    {
        "key": "BEAST_COPY_WRITER_N",
        "category": "BEAST Features",
        "description": "Number of copy variants to generate (Best-of-N)",
        "type": "number",
        "options": ["1", "2", "3", "4", "5"],
        "default": "3",
    },
    {
        "key": "BEAST_JUDGE_CROSS_PROVIDER",
        "category": "BEAST Features",
        "description": "Use different LLM for judging (reduces bias)",
        "type": "boolean",
        "default": "true",
    },

    # Model Selection
    {
        "key": "USE_IDEOGRAM",
        "category": "Model Selection",
        "description": "Enable Ideogram v3 for typography bucket",
        "type": "boolean",
        "default": "true",
    },

    # Quality & Testing
    {
        "key": "USE_DETERMINISTIC_LAYOUT",
        "category": "Quality Features",
        "description": "Computer vision-based layout (vs LLM)",
        "type": "boolean",
        "default": "false",
    },
    {
        "key": "USE_HYBRID_QUALITY_CRITIC",
        "category": "Quality Features",
        "description": "Hybrid VLM + Python quality validation",
        "type": "boolean",
        "default": "false",
    },

    # Advanced
    {
        "key": "QUALITY_CRITIC_THRESHOLD",
        "category": "Advanced",
        "description": "Minimum quality score to approve (0-10)",
        "type": "number",
        "options": ["7.0", "7.5", "8.0", "8.5", "9.0"],
        "default": "8.5",
    },
    {
        "key": "QUALITY_CRITIC_PROVIDER",
        "category": "Advanced",
        "description": "Quality critic LLM provider",
        "type": "string",
        "options": ["gemini", "claude", "groq"],
        "default": "gemini",
    },
]


# ── Helper Functions ─────────────────────────────────────────────────────────

def _get_env_file_path() -> str:
    """Get path to .env file."""
    # Try multiple locations
    candidates = [
        "/home/ubuntu/PhotoGenius-AI/apps/api/.env",  # Production
        "c:/desktop/PhotoGenius AI/apps/api/.env",    # Local Windows
        "/c/desktop/PhotoGenius AI/apps/api/.env",    # Local Git Bash
        os.path.join(os.path.dirname(__file__), "../../../.env"),  # Relative
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    # Default to relative path
    return os.path.join(os.path.dirname(__file__), "../../../.env")


def _read_env_file() -> Dict[str, str]:
    """Read current .env file values."""
    env_path = _get_env_file_path()
    env_vars = {}

    if not os.path.exists(env_path):
        return env_vars

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception:
        pass

    return env_vars


def _write_env_file(env_vars: Dict[str, str]) -> None:
    """Write updated .env file."""
    env_path = _get_env_file_path()

    # Read existing file to preserve comments and order
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    # Update existing values
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in env_vars:
                new_lines.append(f"{key}={env_vars[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Add new keys that weren't in the file
    for key, value in env_vars.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    # Write back
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


# ── API Endpoints ────────────────────────────────────────────────────────────

@router.get("/admin/config", response_model=ConfigResponse)
async def get_config():
    """
    Get all feature flags and their current values.

    Returns current .env configuration for the admin panel.
    """
    current_env = _read_env_file()
    env_path = _get_env_file_path()

    # Build feature flags with current values
    flags = []
    for flag_def in FEATURE_FLAGS:
        current_value = current_env.get(flag_def["key"], flag_def["default"])

        flags.append(FeatureFlag(
            key=flag_def["key"],
            value=current_value,
            category=flag_def["category"],
            description=flag_def["description"],
            type=flag_def["type"],
            options=flag_def.get("options", []),
        ))

    # Get last modified time
    last_modified = ""
    if os.path.exists(env_path):
        import datetime
        mtime = os.path.getmtime(env_path)
        last_modified = datetime.datetime.fromtimestamp(mtime).isoformat()

    return ConfigResponse(
        flags=flags,
        env_file_path=env_path,
        last_modified=last_modified,
    )


@router.post("/admin/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update feature flags in .env file.

    Body:
        {
            "updates": {
                "USE_MASTER_STRATEGIST": "true",
                "BEAST_COPY_WRITER_N": "3",
                ...
            }
        }

    Returns:
        Updated configuration

    Note: Requires API restart (pm2 restart) to take effect.
    """
    # Validate all keys are known feature flags
    valid_keys = {flag["key"] for flag in FEATURE_FLAGS}
    invalid_keys = set(request.updates.keys()) - valid_keys

    if invalid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration keys: {', '.join(invalid_keys)}"
        )

    # Read current .env
    current_env = _read_env_file()

    # Apply updates
    current_env.update(request.updates)

    # Write back
    try:
        _write_env_file(current_env)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update .env file: {str(e)}"
        )

    return {
        "success": True,
        "message": f"Updated {len(request.updates)} configuration values",
        "updates": request.updates,
        "note": "⚠️ Restart API (pm2 restart photogenius-api) for changes to take effect"
    }


@router.post("/admin/config/restart")
async def restart_api():
    """
    Restart the API to apply configuration changes.

    Executes: pm2 restart photogenius-api

    Security: Only works on production server with pm2 installed.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["pm2", "restart", "photogenius-api"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return {
                "success": True,
                "message": "API restarted successfully",
                "output": result.stdout,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"pm2 restart failed: {result.stderr}"
            )

    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="pm2 not installed on this server"
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail="pm2 restart timed out"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart API: {str(e)}"
        )
