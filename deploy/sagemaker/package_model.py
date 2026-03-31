"""
Package PhotoGenius AI for SageMaker deployment.

Creates a model.tar.gz with:
- All service modules (ai-pipeline/services)
- Inference script (model_fn, input_fn, predict_fn, output_fn)
- Dependencies (requirements.txt)
- Deployment config (config.json)

Run from repo root: python deploy/sagemaker/package_model.py
"""

from __future__ import annotations

import json
import os
import shutil
import tarfile
from pathlib import Path

# Repo root: deploy/sagemaker/package_model.py -> parent.parent = deploy -> parent = repo root
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent


def package_for_sagemaker(output_dir: str | None = None) -> str:
    """
    Package complete system for SageMaker deployment.

    Creates:
    - model.tar.gz: Complete model package (inference.py, services/, requirements.txt, config.json)
    - All under deploy/sagemaker/artifacts/ by default

    Returns:
        Path to the created model.tar.gz
    """
    if output_dir is None:
        output_dir = str(SCRIPT_DIR / "artifacts")
    print("Packaging PhotoGenius AI for SageMaker...\n")
    print(f"   Root: {ROOT}")
    print(f"   Output: {output_dir}\n")

    os.makedirs(output_dir, exist_ok=True)
    staging_dir = os.path.join(output_dir, "staging")
    if os.path.isdir(staging_dir):
        shutil.rmtree(staging_dir)
    os.makedirs(staging_dir, exist_ok=True)

    # 1. Copy service modules (from ai-pipeline/services)
    services_src = ROOT / "ai-pipeline" / "services"
    services_dst = os.path.join(staging_dir, "services")
    if services_src.is_dir():
        print("1. Copying service modules...")
        shutil.copytree(str(services_src), services_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
        print(f"   [OK] Copied services to {services_dst}")
    else:
        print(f"1. WARNING: {services_src} not found; inference will use fallback only.")
        os.makedirs(services_dst, exist_ok=True)
        with open(os.path.join(services_dst, "__init__.py"), "w") as f:
            f.write("# Placeholder\n")

    # 2. Create inference script
    print("\n2. Creating inference script...")
    _create_inference_script(staging_dir)
    print("   [OK] Created inference.py")

    # 3. Create requirements file
    print("\n3. Creating requirements.txt...")
    _create_requirements_file(staging_dir)
    print("   [OK] Created requirements.txt")

    # 4. Create config file
    print("\n4. Creating deployment config...")
    _create_deployment_config(staging_dir)
    print("   [OK] Created config.json")

    # 5. Create tarball (root of tar = contents of staging so inference.py is at top level)
    print("\n5. Creating model.tar.gz...")
    tar_path = os.path.join(output_dir, "model.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(staging_dir, arcname=".")
    print(f"   [OK] Created {tar_path}")

    # 6. Clean up staging
    shutil.rmtree(staging_dir)

    size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print("\nPackaging complete!")
    print(f"   Package: {tar_path}")
    print(f"   Size: {size_mb:.1f} MB")
    print("\nNext: Upload to S3 and deploy with deploy/sagemaker/upload_and_deploy.py\n")
    return tar_path


def _create_inference_script(staging_dir: str) -> None:
    """Create SageMaker inference handler with tier support and fallbacks."""
    inference_script = '''"""
SageMaker Inference Handler for PhotoGenius AI.

Handles: model loading, request parsing, generation, response formatting.
Tiers: STANDARD (fast), PREMIUM (balanced), PERFECT (best quality).
"""

import json
import os
import sys
from io import BytesIO
import base64

# Add current dir for services
if __name__ == "__main__":
    pass  # SageMaker runs this as script
_model_dir = os.environ.get("SM_MODEL_DIR", os.path.dirname(os.path.abspath(__file__)))
if _model_dir not in sys.path:
    sys.path.insert(0, _model_dir)

# Global model state
_refinement_engine = None
_si_engine = None
_tier_config = None
_tier_name = "STANDARD"
_use_fallback = False


def _load_fallback():
    """Light fallback when full pipeline is not available (e.g. missing heavy deps)."""
    global _use_fallback
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    _use_fallback = True
    return {"Image": Image, "np": np}


def model_fn(model_dir):
    """
    Load model and initialize engines. Called once when SageMaker endpoint starts.
    """
    global _refinement_engine, _si_engine, _tier_config, _tier_name
    print("Loading PhotoGenius AI models...")
    tier = os.environ.get("PHOTOGENIUS_TIER", "STANDARD")
    _tier_name = tier
    tier_configs = {
        "STANDARD": {
            "max_iterations": 2,
            "quality_threshold": 0.75,
            "use_reward_guidance": False,
            "num_inference_steps": 30,
        },
        "PREMIUM": {
            "max_iterations": 3,
            "quality_threshold": 0.85,
            "use_reward_guidance": True,
            "num_inference_steps": 40,
        },
        "PERFECT": {
            "max_iterations": 5,
            "quality_threshold": 0.90,
            "use_reward_guidance": True,
            "num_inference_steps": 50,
        },
    }
    _tier_config = tier_configs.get(tier, tier_configs["STANDARD"])
    print(f"   Tier: {tier}, config: {_tier_config}")

    fallback = _load_fallback()
    try:
        from services.iterative_refinement_engine import IterativeRefinementEngine
        from services.self_improvement_engine import SelfImprovementEngine
        from services.physics_micro_simulation import EnvironmentalCondition, create_rainy_environment, create_fantasy_environment

        _refinement_engine = IterativeRefinementEngine(
            device="cuda",
            use_reward_guidance=_tier_config["use_reward_guidance"],
            max_iterations=_tier_config["max_iterations"],
            quality_threshold=_tier_config["quality_threshold"],
        )
        memory_dir = os.path.join(model_dir, "memory")
        os.makedirs(memory_dir, exist_ok=True)
        _si_engine = SelfImprovementEngine(storage_dir=memory_dir)
        print("   Full pipeline loaded (SelfImprovement + IterativeRefinement)")
    except Exception as e:
        print(f"   Full pipeline unavailable: {e}")
        _refinement_engine = None
        _si_engine = None
        if not fallback:
            raise RuntimeError("No inference backend available. Install services deps or use fallback.") from e

    return {
        "refinement_engine": _refinement_engine,
        "si_engine": _si_engine,
        "tier": tier,
        "config": _tier_config,
        "fallback": fallback,
    }


def input_fn(request_body, request_content_type):
    """Parse input request. Expects application/json."""
    if request_content_type != "application/json":
        raise ValueError(f"Unsupported content type: {request_content_type}")
    return json.loads(request_body)


def predict_fn(input_data, model):
    """Generate image from prompt."""
    global _tier_config
    prompt = input_data.get("prompt") or ""
    environment_type = input_data.get("environment", "normal")
    seed = input_data.get("seed")
    max_iterations = input_data.get("max_iterations") or (_tier_config or {}).get("max_iterations", 3)

    if model.get("si_engine") and model.get("refinement_engine"):
        try:
            from services.physics_micro_simulation import (
                EnvironmentalCondition,
                create_rainy_environment,
                create_fantasy_environment,
            )
            if environment_type == "rainy":
                environment = create_rainy_environment(0.8)
            elif environment_type == "fantasy":
                environment = create_fantasy_environment()
            else:
                environment = EnvironmentalCondition(
                    weather="none", intensity=0.0, temperature=20, wind_speed=0, lighting="day"
                )
            result = model["si_engine"].generate_with_learning(
                model["refinement_engine"],
                prompt,
                environment=environment,
                max_iterations=max_iterations,
                seed=seed,
                save_iterations=False,
            )
            return result
        except Exception as e:
            print(f"Full pipeline error: {e}")
            pass

    # Fallback: return placeholder result so endpoint responds
    fallback = model.get("fallback")
    if fallback:
        Image = fallback["Image"]
        np = fallback["np"]
        w, h = 512, 512
        arr = np.zeros((h, w, 3), dtype=np.uint8)
        arr[:] = [40, 44, 52]  # dark gray
        img = Image.fromarray(arr)
        return {
            "image": img,
            "final_score": 0.0,
            "total_iterations": 0,
            "success": False,
            "metadata": {"prompt": prompt, "fallback": True},
            "self_improvement": {},
        }
    raise RuntimeError("No inference backend available.")


def output_fn(prediction, response_content_type):
    """Format output as JSON with base64 image and metadata."""
    if response_content_type != "application/json":
        raise ValueError(f"Unsupported response content type: {response_content_type}")
    image = prediction.get("image")
    img_base64 = ""
    if image is not None:
        try:
            from PIL import Image
            if not isinstance(image, Image.Image):
                from PIL import Image as PILImage
                image = PILImage.fromarray(image)
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            print(f"Image encode error: {e}")
    meta = prediction.get("metadata") or {}
    response = {
        "image": img_base64,
        "metadata": {
            "final_score": prediction.get("final_score", 0.0),
            "total_iterations": prediction.get("total_iterations", 0),
            "success": prediction.get("success", False),
            "prompt": meta.get("prompt", ""),
        },
        "self_improvement": prediction.get("self_improvement", {}),
    }
    return json.dumps(response)
'''
    with open(os.path.join(staging_dir, "inference.py"), "w", encoding="utf-8") as f:
        f.write(inference_script)


def _create_requirements_file(staging_dir: str) -> None:
    """Create requirements.txt for the container."""
    requirements = """
torch>=2.0.0
torchvision>=0.15.0
diffusers>=0.25.0
transformers>=4.35.0
accelerate>=0.24.0
pillow>=10.0.0
numpy>=1.24.0
scipy>=1.10.0
scikit-learn>=1.3.0
networkx>=3.0
"""
    with open(os.path.join(staging_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(requirements.strip() + "\n")


def _create_deployment_config(staging_dir: str) -> None:
    """Create deployment configuration (tiers, scaling, cost)."""
    config = {
        "model_name": "photogenius-ai",
        "version": "1.0.0",
        "tiers": {
            "STANDARD": {
                "instance_type": "ml.g5.xlarge",
                "description": "Fast generation, ~85% quality",
                "max_iterations": 2,
                "cost_per_hour": 1.006,
            },
            "PREMIUM": {
                "instance_type": "ml.g5.2xlarge",
                "description": "Balanced quality, ~90% success",
                "max_iterations": 3,
                "cost_per_hour": 1.212,
            },
            "PERFECT": {
                "instance_type": "ml.g5.4xlarge",
                "description": "Best quality, ~99% success",
                "max_iterations": 5,
                "cost_per_hour": 1.624,
            },
        },
        "auto_scaling": {
            "min_instances": 1,
            "max_instances": 10,
            "target_invocations_per_instance": 100,
        },
    }
    with open(os.path.join(staging_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    package_for_sagemaker()
