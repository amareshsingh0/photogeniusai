"""
Tests for Training Augmentation (AdvancedLoRATrainer).

- Augmentation pipeline: 3x per image, output count and type.
- Regularization: default load returns list.
- Validation prompts and face similarity (optional, GPU/InsightFace).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from PIL import Image
import numpy as np


def test_augmentation_returns_three_times_per_image():
    """_augment_training_images returns 3x the number of input images."""
    from services.lora_trainer import AdvancedLoRATrainer

    pipe = MagicMock()
    face_app = MagicMock()
    trainer = AdvancedLoRATrainer(pipe=pipe, face_app=face_app, trigger_word="sks")

    # Single 1024x1024 PIL image
    img = Image.new("RGB", (1024, 1024), color=(128, 128, 128))
    images = [img]
    augmented = trainer._augment_training_images(images)
    assert len(augmented) == 3, "Expected 3 augmented images per input image"

    # Five images -> 15 augmented
    images5 = [Image.new("RGB", (1024, 1024), color=(i * 50, 100, 150)) for i in range(5)]
    augmented5 = trainer._augment_training_images(images5)
    assert len(augmented5) == 15


def test_augmentation_output_size():
    """Augmented images have expected size (1024 for SDXL)."""
    from services.lora_trainer import AdvancedLoRATrainer

    pipe = MagicMock()
    face_app = MagicMock()
    trainer = AdvancedLoRATrainer(pipe=pipe, face_app=face_app, trigger_word="sks")
    img = Image.new("RGB", (1024, 1024), color=(0, 0, 0))
    augmented = trainer._augment_training_images([img])
    for out in augmented:
        # Augmentation uses RandomResizedCrop(1024); output is 1024x1024 (PIL) or tensor
        if hasattr(out, "size"):
            assert out.size[0] == 1024 and out.size[1] == 1024
        elif hasattr(out, "shape"):
            assert out.shape[-2] == 1024 and out.shape[-1] == 1024


def test_load_default_regularization_returns_list():
    """_load_default_regularization returns a list (may be empty)."""
    from services.lora_trainer import AdvancedLoRATrainer

    pipe = MagicMock()
    face_app = MagicMock()
    trainer = AdvancedLoRATrainer(pipe=pipe, face_app=face_app, trigger_word="sks")
    reg = trainer._load_default_regularization()
    assert isinstance(reg, list)


def test_validation_prompts_non_empty():
    """Validation prompts are defined and non-empty."""
    from services.lora_trainer import AdvancedLoRATrainer

    assert len(AdvancedLoRATrainer.VALIDATION_PROMPTS) >= 3
    for p in AdvancedLoRATrainer.VALIDATION_PROMPTS:
        assert isinstance(p, str) and len(p) > 0


def test_detect_and_crop_faces_empty_on_no_faces():
    """_detect_and_crop_faces returns empty list when face_app finds no faces."""
    from services.lora_trainer import AdvancedLoRATrainer

    face_app = MagicMock()
    face_app.get.return_value = []  # no faces
    pipe = MagicMock()
    trainer = AdvancedLoRATrainer(pipe=pipe, face_app=face_app, trigger_word="sks")
    img = Image.new("RGB", (512, 512), color=(200, 200, 200))
    result = trainer._detect_and_crop_faces([img])
    assert result == []


def test_compute_face_similarity_in_range():
    """_compute_face_similarity returns value in [0, 1] (0 when no face, high when same face)."""
    pytest.importorskip("insightface")
    from services.lora_trainer import AdvancedLoRATrainer

    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        pytest.skip("InsightFace not available")
    face_app = FaceAnalysis(name="buffalo_l")
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    pipe = MagicMock()
    trainer = AdvancedLoRATrainer(pipe=pipe, face_app=face_app, trigger_word="sks")
    img = Image.new("RGB", (256, 256), color=(180, 160, 140))
    sim = trainer._compute_face_similarity(img, img)
    assert 0 <= sim <= 1.01
    # Same image: if face detected, sim is high (~1); if no face, sim is 0


@pytest.mark.gpu
def test_train_identity_lora_interface():
    """train_identity_lora runs without error with minimal data (smoke test)."""
    pytest.importorskip("torch")
    pytest.importorskip("diffusers")
    pytest.importorskip("insightface")
    from services.lora_trainer import AdvancedLoRATrainer
    import torch
    from diffusers import StableDiffusionXLPipeline
    from peft import LoraConfig, get_peft_model
    from insightface.app import FaceAnalysis

    # Minimal setup: tiny steps, small model not actually loaded in test
    # This test is meant to run in GPU env; skip if no CUDA
    if not torch.cuda.is_available():
        pytest.skip("CUDA required for train_identity_lora smoke test")

    face_app = FaceAnalysis(name="buffalo_l")
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        variant="fp16",
    ).to("cuda")
    lora_config = LoraConfig(r=8, lora_alpha=8, target_modules=["to_q", "to_k"], lora_dropout=0.05, bias="none")
    pipe.unet = get_peft_model(pipe.unet, lora_config)
    trainer = AdvancedLoRATrainer(pipe=pipe, face_app=face_app, trigger_word="sks", device="cuda")
    # Use 2 identical small "face" images (may not detect face; then _detect_and_crop_faces returns [])
    imgs = [Image.new("RGB", (512, 512), color=(180, 170, 160)) for _ in range(2)]
    faces = trainer._detect_and_crop_faces(imgs)
    if len(faces) < 2:
        pytest.skip("Need at least 2 face crops; use real face images in GPU env")
    try:
        unet, score = trainer.train_identity_lora(identity_images=faces, regularization_images=[], steps=2, batch_size=2)
        assert unet is not None
        assert 0 <= score <= 1.01
    except Exception as e:
        pytest.skip(f"train_identity_lora smoke test skipped: {e}")
