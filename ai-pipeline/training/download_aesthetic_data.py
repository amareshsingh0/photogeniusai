"""
Download aesthetic training data for AestheticPredictor.

Datasets:
- LAION-Aesthetics subset (100k images with scores)
- AVA (manual download instructions only)

Run:
    modal run ai-pipeline/training/download_aesthetic_data.py
"""

import modal

app = modal.App("download-aesthetic-data")

volume = modal.Volume.from_name("aesthetic-dataset", create_if_missing=True)


@app.function(
    volumes={"/data": volume},
    timeout=7200,
    image=modal.Image.debian_slim(python_version="3.11").pip_install(
        [
            "datasets",
            "huggingface_hub",
            "tqdm",
            "pillow",
            "requests",
        ]
    ),
)
def download_datasets():
    """Download LAION-Aesthetics subset into /data/laion; print AVA instructions."""
    from datasets import load_dataset
    from huggingface_hub import snapshot_download  # noqa: F401
    from tqdm import tqdm
    from PIL import Image
    import json
    import os
    import requests
    from io import BytesIO

    os.makedirs("/data/laion", exist_ok=True)

    print("📥 Downloading aesthetic datasets...")

    # 1. LAION-Aesthetics V2 (filtered high-quality)
    print("\n1. Downloading LAION-Aesthetics subset...")
    dataset = load_dataset(
        "ChristophSchuhmann/improved_aesthetics_6plus",
        split="train",
        streaming=True,
    )

    counter = 0
    max_images = 100000  # 100k subset

    for item in tqdm(dataset, desc="LAION-Aesthetics", total=max_images):
        if counter >= max_images:
            break

        url = item.get("URL")
        caption = item.get("TEXT")
        score = item.get("aesthetic_score")

        if not url or score is None:
            continue

        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGB")

            img_path = f"/data/laion/{counter:06d}.jpg"
            meta_path = f"/data/laion/{counter:06d}.json"

            img.save(img_path, "JPEG", quality=90)

            metadata = {
                "url": url,
                "caption": caption,
                "aesthetic_score": float(score),
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False)

            counter += 1

            if counter % 1000 == 0:
                print(f"  Downloaded {counter}/{max_images} images")
                volume.commit()

        except Exception:
            # Skip failed downloads silently
            continue

    print(f"✅ LAION-Aesthetics complete: {counter} images saved in /data/laion")

    # 2. AVA Dataset (manual)
    print("\n2. AVA dataset (manual download required)")
    print("⚠️  AVA requires academic access.")
    print("   Download instructions: http://academictorrents.com/details/71631f83b11d3d79d8f84efe0a7e12f0ac001460")
    print("   After download, place AVA files under /data/ava/")

    volume.commit()

    return {
        "laion_images": counter,
        "ava_status": "manual_download_required",
    }


@app.local_entrypoint()
def main():
    """CLI entrypoint: download datasets via Modal."""
    result = download_datasets.remote()
    print(f"\n✅ Download complete: {result}")

