"""
Demo: Self-Improvement Engine

Shows how the system learns from experiences.

Usage:
    python demo_self_improvement.py
    python demo_self_improvement.py "Single prompt here"

Run from ai-pipeline directory:
    cd ai-pipeline && python demo_self_improvement.py
"""

import os
import sys

if __name__ == "__main__":
    if os.path.basename(os.getcwd()) != "ai-pipeline":
        _base = os.path.dirname(os.path.abspath(__file__))
        if os.path.isdir(_base):
            _ai = os.path.join(_base, "ai-pipeline")
            if os.path.isdir(_ai):
                os.chdir(_ai)
        if not os.path.exists("services/self_improvement_engine.py"):
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from services.self_improvement_engine import SelfImprovementEngine
    from services.iterative_refinement_engine import IterativeRefinementEngine
except ImportError:
    from ai_pipeline.services.self_improvement_engine import SelfImprovementEngine
    from ai_pipeline.services.iterative_refinement_engine import IterativeRefinementEngine


def main() -> None:
    prompts = [
        "Mother with 3 children under umbrella in rain",
        "Family of 4 at sunset beach",
        "Couple walking in rain under umbrella",
    ]

    if len(sys.argv) > 1:
        prompts = [sys.argv[1]]

    print("=" * 70)
    print("PHOTOGENIUS AI - SELF-IMPROVEMENT DEMO")
    print("=" * 70)
    print("\nThis demo shows how the system learns from each generation.")
    print("Watch the statistics improve over multiple prompts!\n")

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"
    print(f"Using device: {device}\n")

    print("Loading systems...")
    refinement_engine = IterativeRefinementEngine(
        device=device,
        max_iterations=3,
        quality_threshold=0.85,
        use_models=(device == "cuda"),
    )

    si_engine = SelfImprovementEngine(storage_dir="data/self_improvement_demo")

    for i, prompt in enumerate(prompts):
        print(f"\n{'='*70}")
        print(f"GENERATION {i+1}/{len(prompts)}")
        print(f"{'='*70}\n")

        try:
            result = si_engine.generate_with_learning(
                refinement_engine,
                prompt,
                max_iterations=3,
                save_iterations=False,
            )
        except Exception as e:
            print(f"Generation failed: {e}")
            continue

        score = result.get("final_score", 0.0)
        total_iter = result.get("total_iterations", 0)
        si = result.get("self_improvement") or {}
        memory_size = si.get("memory_size", 0)

        print(f"\nGeneration {i+1} complete.")
        print(f"   Score: {score:.3f}")
        print(f"   Iterations: {total_iter}")
        print(f"   Memory size: {memory_size}")

    print(f"\n{'='*70}")
    print("FINAL STATISTICS")
    print(f"{'='*70}")

    stats = si_engine.memory.get_statistics()
    print(f"Total experiences: {stats.get('total_experiences', 0)}")
    print(f"Overall success rate: {stats.get('success_rate', 0):.1%}")
    print(f"Average score: {stats.get('avg_score', 0):.3f}")
    print(f"Average iterations: {stats.get('avg_iterations', 0):.1f}")
    print(f"Failure patterns learned: {stats.get('failure_patterns_known', 0)}")
    print(f"Success patterns learned: {stats.get('success_patterns_known', 0)}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
