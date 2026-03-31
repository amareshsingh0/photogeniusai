"""
Comprehensive tests for Dual Pipeline Safety System
Tests pre-generation and post-generation checks
"""
import pytest  # type: ignore[reportMissingImports]
import asyncio
from pathlib import Path
from PIL import Image  # type: ignore[reportMissingImports]
from app.services.safety.dual_pipeline import (
    DualPipelineSafety,
    SafetyStage,
    PreGenerationResult,
    PostGenerationResult,
    run_pre_check,
    run_post_check,
)

class TestDualPipelineSafety:
    """Tests for dual pipeline safety system"""
    
    @pytest.fixture
    async def pipeline(self):
        return DualPipelineSafety()
    
    @pytest.fixture
    def safe_prompt(self):
        return "professional headshot of businessman in suit"
    
    @pytest.fixture
    def unsafe_prompt(self):
        return "nude celebrity portrait"
    
    @pytest.fixture
    def test_image_path(self, tmp_path):
        """Create a test image"""
        img = Image.new('RGB', (512, 512), color='white')
        path = tmp_path / "test.png"
        img.save(path)
        return str(path)
    
    # ==================== INITIALIZATION ====================
    
    @pytest.mark.asyncio
    async def test_initialize_pipeline(self, pipeline):
        """Test pipeline initialization"""
        assert pipeline is not None
        assert pipeline.prompt_sanitizer is not None
        assert pipeline.nsfw_classifier is not None
        assert pipeline.age_estimator is not None
        assert pipeline.stats["pre_gen_checks"] == 0
    
    # ==================== PRE-GENERATION CHECKS ====================
    
    @pytest.mark.asyncio
    async def test_pre_check_safe_prompt(self, pipeline, safe_prompt):
        """Test pre-check with safe prompt"""
        result = await pipeline.pre_generation_check(
            user_id="test_user",
            prompt=safe_prompt,
            mode="REALISM"
        )
        
        assert isinstance(result, PreGenerationResult)
        assert result.allowed is True
        assert len(result.violations) == 0
        assert result.severity == "LOW"
        assert result.user_strike_added is False
    
    @pytest.mark.asyncio
    async def test_pre_check_unsafe_prompt(self, pipeline, unsafe_prompt):
        """Test pre-check with unsafe prompt"""
        result = await pipeline.pre_generation_check(
            user_id="test_user",
            prompt=unsafe_prompt,
            mode="REALISM"
        )
        
        assert isinstance(result, PreGenerationResult)
        assert result.allowed is False
        assert len(result.violations) > 0
        assert result.severity in ["MEDIUM", "HIGH", "CRITICAL"]
    
    @pytest.mark.asyncio
    async def test_pre_check_with_identity(self, pipeline, safe_prompt):
        """Test pre-check with identity"""
        result = await pipeline.pre_generation_check(
            user_id="test_user",
            prompt=safe_prompt,
            mode="REALISM",
            identity_id="test_identity"
        )
        
        assert isinstance(result, PreGenerationResult)
        # Should pass if identity check passes (or if fallback allows)
    
    # ==================== POST-GENERATION CHECKS ====================
    
    @pytest.mark.asyncio
    async def test_post_check_safe_image(self, pipeline, test_image_path):
        """Test post-check with safe image"""
        result = await pipeline.post_generation_check(
            image_path=test_image_path,
            user_id="test_user",
            generation_id="test_gen",
            mode="REALISM"
        )
        
        assert isinstance(result, PostGenerationResult)
        assert result.safe is True or result.action == "ALLOW"
        assert result.image_deleted is False
    
    @pytest.mark.asyncio
    async def test_post_check_missing_image(self, pipeline):
        """Test post-check with missing image"""
        result = await pipeline.post_generation_check(
            image_path="/nonexistent/image.png",
            user_id="test_user",
            generation_id="test_gen",
            mode="REALISM"
        )
        
        assert isinstance(result, PostGenerationResult)
        # Should handle gracefully (block on error)
        assert result.safe is False
    
    # ==================== CONVENIENCE FUNCTIONS ====================
    
    @pytest.mark.asyncio
    async def test_run_pre_check(self, safe_prompt):
        """Test convenience function"""
        result = await run_pre_check(
            user_id="test_user",
            prompt=safe_prompt,
            mode="REALISM"
        )
        
        assert isinstance(result, PreGenerationResult)
    
    @pytest.mark.asyncio
    async def test_run_post_check(self, test_image_path):
        """Test convenience function"""
        result = await run_post_check(
            image_path=test_image_path,
            user_id="test_user",
            generation_id="test_gen",
            mode="REALISM"
        )
        
        assert isinstance(result, PostGenerationResult)
    
    # ==================== STATISTICS ====================
    
    def test_get_statistics(self, pipeline):
        """Test statistics retrieval"""
        stats = pipeline.get_statistics()
        
        assert "pre_gen_checks" in stats
        assert "pre_gen_blocks" in stats
        assert "post_gen_checks" in stats
        assert "post_gen_blocks" in stats
        assert "strikes_added" in stats
        assert "users_banned" in stats
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, pipeline, safe_prompt):
        """Test statistics are tracked"""
        initial_checks = pipeline.stats["pre_gen_checks"]
        
        await pipeline.pre_generation_check(
            user_id="test_user",
            prompt=safe_prompt,
            mode="REALISM"
        )
        
        assert pipeline.stats["pre_gen_checks"] == initial_checks + 1
    
    # ==================== INTEGRATION ====================
    
    @pytest.mark.asyncio
    async def test_full_pipeline_flow(self, pipeline, safe_prompt, test_image_path):
        """Test complete pipeline flow"""
        # Pre-check
        pre_result = await pipeline.pre_generation_check(
            user_id="test_user",
            prompt=safe_prompt,
            mode="REALISM"
        )
        
        assert pre_result.allowed is True
        
        # Post-check
        post_result = await pipeline.post_generation_check(
            image_path=test_image_path,
            user_id="test_user",
            generation_id="test_gen",
            mode="REALISM"
        )
        
        assert isinstance(post_result, PostGenerationResult)
    
    # ==================== ERROR HANDLING ====================
    
    @pytest.mark.asyncio
    async def test_pre_check_error_handling(self, pipeline):
        """Test error handling in pre-check"""
        # Pass invalid parameters
        result = await pipeline.pre_generation_check(
            user_id="",
            prompt="",
            mode="INVALID_MODE"
        )
        
        assert isinstance(result, PreGenerationResult)
        # Should handle gracefully
    
    @pytest.mark.asyncio
    async def test_post_check_error_handling(self, pipeline):
        """Test error handling in post-check"""
        result = await pipeline.post_generation_check(
            image_path="",
            user_id="test_user",
            generation_id="test_gen",
            mode="REALISM"
        )
        
        assert isinstance(result, PostGenerationResult)
        # Should handle gracefully

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
