import pytest  # type: ignore[reportMissingImports]
import asyncio
from pathlib import Path
from PIL import Image  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from app.services.safety.nsfw_classifier import (
    NSFWClassifier,
    SafetyAction,
    QuarantineManager
)

class TestNSFWClassifier:
    """Comprehensive tests for NSFW classifier"""
    
    @pytest.fixture
    async def classifier(self):
        return NSFWClassifier()
    
    @pytest.fixture
    def safe_image_path(self, tmp_path):
        """Create a safe test image"""
        img = Image.new('RGB', (512, 512), color='white')
        path = tmp_path / "safe.png"
        img.save(path)
        return str(path)
    
    # ==================== BASIC TESTS ====================
    
    @pytest.mark.asyncio
    async def test_initialize_classifier(self, classifier):
        """Test classifier initialization"""
        assert classifier is not None
        assert classifier.detector is not None
        assert classifier.stats["total_checked"] == 0
    
    @pytest.mark.asyncio
    async def test_classify_safe_image(self, classifier, safe_image_path):
        """Test classification of safe image"""
        result = await classifier.classify_image(
            image_path=safe_image_path,
            mode="REALISM",
            user_id="test_user",
            generation_id="test_gen"
        )
        
        assert result is not None
        assert result.action == SafetyAction.ALLOW
        assert result.nsfw_score < 0.40
        assert not result.user_strike_recommended
    
    # ==================== THRESHOLD TESTS ====================
    
    @pytest.mark.asyncio
    async def test_mode_specific_thresholds(self, classifier):
        """Test different modes have different thresholds"""
        realism_thresh = classifier.THRESHOLDS["REALISM"]
        creative_thresh = classifier.THRESHOLDS["CREATIVE"]
        romantic_thresh = classifier.THRESHOLDS["ROMANTIC"]
        
        # Romantic should be strictest
        assert romantic_thresh["BLOCK"] < realism_thresh["BLOCK"]
        assert romantic_thresh["BLOCK"] < creative_thresh["BLOCK"]
        
        # Creative should be most lenient
        assert creative_thresh["BLOCK"] > realism_thresh["BLOCK"]
    
    # ==================== SCORE CALCULATION ====================
    
    def test_calculate_nsfw_score_empty(self, classifier):
        """Test score calculation with no detections"""
        score = classifier._calculate_nsfw_score([])
        assert score == 0.0
    
    def test_calculate_nsfw_score_critical(self, classifier):
        """Test score with critical parts"""
        detections = [
            {
                "class": "EXPOSED_GENITALIA_F",
                "score": 0.95,
                "box": [0, 0, 100, 100]
            }
        ]
        
        score = classifier._calculate_nsfw_score(detections)
        assert score > 0.8  # High score for critical part
    
    def test_calculate_nsfw_score_low_severity(self, classifier):
        """Test score with low severity parts"""
        detections = [
            {
                "class": "EXPOSED_FEET",
                "score": 0.90,
                "box": [0, 0, 100, 100]
            }
        ]
        
        score = classifier._calculate_nsfw_score(detections)
        assert score < 0.2  # Low score for feet
    
    # ==================== ACTION DETERMINATION ====================
    
    def test_determine_action_critical_parts(self, classifier):
        """Test instant block for critical parts"""
        detections = [
            {
                "class": "EXPOSED_GENITALIA_M",
                "score": 0.50,
                "box": [0, 0, 100, 100]
            }
        ]
        
        action = classifier._determine_action(
            nsfw_score=0.30,  # Even low score
            detections=detections,
            thresholds=classifier.THRESHOLDS["REALISM"]
        )
        
        assert action == SafetyAction.BLOCK
    
    def test_determine_action_by_score(self, classifier):
        """Test action determination by score"""
        thresholds = classifier.THRESHOLDS["REALISM"]
        
        # Test BLOCK
        action = classifier._determine_action(
            nsfw_score=0.65,
            detections=[],
            thresholds=thresholds
        )
        assert action == SafetyAction.BLOCK
        
        # Test QUARANTINE
        action = classifier._determine_action(
            nsfw_score=0.50,
            detections=[],
            thresholds=thresholds
        )
        assert action == SafetyAction.QUARANTINE
        
        # Test ALLOW
        action = classifier._determine_action(
            nsfw_score=0.30,
            detections=[],
            thresholds=thresholds
        )
        assert action == SafetyAction.ALLOW
    
    # ==================== REASONING ====================
    
    def test_generate_reasoning_safe(self, classifier):
        """Test reasoning for safe content"""
        reasoning = classifier._generate_reasoning(
            detections=[],
            score=0.05,
            action=SafetyAction.ALLOW
        )
        
        assert "No NSFW content" in reasoning or "Safe" in reasoning
    
    def test_generate_reasoning_critical(self, classifier):
        """Test reasoning for critical content"""
        detections = [
            {
                "class": "EXPOSED_GENITALIA_F",
                "score": 0.95,
                "box": [0, 0, 100, 100]
            }
        ]
        
        reasoning = classifier._generate_reasoning(
            detections=detections,
            score=0.90,
            action=SafetyAction.BLOCK
        )
        
        assert "Critical" in reasoning or "EXPOSED_GENITALIA" in reasoning
    
    # ==================== USER STRIKES ====================
    
    def test_should_add_strike_critical(self, classifier):
        """Test strike for critical content"""
        detections = [
            {
                "class": "EXPOSED_ANUS",
                "score": 0.95,
                "box": [0, 0, 100, 100]
            }
        ]
        
        should_strike = classifier._should_add_strike(
            SafetyAction.BLOCK,
            detections
        )
        
        assert should_strike is True
    
    def test_should_add_strike_quarantine(self, classifier):
        """Test no strike for quarantine"""
        should_strike = classifier._should_add_strike(
            SafetyAction.QUARANTINE,
            []
        )
        
        assert should_strike is False
    
    # ==================== BATCH PROCESSING ====================
    
    @pytest.mark.asyncio
    async def test_batch_classify(self, classifier, tmp_path):
        """Test batch classification"""
        # Create multiple test images
        image_paths = []
        for i in range(5):
            img = Image.new('RGB', (512, 512), color='white')
            path = tmp_path / f"test_{i}.png"
            img.save(path)
            image_paths.append(str(path))
        
        results = await classifier.batch_classify(
            image_paths=image_paths,
            mode="REALISM",
            user_id="test_user",
            generation_id="test_gen"
        )
        
        assert len(results) == 5
        for result in results:
            assert isinstance(result.action, SafetyAction)
    
    # ==================== STATISTICS ====================
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, classifier, safe_image_path):
        """Test statistics are tracked"""
        initial_total = classifier.stats["total_checked"]
        
        await classifier.classify_image(
            image_path=safe_image_path,
            mode="REALISM",
            user_id="test_user",
            generation_id="test_gen"
        )
        
        assert classifier.stats["total_checked"] == initial_total + 1
        assert classifier.stats["allowed"] > 0
    
    def test_get_statistics(self, classifier):
        """Test statistics retrieval"""
        stats = classifier.get_statistics()
        
        assert "total_checked" in stats
        assert "blocked" in stats
        assert "quarantined" in stats
        assert "allowed" in stats
    
    # ==================== PERFORMANCE ====================
    
    @pytest.mark.asyncio
    async def test_classification_performance(self, classifier, safe_image_path):
        """Test classification completes in <2 seconds"""
        import time
        
        start = time.time()
        
        result = await classifier.classify_image(
            image_path=safe_image_path,
            mode="REALISM",
            user_id="test_user",
            generation_id="test_gen"
        )
        
        elapsed = time.time() - start
        
        assert elapsed < 2.0, f"Too slow: {elapsed:.2f}s"
        assert result is not None
    
    # ==================== ERROR HANDLING ====================
    
    @pytest.mark.asyncio
    async def test_handle_missing_image(self, classifier):
        """Test handling of missing image"""
        result = await classifier.classify_image(
            image_path="/nonexistent/image.png",
            mode="REALISM",
            user_id="test_user",
            generation_id="test_gen"
        )
        
        # Should return BLOCK on error (fail-safe)
        assert result.action == SafetyAction.BLOCK
        assert "error" in result.metadata
    
    @pytest.mark.asyncio
    async def test_handle_corrupted_image(self, classifier, tmp_path):
        """Test handling of corrupted image"""
        # Create corrupted file
        corrupted = tmp_path / "corrupted.png"
        corrupted.write_bytes(b"not an image")
        
        result = await classifier.classify_image(
            image_path=str(corrupted),
            mode="REALISM",
            user_id="test_user",
            generation_id="test_gen"
        )
        
        # Should handle gracefully
        assert result is not None


class TestQuarantineManager:
    """Tests for quarantine management"""
    
    @pytest.fixture
    def quarantine_manager(self, tmp_path):
        return QuarantineManager(quarantine_dir=str(tmp_path))
    
    @pytest.mark.asyncio
    async def test_list_quarantined_empty(self, quarantine_manager):
        """Test listing with no quarantined images"""
        quarantined = await quarantine_manager.list_quarantined()
        assert quarantined == []
    
    @pytest.mark.asyncio
    async def test_cleanup_old(self, quarantine_manager):
        """Test cleanup of old quarantined images"""
        deleted = await quarantine_manager.cleanup_old(days=30)
        assert deleted >= 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
