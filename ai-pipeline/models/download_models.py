"""
Download and cache models locally or on AWS (EFS/S3 path).
No Modal; uses MODEL_DIR from env (default ./models or /models). AWS-compatible.
Run on EC2/ECS with GPU if needed for SDXL/InstantID.
"""

from pathlib import Path
import os

# MODEL_DIR from env for AWS EFS or local
MODEL_DIR = os.environ.get("MODEL_DIR", "/models")


def download_base_models() -> None:
    """Download SDXL and InstantID models to MODEL_DIR (local/EFS)."""
    from diffusers import StableDiffusionXLPipeline  # type: ignore[reportMissingImports]
    from huggingface_hub import hf_hub_download  # type: ignore[reportMissingImports]
    import torch  # type: ignore[reportMissingImports]

    base = Path(MODEL_DIR)
    base.mkdir(parents=True, exist_ok=True)

    print("[*] Downloading SDXL Base Model...")
    hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
    if hf_token:
        print("[*] Using HuggingFace token for authenticated downloads")

    sdxl_path = base / "sdxl-base"
    if not sdxl_path.exists():
        pretrained_kwargs = {
            "torch_dtype": torch.float16,
            "variant": "fp16",
            "use_safetensors": True,
        }
        if hf_token:
            pretrained_kwargs["token"] = hf_token

        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0", **pretrained_kwargs
        )
        pipe.save_pretrained(str(sdxl_path))
        print("[OK] SDXL downloaded")
    else:
        print("[OK] SDXL already cached")

    print("[*] Downloading InstantID...")
    instantid_path = base / "instantid"
    instantid_path.mkdir(parents=True, exist_ok=True)

    files_to_download = [
        "ip-adapter.bin",
        "ControlNetModel/config.json",
        "ControlNetModel/diffusion_pytorch_model.safetensors",
    ]

    for file in files_to_download:
        local_path = instantid_path / file
        if not local_path.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            download_kwargs = {
                "repo_id": "InstantX/InstantID",
                "filename": file,
                "local_dir": str(instantid_path),
            }
            if hf_token:
                download_kwargs["token"] = hf_token
            hf_hub_download(**download_kwargs)

    print("[OK] InstantID downloaded")

    print("[*] Downloading InsightFace models...")
    insightface_path = base / "insightface"
    insightface_path.mkdir(parents=True, exist_ok=True)
    insightface_kwargs = {
        "repo_id": "public-data/insightface",
        "filename": "models/buffalo_l.zip",
        "local_dir": str(insightface_path),
    }
    if hf_token:
        insightface_kwargs["token"] = hf_token
    hf_hub_download(**insightface_kwargs)

    print("[OK] All models downloaded and cached!")


def main() -> None:
    """Entrypoint: run download to MODEL_DIR."""
    download_base_models()


if __name__ == "__main__":
    main()
