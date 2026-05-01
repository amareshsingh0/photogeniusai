"""
Empirical prompt harness for Wan 2.7 and Flux 2 Flex ad variants.

This script is not part of the production request path. It generates one image
per prompt variant and writes a comparison HTML file under scripts/output.

Usage:
    python scripts/test_specialized_models.py
    python scripts/test_specialized_models.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


from app.services.smart.model_prompt_formatter import format_prompt_for_model  # noqa: E402
from app.services.smart.simple_prompt_engine import _ANTI_COLLAGE_NEGATIVES  # noqa: E402


SIMPLE_PAYLOAD: Dict[str, Any] = {
    "intent": "face powder launch",
    "campaign_type": "product_launch",
    "subject_category": "beauty",
    "aspect_hint": "portrait_4_3",
    "prompt": (
        "A premium beauty advertisement for myPowder face powder. Warm cream "
        "studio background, rose-gold compact open on the right with soft "
        "powder dust, large bold text at the top, elegant beauty lighting, "
        "premium commercial photography."
    ),
    "negative_prompt": _ANTI_COLLAGE_NEGATIVES,
    "ad_copy": {
        "brand_name": "myPowder",
        "headline": "LIGHT AS AIR",
        "subhead": "Flawless Everywhere",
        "cta": "Available Now",
        "benefit_lines": ["Lightweight", "Oil Control", "Long Lasting", "Blurs Skin"],
        "trust_signals": ["Vegan", "Dermatologically Tested", "Suits All Skin Types", "Made With Care"],
        "emotional_tagline": "Soft focus confidence for every day.",
    },
    "visual": {
        "mood": "minimalist, elegant, premium",
        "color_palette": "warm cream, rose-gold, soft ivory, muted taupe",
        "lighting": "soft beauty lighting with gentle highlights",
        "background": "a warm cream studio surface with subtle rose-gold reflections",
        "composition": "product on the right, text hierarchy on the left, clear bottom action area",
        "typography_style": "bold condensed uppercase headline with elegant italic accent text",
    },
}


BASE_PROMPT = (
    "ONE single unified image. "
    + SIMPLE_PAYLOAD["prompt"]
)


@dataclass(frozen=True)
class Variant:
    key: str
    model_key: str
    prompt: str
    notes: str


def _quoted_list_prompt(prefix: str) -> str:
    ad_copy = SIMPLE_PAYLOAD["ad_copy"]
    labels = [
        ad_copy["brand_name"],
        ad_copy["headline"],
        ad_copy["subhead"],
        ad_copy["cta"],
        *ad_copy["benefit_lines"],
        *ad_copy["trust_signals"],
    ]
    quoted = ", ".join(f'"{item}"' for item in labels if item)
    return (
        f"{prefix} {SIMPLE_PAYLOAD['prompt']} "
        "Render these exact visible text strings if the model supports text: "
        f"{quoted}. Keep a single polished advertising composition."
    )


def build_variants() -> List[Variant]:
    imagen_narrative = format_prompt_for_model(
        base_prompt=BASE_PROMPT,
        model_key="imagen_4_base",
        simple_payload=SIMPLE_PAYLOAD,
    )
    return [
        Variant(
            key="wan_2_7_current",
            model_key="wan_2_7",
            prompt=format_prompt_for_model(BASE_PROMPT, "wan_2_7", SIMPLE_PAYLOAD),
            notes="Current WaveSpeed formatter.",
        ),
        Variant(
            key="wan_2_7_imagine_prefix",
            model_key="wan_2_7",
            prompt="/imagine prompt: Highly detailed, commercial photography style. " + imagen_narrative,
            notes="Research starting template with descriptive narrative.",
        ),
        Variant(
            key="wan_2_7_quoted_list",
            model_key="wan_2_7",
            prompt=_quoted_list_prompt("Highly detailed commercial beauty advertisement."),
            notes="Quoted-string-list text stress test.",
        ),
        Variant(
            key="flux_2_flex_current",
            model_key="flux_2_flex",
            prompt=format_prompt_for_model(BASE_PROMPT, "flux_2_flex", SIMPLE_PAYLOAD),
            notes="Current Flux formatter.",
        ),
        Variant(
            key="flux_2_flex_imagine_prefix",
            model_key="flux_2_flex",
            prompt="/imagine prompt: Highly detailed, commercial photography style. " + imagen_narrative,
            notes="Research starting template with descriptive narrative.",
        ),
        Variant(
            key="flux_2_flex_quoted_list",
            model_key="flux_2_flex",
            prompt=_quoted_list_prompt("Premium commercial photography style."),
            notes="Quoted-string-list text stress test.",
        ),
        Variant(
            key="gpt_image_2_control",
            model_key="gpt_image_2",
            prompt=format_prompt_for_model(BASE_PROMPT, "gpt_image_2", SIMPLE_PAYLOAD),
            notes="GPT Image 2 control using sectioned imperative formatter.",
        ),
    ]


async def _generate_variant(variant: Variant, dry_run: bool) -> Dict[str, Any]:
    started = time.time()
    result: Dict[str, Any] = {
        "key": variant.key,
        "model_key": variant.model_key,
        "prompt": variant.prompt,
        "notes": variant.notes,
        "image_url": None,
        "success": False,
        "error": None,
        "latency_sec": 0.0,
    }
    if dry_run:
        result["success"] = True
        result["latency_sec"] = 0.0
        return result

    try:
        from app.services.external.multi_provider_client import multi_client

        gen = await multi_client.generate(
            model_key=variant.model_key,
            prompt=variant.prompt,
            negative_prompt=SIMPLE_PAYLOAD["negative_prompt"],
            num_images=1,
            image_size="portrait_4_3",
            num_inference_steps=20,
            guidance_scale=3.5,
        )
        result["success"] = bool(gen.get("success"))
        result["image_url"] = gen.get("image_url")
        result["error"] = gen.get("error") or gen.get("metadata", {}).get("error")
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        result["latency_sec"] = round(time.time() - started, 3)
    return result


def _write_html(results: List[Dict[str, Any]], output_dir: Path, dry_run: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"specialized_models_{stamp}.html"
    cards = []
    for item in results:
        image_url = item.get("image_url")
        image_html = (
            f'<img src="{html.escape(image_url)}" alt="{html.escape(item["key"])}" />'
            if image_url
            else '<div class="placeholder">No image generated</div>'
        )
        cards.append(
            f"""
            <section class="card">
              <h2>{html.escape(item["key"])}</h2>
              <p class="meta">{html.escape(item["model_key"])} | {item["latency_sec"]}s</p>
              <p>{html.escape(item["notes"])}</p>
              {image_html}
              <details>
                <summary>Prompt</summary>
                <pre>{html.escape(item["prompt"])}</pre>
              </details>
              <pre class="status">{html.escape(json.dumps({"success": item["success"], "error": item["error"]}, indent=2))}</pre>
            </section>
            """
        )
    body = "\n".join(cards)
    mode = "dry run" if dry_run else "live generation"
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wan and Flux Prompt Harness</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #111; color: #eee; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
    h1 {{ font-size: 24px; margin: 0 0 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
    .card {{ border: 1px solid #333; background: #181818; border-radius: 8px; padding: 14px; }}
    .card h2 {{ margin: 0 0 4px; font-size: 16px; }}
    .meta {{ color: #aaa; font-size: 12px; }}
    img, .placeholder {{ width: 100%; aspect-ratio: 3 / 4; object-fit: cover; background: #242424; border-radius: 6px; }}
    .placeholder {{ display: grid; place-items: center; color: #888; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; background: #0d0d0d; padding: 10px; border-radius: 6px; }}
    summary {{ cursor: pointer; margin: 10px 0; }}
  </style>
</head>
<body>
  <main>
    <h1>Wan 2.7 / Flux 2 Flex Prompt Harness</h1>
    <p class="meta">Mode: {html.escape(mode)}. One image per variant.</p>
    <div class="grid">{body}</div>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


async def async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Write prompts to HTML without provider calls.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of variants for quick smoke tests.")
    parser.add_argument(
        "--output-dir",
        default=str(API_ROOT / "scripts" / "output"),
        help="Directory for comparison HTML.",
    )
    args = parser.parse_args()

    variants = build_variants()
    if args.limit and args.limit > 0:
        variants = variants[: args.limit]

    results = []
    for variant in variants:
        print(f"[harness] running {variant.key} on {variant.model_key}", flush=True)
        results.append(await _generate_variant(variant, dry_run=args.dry_run))

    output_path = _write_html(results, Path(args.output_dir), dry_run=args.dry_run)
    print(f"[harness] wrote {output_path}", flush=True)
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
