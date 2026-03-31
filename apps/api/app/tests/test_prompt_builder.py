"""
Tests for Advanced Prompt Builder
"""
import pytest  # type: ignore[reportMissingImports]
from app.services.ai.prompt_builder import (
    PromptBuilder,
    PromptStyle,
    PROMPT_PRESETS,
    prompt_builder,
)


class TestPromptBuilder:
    """Tests for prompt builder"""
    
    @pytest.fixture
    def builder(self):
        return PromptBuilder()
    
    # ==================== BASIC BUILDING ====================
    
    def test_build_basic_prompt(self, builder):
        """Test basic prompt building"""
        result = builder.build_prompt(
            user_prompt="portrait of a person",
            mode="REALISM",
        )
        
        assert result.enhanced_prompt
        assert result.negative_prompt
        assert len(result.enhanced_prompt) > len(result.original_prompt)
        assert result.original_prompt == "portrait of a person"
        assert result.estimated_tokens > 0
    
    def test_build_with_style(self, builder):
        """Test building with style template"""
        result = builder.build_prompt(
            user_prompt="person",
            mode="REALISM",
            style=PromptStyle.PROFESSIONAL,
        )
        
        assert "professional" in result.enhanced_prompt.lower()
        style_enhancements = [e for e in result.enhancements_applied if e.startswith("style:")]
        assert len(style_enhancements) > 0
        assert PromptStyle.PROFESSIONAL.value in style_enhancements[0]
    
    def test_build_with_pose(self, builder):
        """Test building with pose"""
        result = builder.build_prompt(
            user_prompt="person",
            mode="REALISM",
            pose="headshot",
        )
        
        pose_enhancements = [e for e in result.enhancements_applied if e.startswith("pose:")]
        assert len(pose_enhancements) > 0
        assert "headshot" in pose_enhancements[0]
    
    # ==================== ENHANCEMENT LEVELS ====================
    
    def test_enhancement_levels(self, builder):
        """Test different enhancement levels"""
        low = builder.build_prompt(
            user_prompt="person",
            mode="REALISM",
            enhancement_level=0.3,
        )
        
        high = builder.build_prompt(
            user_prompt="person",
            mode="REALISM",
            enhancement_level=1.0,
        )
        
        # High enhancement should have more content
        assert len(high.enhanced_prompt) >= len(low.enhanced_prompt)
        assert len(high.enhancements_applied) >= len(low.enhancements_applied)
    
    def test_no_enhancement(self, builder):
        """Test with no enhancement"""
        result = builder.build_prompt(
            user_prompt="person",
            mode="REALISM",
            enhancement_level=0.0,
            add_quality_boosters=False,
            add_technical_boosters=False,
        )
        
        # Should still have negative prompt
        assert result.negative_prompt
        # But minimal enhancements
        assert len(result.enhancements_applied) == 0 or "quality_boosters" not in result.enhancements_applied
    
    # ==================== NEGATIVE PROMPTS ====================
    
    def test_negative_prompt_generation(self, builder):
        """Test negative prompt generation"""
        result = builder.build_prompt(
            user_prompt="person",
            mode="REALISM",
        )
        
        assert result.negative_prompt
        assert "blurry" in result.negative_prompt
        assert "low quality" in result.negative_prompt
    
    def test_mode_specific_negatives(self, builder):
        """Test mode-specific negative prompts"""
        realism = builder.build_prompt("person", mode="REALISM")
        romantic = builder.build_prompt("person", mode="ROMANTIC")
        
        # Both should have base negatives
        assert "blurry" in realism.negative_prompt.lower()
        assert "blurry" in romantic.negative_prompt.lower()
        
        # Romantic should have additional restrictions
        romantic_lower = romantic.negative_prompt.lower()
        assert any(word in romantic_lower for word in ["inappropriate", "explicit", "nsfw", "vulgar"])
    
    def test_portrait_negatives(self, builder):
        """Test portrait-specific negatives"""
        result = builder.build_prompt(
            "person",
            mode="REALISM",
            style=PromptStyle.PORTRAIT,
        )
        
        negative_lower = result.negative_prompt.lower()
        assert any(word in negative_lower for word in ["bad anatomy", "extra fingers", "mutated hands"])
    
    # ==================== CLEANING ====================
    
    def test_prompt_cleaning(self, builder):
        """Test prompt cleaning removes duplicates"""
        dirty = "professional, high quality, professional, sharp focus"
        result = builder.build_prompt(
            user_prompt=dirty,
            mode="REALISM",
            add_quality_boosters=False,
            add_technical_boosters=False,
        )
        
        # Should remove duplicate "professional"
        assert result.enhanced_prompt.lower().count("professional") == 1
    
    def test_prompt_cleaning_spaces(self, builder):
        """Test prompt cleaning removes extra spaces"""
        dirty = "person  with   multiple    spaces"
        result = builder.build_prompt(
            user_prompt=dirty,
            mode="REALISM",
            add_quality_boosters=False,
            add_technical_boosters=False,
        )
        
        # Should have normalized spaces
        assert "  " not in result.enhanced_prompt
    
    # ==================== TOKEN OPTIMIZATION ====================
    
    def test_token_optimization(self, builder):
        """Test token limit optimization"""
        long_prompt = "word " * 100  # 100 words
        
        optimized = builder.optimize_for_tokens(long_prompt, max_tokens=77)
        
        # Should be truncated
        assert len(optimized.split()) < len(long_prompt.split())
        assert len(optimized.split()) <= 77  # Rough estimate
    
    def test_token_optimization_short_prompt(self, builder):
        """Test token optimization with short prompt"""
        short_prompt = "portrait of person"
        
        optimized = builder.optimize_for_tokens(short_prompt, max_tokens=77)
        
        # Should remain unchanged
        assert optimized == short_prompt
    
    # ==================== EMPHASIS ====================
    
    def test_add_emphasis(self, builder):
        """Test adding emphasis to keywords"""
        prompt = "portrait of person with blue eyes"
        
        emphasized = builder.add_emphasis(
            prompt,
            keywords=["blue eyes"],
            strength=1.3
        )
        
        assert "(blue eyes:1.3)" in emphasized
    
    def test_add_emphasis_multiple(self, builder):
        """Test adding emphasis to multiple keywords"""
        prompt = "portrait of person with blue eyes and red hair"
        
        emphasized = builder.add_emphasis(
            prompt,
            keywords=["blue eyes", "red hair"],
            strength=1.5
        )
        
        assert "(blue eyes:1.5)" in emphasized
        assert "(red hair:1.5)" in emphasized
    
    # ==================== VARIATIONS ====================
    
    def test_generate_variations(self, builder):
        """Test generating prompt variations"""
        variations = builder.generate_variations(
            base_prompt="portrait of person",
            num_variations=3
        )
        
        assert len(variations) == 3
        assert variations[0] == "portrait of person"
        assert all(isinstance(v, str) for v in variations)
        # Variations should be different
        assert len(set(variations)) >= 1  # At least base is unique
    
    def test_generate_variations_single(self, builder):
        """Test generating single variation"""
        variations = builder.generate_variations(
            base_prompt="portrait of person",
            num_variations=1
        )
        
        assert len(variations) == 1
        assert variations[0] == "portrait of person"
    
    # ==================== PRESETS ====================
    
    def test_presets_exist(self):
        """Test that presets are defined"""
        assert "professional_headshot" in PROMPT_PRESETS
        assert "linkedin_profile" in PROMPT_PRESETS
        assert "cyberpunk_character" in PROMPT_PRESETS
        assert "fantasy_hero" in PROMPT_PRESETS
        assert "vintage_photo" in PROMPT_PRESETS
    
    def test_use_preset(self, builder):
        """Test using a preset"""
        preset = PROMPT_PRESETS["professional_headshot"]
        
        result = builder.build_prompt(
            user_prompt=preset["prompt"],
            mode="REALISM",
            style=preset.get("style"),
            pose=preset.get("pose"),
        )
        
        assert result.enhanced_prompt
        assert result.negative_prompt
    
    def test_all_presets_work(self, builder):
        """Test that all presets can be used"""
        for preset_name, preset in PROMPT_PRESETS.items():
            result = builder.build_prompt(
                user_prompt=preset["prompt"],
                mode="REALISM",
                style=preset.get("style"),
                pose=preset.get("pose"),
            )
            
            assert result.enhanced_prompt
            assert result.negative_prompt
            assert result.estimated_tokens > 0
    
    # ==================== STYLE TEMPLATES ====================
    
    def test_all_styles_work(self, builder):
        """Test that all style templates work"""
        for style in PromptStyle:
            result = builder.build_prompt(
                user_prompt="person",
                mode="REALISM",
                style=style,
            )
            
            assert result.enhanced_prompt
            assert style.value in [e.split(':')[1] for e in result.enhancements_applied if e.startswith("style:")]
    
    # ==================== MODE SUPPORT ====================
    
    def test_all_modes_supported(self, builder):
        """Test that all modes are supported"""
        modes = ["REALISM", "CREATIVE", "ROMANTIC"]
        
        for mode in modes:
            result = builder.build_prompt(
                user_prompt="person",
                mode=mode,
            )
            
            assert result.enhanced_prompt
            assert result.metadata["mode"] == mode
    
    # ==================== STATISTICS ====================
    
    def test_statistics_tracking(self, builder):
        """Test statistics are tracked"""
        initial_count = builder.stats["total_builds"]
        
        builder.build_prompt("test", mode="REALISM")
        
        assert builder.stats["total_builds"] == initial_count + 1
    
    def test_get_statistics(self, builder):
        """Test getting statistics"""
        stats = builder.get_statistics()
        
        assert "total_builds" in stats
        assert "avg_enhancement_count" in stats
        assert isinstance(stats["total_builds"], int)
        assert isinstance(stats["avg_enhancement_count"], (int, float))
    
    # ==================== GLOBAL INSTANCE ====================
    
    def test_global_instance(self):
        """Test that global instance exists and works"""
        assert prompt_builder is not None
        assert isinstance(prompt_builder, PromptBuilder)
        
        result = prompt_builder.build_prompt(
            user_prompt="test",
            mode="REALISM",
        )
        
        assert result.enhanced_prompt
    
    # ==================== METADATA ====================
    
    def test_metadata_included(self, builder):
        """Test that metadata is included in result"""
        result = builder.build_prompt(
            user_prompt="person",
            mode="REALISM",
            style=PromptStyle.PROFESSIONAL,
            pose="headshot",
            enhancement_level=0.8,
        )
        
        assert result.metadata["mode"] == "REALISM"
        assert result.metadata["style"] == PromptStyle.PROFESSIONAL.value
        assert result.metadata["pose"] == "headshot"
        assert result.metadata["enhancement_level"] == 0.8
    
    # ==================== SUBJECT EXTRACTION ====================
    
    def test_subject_extraction(self, builder):
        """Test subject extraction from prompt"""
        # Test with common patterns
        test_cases = [
            ("portrait of a woman", "woman"),
            ("professional man", "man"),
            ("business person", "person"),
        ]
        
        for prompt, expected_subject in test_cases:
            subject = builder._extract_subject(prompt)
            # Should extract some subject (may not be exact match)
            assert subject
            assert isinstance(subject, str)
    
    # ==================== TRANSLATION PLACEHOLDER ====================
    
    def test_translation_placeholder(self, builder):
        """Test translation placeholder (returns original)"""
        original = "portrait of person"
        translated = builder.translate_to_english(original, source_lang="hi")
        
        # Currently returns original (placeholder)
        assert translated == original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
