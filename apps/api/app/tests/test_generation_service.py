"""
Tests for SDXL generation service.
"""

import pytest  # type: ignore[reportMissingImports]
import torch  # type: ignore[reportMissingImports]
from pathlib import Path
from PIL import Image  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.services.ai.generation_service import (
    SDXLGenerationService,
    GenerationConfig,
    GenerationResult,
    get_generation_service,
)


class TestSDXLGenerationService:
    """Tests for SDXL generation service"""
    
    @pytest.fixture
    def service(self):
        """Create service instance"""
        # Use CPU for testing to avoid GPU requirements
        return SDXLGenerationService(
            model_path="stabilityai/stable-diffusion-xl-base-1.0",
            device="cpu",  # Use CPU for tests
        )
    
    @pytest.fixture
    def identity_data(self):
        """Mock identity data"""
        return {
            "lora_path": "/path/to/lora.safetensors",
            "face_embedding": np.random.rand(512).astype(np.float32),
            "trigger_word": "sks",
        }
    
    @pytest.fixture
    def mock_image(self):
        """Create a mock PIL Image"""
        return Image.new("RGB", (1024, 1024), color="red")
    
    # ==================== INITIALIZATION ====================
    
    def test_initialize_service(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.device in ["cpu", "cuda"]
        assert service.model_path is not None
    
    def test_mode_configs_exist(self, service):
        """Test mode configurations exist"""
        assert "REALISM" in service.MODE_CONFIGS
        assert "CREATIVE" in service.MODE_CONFIGS
        assert "ROMANTIC" in service.MODE_CONFIGS
        
        # Check config structure
        realism_config = service.MODE_CONFIGS["REALISM"]
        assert isinstance(realism_config, GenerationConfig)
        assert realism_config.mode == "REALISM"
        assert realism_config.num_candidates > 0
        assert realism_config.num_inference_steps > 0
    
    def test_mode_configs_different(self, service):
        """Test that mode configs have different settings"""
        realism = service.MODE_CONFIGS["REALISM"]
        creative = service.MODE_CONFIGS["CREATIVE"]
        
        # Creative should have more candidates
        assert creative.num_candidates >= realism.num_candidates
    
    # ==================== PROMPT ENHANCEMENT ====================
    
    def test_enhance_prompt_adds_trigger(self, service):
        """Test trigger word is added to prompt"""
        prompt = "professional headshot"
        enhanced = service._enhance_prompt_with_trigger(
            prompt, "sks", "REALISM"
        )
        
        assert "sks" in enhanced
    
    def test_enhance_prompt_replaces_person(self, service):
        """Test person is replaced with trigger"""
        prompt = "portrait of a person"
        enhanced = service._enhance_prompt_with_trigger(
            prompt, "sks", "REALISM"
        )
        
        assert "sks person" in enhanced
        # Should not have standalone "a person"
        assert "a person" not in enhanced or "sks person" in enhanced
    
    def test_enhance_prompt_mode_specific(self, service):
        """Test mode-specific enhancements"""
        prompt = "portrait"
        
        realism = service._enhance_prompt_with_trigger(prompt, "sks", "REALISM")
        assert "professional" in realism.lower() or "high quality" in realism.lower()
        
        creative = service._enhance_prompt_with_trigger(prompt, "sks", "CREATIVE")
        assert "creative" in creative.lower() or "artistic" in creative.lower()
        
        romantic = service._enhance_prompt_with_trigger(prompt, "sks", "ROMANTIC")
        assert "elegant" in romantic.lower() or "romantic" in romantic.lower()
    
    def test_enhance_prompt_preserves_original(self, service):
        """Test that original prompt content is preserved"""
        prompt = "a beautiful sunset"
        enhanced = service._enhance_prompt_with_trigger(
            prompt, "sks", "REALISM"
        )
        
        assert "sunset" in enhanced.lower()
    
    # ==================== NEGATIVE PROMPT ====================
    
    def test_default_negative_prompt(self, service):
        """Test default negative prompts for modes"""
        realism_neg = service._get_default_negative_prompt("REALISM")
        creative_neg = service._get_default_negative_prompt("CREATIVE")
        romantic_neg = service._get_default_negative_prompt("ROMANTIC")
        
        assert len(realism_neg) > 0
        assert len(creative_neg) > 0
        assert len(romantic_neg) > 0
        
        # Realism should exclude artistic styles
        assert "cartoon" in realism_neg.lower() or "painting" in realism_neg.lower()
        
        # Romantic should exclude inappropriate content
        assert "inappropriate" in romantic_neg.lower() or "explicit" in romantic_neg.lower()
    
    # ==================== STATISTICS ====================
    
    def test_statistics_tracking(self, service):
        """Test statistics are tracked"""
        stats = service.get_statistics()
        
        assert "total_generations" in stats
        assert "total_images" in stats
        assert "avg_generation_time" in stats
        assert "lora_loads" in stats
        
        # Initial values should be zero
        assert stats["total_generations"] == 0
        assert stats["total_images"] == 0
        assert stats["lora_loads"] == 0
    
    def test_statistics_are_copy(self, service):
        """Test that statistics return a copy"""
        stats1 = service.get_statistics()
        stats2 = service.get_statistics()
        
        # Should be equal but not the same object
        assert stats1 == stats2
        assert stats1 is not stats2
    
    # ==================== CACHE MANAGEMENT ====================
    
    def test_clear_cache(self, service):
        """Test cache clearing"""
        service.clear_cache()
        
        # Should not raise exception
        assert service.current_lora_path is None
    
    def test_clear_cache_with_lora(self, service):
        """Test cache clearing with loaded LoRA"""
        service.current_lora_path = "/test/lora.safetensors"
        service.clear_cache()
        
        assert service.current_lora_path is None
    
    # ==================== LORA LOADING ====================
    
    @pytest.mark.asyncio
    async def test_load_lora_skips_if_same(self, service):
        """Test that loading same LoRA is skipped"""
        service.current_lora_path = "/test/lora.safetensors"
        
        with patch.object(service, "_download_from_s3", new_callable=AsyncMock) as mock_download:
            await service._load_lora("/test/lora.safetensors")
            # Should not download if already loaded
            mock_download.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_load_lora_downloads_from_s3(self, service):
        """Test LoRA download from S3"""
        s3_path = "s3://bucket/lora.safetensors"
        local_path = "/tmp/lora_cache/lora.safetensors"
        
        with patch.object(service, "_download_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = local_path
            with patch("os.path.exists", return_value=True):
                with patch.object(service, "_ensure_pipeline_loaded"):
                    with patch.object(service.pipe, "load_lora_weights") if service.pipe else patch("builtins.hasattr"):
                        await service._load_lora(s3_path)
                        mock_download.assert_called_once_with(s3_path)
    
    @pytest.mark.asyncio
    async def test_load_lora_raises_on_missing_file(self, service):
        """Test that missing LoRA file raises error"""
        with patch.object(service, "_download_from_s3", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = "/nonexistent/path.safetensors"
            with patch("os.path.exists", return_value=False):
                with pytest.raises(FileNotFoundError):
                    await service._load_lora("s3://bucket/lora.safetensors")
    
    # ==================== S3 DOWNLOAD ====================
    
    @pytest.mark.asyncio
    async def test_download_from_s3_uses_cache(self, service, tmp_path):
        """Test S3 download uses cache if file exists"""
        cache_dir = tmp_path / "lora_cache"
        cache_dir.mkdir()
        local_file = cache_dir / "lora.safetensors"
        local_file.write_text("test")
        
        # Mock Path to return our temp directory
        with patch("app.services.ai.generation_service.Path") as mock_path:
            mock_path.return_value.mkdir = Mock()
            mock_path.return_value.__truediv__ = lambda self, other: cache_dir / other
            mock_path.return_value.exists = lambda: True
            
            result = await service._download_from_s3("s3://bucket/lora.safetensors")
            # Should return cached path
            assert "lora.safetensors" in str(result)
    
    # ==================== GENERATION ====================
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    async def test_generate_requires_pipeline(self, service):
        """Test that generation requires pipeline to be loaded"""
        service._pipe_initialized = False
        
        with patch.object(service, "_ensure_pipeline_loaded") as mock_ensure:
            with patch.object(service, "_generate_candidates", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {"images": [Image.new("RGB", (100, 100))], "seeds": [123]}
                with patch("app.services.ai.generation_service.QualityScorer") as mock_scorer:
                    mock_scorer.return_value.score_batch = AsyncMock(return_value=[{"total_score": 90.0}])
                    
                    result = await service.generate(
                        prompt="test",
                        negative_prompt="bad",
                        identity_data=None,
                        mode="REALISM",
                    )
                    
                    mock_ensure.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_invalid_mode_raises(self, service):
        """Test that invalid mode raises error"""
        with pytest.raises(ValueError, match="Invalid mode"):
            await service.generate(
                prompt="test",
                mode="INVALID_MODE",
            )
    
    @pytest.mark.asyncio
    async def test_generate_uses_mode_config(self, service):
        """Test that generation uses correct mode config"""
        with patch.object(service, "_ensure_pipeline_loaded"):
            with patch.object(service, "_generate_candidates", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {"images": [Image.new("RGB", (100, 100))], "seeds": [123]}
                with patch("app.services.ai.generation_service.QualityScorer") as mock_scorer:
                    mock_scorer.return_value.score_batch = AsyncMock(return_value=[{"total_score": 90.0}])
                    
                    await service.generate(
                        prompt="test",
                        mode="CREATIVE",
                    )
                    
                    # Check that creative config was used
                    call_args = mock_gen.call_args
                    config = call_args.kwargs["config"]
                    assert config.mode == "CREATIVE"
                    assert config.num_candidates == service.MODE_CONFIGS["CREATIVE"].num_candidates
    
    @pytest.mark.asyncio
    async def test_generate_updates_statistics(self, service):
        """Test that generation updates statistics"""
        initial_stats = service.get_statistics()
        assert initial_stats["total_generations"] == 0
        
        with patch.object(service, "_ensure_pipeline_loaded"):
            with patch.object(service, "_generate_candidates", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {"images": [Image.new("RGB", (100, 100))], "seeds": [123]}
                with patch("app.services.ai.generation_service.QualityScorer") as mock_scorer:
                    mock_scorer.return_value.score_batch = AsyncMock(return_value=[{"total_score": 90.0}])
                    
                    await service.generate(
                        prompt="test",
                        mode="REALISM",
                    )
                    
                    stats = service.get_statistics()
                    assert stats["total_generations"] == 1
                    assert stats["total_images"] > 0
    
    @pytest.mark.asyncio
    async def test_generate_progress_callback(self, service):
        """Test that progress callback is called"""
        progress_calls = []
        
        async def progress_callback(progress: int, message: str):
            progress_calls.append((progress, message))
        
        with patch.object(service, "_ensure_pipeline_loaded"):
            with patch.object(service, "_generate_candidates", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {"images": [Image.new("RGB", (100, 100))], "seeds": [123]}
                with patch("app.services.ai.generation_service.QualityScorer") as mock_scorer:
                    mock_scorer.return_value.score_batch = AsyncMock(return_value=[{"total_score": 90.0}])
                    
                    await service.generate(
                        prompt="test",
                        mode="REALISM",
                        progress_callback=progress_callback,
                    )
                    
                    # Should have progress updates
                    assert len(progress_calls) > 0
                    # Should end at 100%
                    assert any(p == 100 for p, _ in progress_calls)
    
    # ==================== BEST SELECTION ====================
    
    @pytest.mark.asyncio
    async def test_generate_with_best_selection(self, service):
        """Test that best selection works"""
        # Create multiple mock images
        images = [Image.new("RGB", (100, 100), color=c) for c in ["red", "green", "blue"]]
        
        with patch.object(service, "_ensure_pipeline_loaded"):
            with patch.object(service, "_generate_candidates", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = {"images": images, "seeds": [1, 2, 3]}
                with patch("app.services.ai.generation_service.QualityScorer") as mock_scorer:
                    # Return scores in descending order
                    mock_scorer.return_value.score_batch = AsyncMock(
                        return_value=[
                            {"total_score": 70.0},  # Worst
                            {"total_score": 90.0},  # Best
                            {"total_score": 80.0},  # Middle
                        ]
                    )
                    
                    result = await service.generate(
                        prompt="test",
                        mode="REALISM",  # Should return top 2
                    )
                    
                    # Should have selected best images
                    assert result.selected_index == 0
                    assert len(result.images) == 2  # Top 2 for realism
                    assert result.quality_scores is not None
    
    # ==================== SINGLETON ====================
    
    def test_get_generation_service_singleton(self):
        """Test that get_generation_service returns singleton"""
        service1 = get_generation_service()
        service2 = get_generation_service()
        
        assert service1 is service2
    
    # ==================== ERROR HANDLING ====================
    
    @pytest.mark.asyncio
    async def test_generate_handles_errors(self, service):
        """Test that generation handles errors gracefully"""
        with patch.object(service, "_ensure_pipeline_loaded", side_effect=Exception("Pipeline error")):
            with pytest.raises(Exception):
                await service.generate(
                    prompt="test",
                    mode="REALISM",
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
