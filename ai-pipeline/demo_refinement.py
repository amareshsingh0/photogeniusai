"""
Demo script for iterative refinement.

Usage:
    python demo_refinement.py "Mother with 3 children under umbrella in rain"

Run from ai-pipeline directory:
    cd ai-pipeline && python demo_refinement.py "Couple walking at sunset"
"""

import os
import sys

# Allow running from repo root or ai-pipeline
if __name__ == "__main__" and os.path.basename(os.getcwd()) != "ai-pipeline":
    _ai_pipeline = os.path.join(os.path.dirname(__file__) or ".", "ai-pipeline")
    if os.path.isdir(_ai_pipeline):
        os.chdir(_ai_pipeline)
    elif os.path.exists("services/iterative_refinement_engine.py"):
        pass  # already in ai-pipeline
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services.iterative_refinement_engine import IterativeRefinementEngine
except ImportError:
    from ai_pipeline.services.iterative_refinement_engine import IterativeRefinementEngine

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


def _save_image(img, path: str) -> bool:
    """Save image (PIL or numpy) to path. Returns True if saved."""
    if img is None:
        return False
    try:
        if hasattr(img, "save"):
            img.save(path)
            return True
        if PILImage is not None and hasattr(img, "shape"):
            PILImage.fromarray(img).save(path)
            return True
    except Exception as e:
        print(f"  Warning: could not save {path}: {e}")
    return False


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python demo_refinement.py '<prompt>'")
        print("\nExample prompts:")
        print("  - 'Mother with 3 children under umbrella in rain'")
        print("  - 'Couple walking at sunset'")
        print("  - 'Dragon flying over crystal city'")
        sys.exit(1)

    prompt = sys.argv[1]

    print(f"\n{'='*70}")
    print("PHOTOGENIUS AI - ITERATIVE REFINEMENT DEMO")
    print(f"{'='*70}\n")

    # Prefer CUDA if available
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"
    print(f"Using device: {device}\n")

    print("Loading refinement engine (this may take a minute)...\n")
    engine = IterativeRefinementEngine(
        device=device,
        use_reward_guidance=True,
        max_iterations=3,
        quality_threshold=0.85,
        use_models=(device == "cuda"),
    )

    result = engine.generate_perfect(
        prompt=prompt,
        max_iterations=3,
        save_iterations=True,
        seed=42,
    )

    output_dir = "outputs/refinement_demo"
    os.makedirs(output_dir, exist_ok=True)

    # Save final image
    final_img = result.get("image")
    final_path = os.path.join(output_dir, "final.png")
    if final_img is not None and _save_image(final_img, final_path):
        print(f"\nSaved final image: {final_path}")
    else:
        print("\nNo final image to save (pipeline may be in placeholder mode).")

    # Save iteration images
    for i, iteration in enumerate(result.get("iterations", [])):
        iter_img = getattr(iteration, "image", None)
        score = getattr(iteration, "validation_score", 0.0)
        iter_path = os.path.join(
            output_dir,
            f"iteration_{i+1}_score_{score:.3f}.png",
        )
        if iter_img is not None and _save_image(iter_img, iter_path):
            print(f"Saved iteration {i+1}: {iter_path}")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Prompt: {prompt}")
    success = result.get("success", False)
    print(f"Success: {'YES' if success else 'NO'}")
    print(f"Final Score: {result.get('final_score', 0):.3f}")
    print(f"Iterations: {result.get('total_iterations', 0)}")
    meta = result.get("metadata") or {}
    avg_time = meta.get("avg_iteration_time", 0.0)
    print(f"Average time per iteration: {avg_time:.1f}s")
    print("\nScore progression:")
    for i, iteration in enumerate(result.get("iterations", [])):
        score = getattr(iteration, "validation_score", 0.0)
        valid = getattr(iteration, "is_valid", False)
        print(f"  Iteration {i+1}: {score:.3f}  {'PASS' if valid else 'FAIL'}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
