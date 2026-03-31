#!/usr/bin/env python3
"""
Quick validation: generate control images from scene graph and save OpenPose for inspection.
Run from ai-pipeline with: PYTHONPATH=. python scripts/validate_control_images.py
"""
import sys
from pathlib import Path

# Allow running from repo root or ai-pipeline
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.control_image_generator import ControlImageGenerator
from services.scene_graph_compiler import SceneGraphCompiler


def main():
    compiler = SceneGraphCompiler(use_spacy=False)
    scene = compiler.compile("Mother with 3 children under umbrella")

    gen = ControlImageGenerator()
    controls = gen.generate_all_controls(scene)

    print(f"✓ Generated controls: {list(controls.keys())}")
    op = controls["openpose"]
    if hasattr(op, "size"):
        print(f"✓ OpenPose size: {op.size}")
    else:
        import numpy as np  # type: ignore[reportMissingImports]

        print(f"✓ OpenPose shape: {np.asarray(op).shape}")

    out_path = Path(__file__).resolve().parent.parent / "test_openpose.png"
    if hasattr(op, "save"):
        op.save(str(out_path))
    else:
        import numpy as np  # type: ignore[reportMissingImports]
        from PIL import Image  # type: ignore[reportMissingImports]

        Image.fromarray(np.asarray(op)).save(str(out_path))
    print(f"✓ Saved {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
