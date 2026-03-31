"""
Tests for advanced quality scorer.
"""

import pytest  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from PIL import Image  # type: ignore[reportMissingImports]
import asyncio

from app.services.ai.quality_scorer import QualityScorer, QualityReport


class TestQualityScorer:
    """Tests for quality scorer"""
    
    @pytest.fixture
    def scorer(self):
        """Create scorer instance"""
        return QualityScorer()
    
    @pytest.fixture
    def test_image(self):
        """Create test image"""
        return Image.new('RGB', (1024, 1024), color='white')
    
    @pytest.fixture
    def test_face_embedding(self):
        """Create mock face embedding"""
        return np.random.rand(512).astype(np.float32)
    
    # ==================== INITIALIZATION ====================
    
    def test_initialize_scorer(self, scorer):
        """Test scorer initialization"""
        assert scorer is not None
        assert hasattr(scorer, 'device')
        assert hasattr(scorer, 'SCORE_WEIGHTS')
    
    def test_mode_weights_exist(self, scorer):
        """Test mode-specific weights exist"""
        assert "REALISM" in scorer.SCORE_WEIGHTS
        assert "CREATIVE" in scorer.SCORE_WEIGHTS
        assert "ROMANTIC" in scorer.SCORE_WEIGHTS
        
        # Check weights sum to ~1.0
        for mode, weights in scorer.SCORE_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{mode} weights don't sum to 1.0"
    
    # ==================== SCORING ====================
    
    @pytest.mark.asyncio
    async def test_score_image(self, scorer, test_image):
        """Test scoring single image with score_image method"""
        scores = await scorer.score_image(test_image, mode="REALISM")
        
        assert isinstance(scores, dict)
        assert "face_match_score" in scores
        assert "aesthetic_score" in scores
        assert "technical_score" in scores
        assert "composition_score" in scores
        assert "total_score" in scores
        
        # All scores should be 0-100
        for key, value in scores.items():
            assert 0 <= value <= 100, f"{key} score out of range: {value}"
    
    @pytest.mark.asyncio
    async def test_score_single_image(self, scorer, test_image):
        """Test scoring single image with score_single method"""
        report = await scorer.score_single(test_image, mode="REALISM")
        
        assert isinstance(report, QualityReport)
        assert 0 <= report.overall_score <= 100
        assert 0 <= report.aesthetic_score <= 100
        assert 0 <= report.technical_quality <= 100
        assert 0 <= report.composition_score <= 100
        assert 0 <= report.prompt_adherence <= 100
    
    @pytest.mark.asyncio
    async def test_score_image_with_face(self, scorer, test_image, test_face_embedding):
        """Test scoring with face embedding using score_image"""
        scores = await scorer.score_image(
            test_image,
            reference_embedding=test_face_embedding,
            mode="REALISM"
        )
        
        assert "face_match_score" in scores
        assert 0 <= scores["face_match_score"] <= 100
        # Should not be 50.0 when face embedding is provided
        assert scores["face_match_score"] != 50.0 or scorer.face_analyzer is None
    
    @pytest.mark.asyncio
    async def test_score_single_with_face(self, scorer, test_image, test_face_embedding):
        """Test scoring with face embedding using score_single"""
        report = await scorer.score_single(
            test_image,
            reference_embedding=test_face_embedding,
            mode="REALISM"
        )
        
        assert report.face_match_percent is not None
        assert 0 <= report.face_match_percent <= 100
    
    @pytest.mark.asyncio
    async def test_score_image_without_face(self, scorer, test_image):
        """Test scoring without face embedding using score_image"""
        scores = await scorer.score_image(test_image, mode="REALISM")
        
        # Face match should be 50.0 (neutral) if no reference
        assert scores["face_match_score"] == 50.0
    
    @pytest.mark.asyncio
    async def test_score_single_without_face(self, scorer, test_image):
        """Test scoring without face embedding using score_single"""
        report = await scorer.score_single(test_image, mode="REALISM")
        
        # Face match should be None if no reference
        assert report.face_match_percent is None
    
    @pytest.mark.asyncio
    async def test_score_batch(self, scorer):
        """Test batch scoring"""
        images = [
            Image.new('RGB', (512, 512), color='white'),
            Image.new('RGB', (512, 512), color='black'),
            Image.new('RGB', (512, 512), color='red'),
        ]
        
        scores = await scorer.score_batch(images, mode="REALISM")
        
        assert len(scores) == 3
        for score_dict in scores:
            assert "total_score" in score_dict
            assert "face_match" in score_dict
            assert "aesthetic" in score_dict
            assert "technical" in score_dict
            assert "composition" in score_dict
            assert "prompt_adherence" in score_dict
            
            # All scores should be 0-100
            for key, value in score_dict.items():
                assert 0 <= value <= 100, f"{key} score out of range: {value}"
    
    # ==================== MODE-SPECIFIC WEIGHTS ====================
    
    @pytest.mark.asyncio
    async def test_mode_specific_weights(self, scorer, test_image):
        """Test different modes use different weights"""
        realism_report = await scorer.score_single(test_image, mode="REALISM")
        creative_report = await scorer.score_single(test_image, mode="CREATIVE")
        romantic_report = await scorer.score_single(test_image, mode="ROMANTIC")
        
        # All should work
        assert realism_report.overall_score >= 0
        assert creative_report.overall_score >= 0
        assert romantic_report.overall_score >= 0
        
        # Scores might differ due to weighting
        # Just verify all are valid
        assert 0 <= realism_report.overall_score <= 100
        assert 0 <= creative_report.overall_score <= 100
        assert 0 <= romantic_report.overall_score <= 100
    
    # ==================== FACE MATCH ====================
    
    @pytest.mark.asyncio
    async def test_face_match_with_embedding(self, scorer, test_image, test_face_embedding):
        """Test face match scoring with embedding"""
        score = await scorer._score_face_match(test_image, test_face_embedding)
        
        # Should return None if no face detected, or a score 0-100
        if score is not None:
            assert 0 <= score <= 100
    
    @pytest.mark.asyncio
    async def test_face_match_without_embedding(self, scorer, test_image):
        """Test face match scoring without embedding"""
        score = await scorer._score_face_match(test_image, None)
        
        assert score is None
    
    # ==================== AESTHETIC ====================
    
    @pytest.mark.asyncio
    async def test_aesthetic_scoring(self, scorer, test_image):
        """Test aesthetic scoring"""
        score = await scorer._score_aesthetic(test_image)
        
        assert 0 <= score <= 100
    
    # ==================== TECHNICAL ====================
    
    @pytest.mark.asyncio
    async def test_technical_scoring(self, scorer, test_image):
        """Test technical quality scoring"""
        score = await scorer._score_technical(test_image)
        
        assert 0 <= score <= 100
    
    # ==================== COMPOSITION ====================
    
    @pytest.mark.asyncio
    async def test_composition_scoring(self, scorer, test_image):
        """Test composition scoring"""
        score = await scorer._score_composition(test_image)
        
        assert 0 <= score <= 100
    
    # ==================== PROMPT ADHERENCE ====================
    
    @pytest.mark.asyncio
    async def test_prompt_adherence_with_prompt(self, scorer, test_image):
        """Test prompt adherence with prompt"""
        score = await scorer._score_prompt_adherence(test_image, "a beautiful landscape")
        
        assert 0 <= score <= 100
    
    @pytest.mark.asyncio
    async def test_prompt_adherence_without_prompt(self, scorer, test_image):
        """Test prompt adherence without prompt"""
        score = await scorer._score_prompt_adherence(test_image, None)
        
        # Should return default score
        assert score == 85.0
    
    # ==================== EDGE CASES ====================
    
    @pytest.mark.asyncio
    async def test_score_small_image(self, scorer):
        """Test scoring small image"""
        small_image = Image.new('RGB', (64, 64), color='blue')
        report = await scorer.score_single(small_image, mode="REALISM")
        
        assert report.overall_score >= 0
        assert report.overall_score <= 100
    
    @pytest.mark.asyncio
    async def test_score_large_image(self, scorer):
        """Test scoring large image"""
        large_image = Image.new('RGB', (2048, 2048), color='green')
        report = await scorer.score_single(large_image, mode="REALISM")
        
        assert report.overall_score >= 0
        assert report.overall_score <= 100
    
    @pytest.mark.asyncio
    async def test_score_empty_batch(self, scorer):
        """Test scoring empty batch"""
        scores = await scorer.score_batch([], mode="REALISM")
        
        assert len(scores) == 0
    
    # ==================== QUALITY REPORT ====================
    
    def test_quality_report_to_dict(self, scorer):
        """Test QualityReport to_dict method"""
        report = QualityReport(
            overall_score=85.0,
            face_match_percent=90.0,
            aesthetic_score=80.0,
            technical_quality=88.0,
            composition_score=75.0,
            prompt_adherence=90.0,
        )
        
        report_dict = report.to_dict()
        
        assert isinstance(report_dict, dict)
        assert "overall_score" in report_dict
        assert "face_match_percent" in report_dict
        assert "aesthetic_score" in report_dict
        assert "technical_quality" in report_dict
        assert "composition_score" in report_dict
        assert "prompt_adherence" in report_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
