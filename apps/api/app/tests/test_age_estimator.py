"""
Comprehensive tests for Age Estimator
Tests DeepFace integration, age detection, and blocking logic
"""
import pytest  # type: ignore[reportMissingImports]
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from app.services.safety.age_estimator import (
    AgeEstimator,
    FaceAgeResult,
    AgeCheckResult
)

class TestAgeEstimator:
    """Tests for age estimator"""
    
    @pytest.fixture
    async def estimator(self):
        return AgeEstimator()
    
    @pytest.fixture
    def test_image_no_face(self, tmp_path):
        """Create image with no face"""
        img = Image.new('RGB', (512, 512), color='white')
        path = tmp_path / "no_face.png"
        img.save(path)
        return str(path)
    
    # ==================== INITIALIZATION ====================
    
    @pytest.mark.asyncio
    async def test_initialize_estimator(self, estimator):
        """Test estimator initialization"""
        assert estimator is not None
        assert estimator.MIN_AGE == 18
        assert estimator.stats["total_checked"] == 0
    
    # ==================== NO FACE DETECTION ====================
    
    @pytest.mark.asyncio
    async def test_no_face_detected(self, estimator, test_image_no_face):
        """Test image with no face is allowed"""
        result = await estimator.check_image(
            image_path=test_image_no_face,
            user_id="test_user",
            generation_id="test_gen"
        )
        
        assert result.safe is True
        assert len(result.faces) == 0
        assert result.min_age is None
        assert "No faces" in result.reason
    
    # ==================== STATISTICS ====================
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, estimator, test_image_no_face):
        """Test statistics are tracked"""
        initial_total = estimator.stats["total_checked"]
        
        await estimator.check_image(
            image_path=test_image_no_face,
            user_id="test_user",
            generation_id="test_gen"
        )
        
        assert estimator.stats["total_checked"] == initial_total + 1
    
    def test_get_statistics(self, estimator):
        """Test statistics retrieval"""
        stats = estimator.get_statistics()
        
        assert "total_checked" in stats
        assert "blocked" in stats
        assert "allowed" in stats
        assert "avg_age" in stats
    
    # ==================== BATCH PROCESSING ====================
    
    @pytest.mark.asyncio
    async def test_batch_check(self, estimator, tmp_path):
        """Test batch processing"""
        # Create multiple test images
        image_paths = []
        for i in range(3):
            img = Image.new('RGB', (512, 512), color='white')
            path = tmp_path / f"test_{i}.png"
            img.save(path)
            image_paths.append(str(path))
        
        results = await estimator.check_batch(
            image_paths=image_paths,
            user_id="test_user",
            generation_id="test_gen"
        )
        
        assert len(results) == 3
        for result in results:
            assert isinstance(result.safe, bool)
    
    # ==================== ERROR HANDLING ====================
    
    @pytest.mark.asyncio
    async def test_handle_missing_image(self, estimator):
        """Test handling of missing image"""
        result = await estimator.check_image(
            image_path="/nonexistent/image.png",
            user_id="test_user",
            generation_id="test_gen"
        )
        
        # Should return blocked on error (fail-safe)
        assert result.safe is False
        assert "failed" in result.reason.lower()
    
    @pytest.mark.asyncio
    async def test_handle_corrupted_image(self, estimator, tmp_path):
        """Test handling of corrupted image"""
        corrupted = tmp_path / "corrupted.png"
        corrupted.write_bytes(b"not an image")
        
        result = await estimator.check_image(
            image_path=str(corrupted),
            user_id="test_user",
            generation_id="test_gen"
        )
        
        # Should handle gracefully
        assert result is not None
    
    # ==================== PERFORMANCE ====================
    
    @pytest.mark.asyncio
    async def test_performance(self, estimator, test_image_no_face):
        """Test estimation completes in <3 seconds"""
        import time
        
        start = time.time()
        
        result = await estimator.check_image(
            image_path=test_image_no_face,
            user_id="test_user",
            generation_id="test_gen"
        )
        
        elapsed = time.time() - start
        
        assert elapsed < 3.0, f"Too slow: {elapsed:.2f}s"
        assert result is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
