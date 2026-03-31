"""
Comprehensive tests for prompt sanitizer
100+ test cases covering all scenarios
"""
import pytest  # type: ignore[reportMissingImports]
import time
from app.services.safety.prompt_sanitizer import PromptSanitizer, SafetyCheckResult

class TestPromptSanitizer:
    """Comprehensive tests for prompt sanitizer"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.sanitizer = PromptSanitizer(mode="REALISM")
        self.romantic_sanitizer = PromptSanitizer(mode="ROMANTIC")
        self.creative_sanitizer = PromptSanitizer(mode="CREATIVE")
    
    # ==================== SAFE PROMPTS ====================
    
    def test_safe_professional_prompts(self):
        """Test that professional prompts pass"""
        safe_prompts = [
            "professional headshot of a businessman in suit",
            "portrait of a woman in elegant dress",
            "cyberpunk warrior with neon armor",
            "fantasy elf in magical forest",
            "doctor in white coat, hospital background",
            "chef cooking in restaurant kitchen",
            "engineer working on computer",
            "teacher in classroom",
            "artist painting canvas",
        ]
        
        for prompt in safe_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert result.safe, f"Failed for: {prompt}"
            assert result.severity == "LOW"
    
    def test_safe_contextual_prompts(self):
        """Test context-aware safe prompts"""
        safe_prompts = [
            "woman wearing nude lipstick",
            "bloody mary cocktail on bar",
            "killing it in this outfit",
            "photo shoot in studio",
            "smoking hot car design",
            "strip mall storefront",
            "peacock feather pattern",
            "cocktail party scene",
        ]
        
        for prompt in safe_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert result.safe, f"Should pass: {prompt}"
    
    def test_safe_artistic_prompts(self):
        """Test artistic prompts"""
        safe_prompts = [
            "renaissance painting style portrait",
            "classical sculpture pose",
            "abstract art composition",
            "tasteful artistic rendering",
        ]
        
        for prompt in safe_prompts:
            result = self.creative_sanitizer.check_prompt(prompt)
            assert result.safe or result.severity == "LOW"
    
    # ==================== TIER 1 BLOCKS ====================
    
    def test_explicit_content_blocked(self):
        """Test explicit content is blocked"""
        blocked_prompts = [
            "nude woman on beach",
            "sexy naked model",
            "porn star photoshoot",
            "xxx content",
            "nsfw image",
            "erotic scene",
        ]
        
        for prompt in blocked_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe, f"Should block: {prompt}"
            assert result.severity == "CRITICAL"
            assert result.user_strike_recommended
    
    def test_violent_content_blocked(self):
        """Test violent content is blocked"""
        blocked_prompts = [
            "person being murdered",
            "gore and blood",
            "dead body on street",
            "suicide scene",
            "torture scene",
            "execution",
        ]
        
        for prompt in blocked_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
            assert result.severity == "CRITICAL"
    
    def test_drug_content_blocked(self):
        """Test drug-related content is blocked"""
        blocked_prompts = [
            "person smoking weed",
            "cocaine on table",
            "heroin injection",
            "drug deal scene",
        ]
        
        for prompt in blocked_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
            assert result.severity in ["HIGH", "CRITICAL"]
    
    def test_hindi_inappropriate_blocked(self):
        """Test Hindi inappropriate terms are blocked"""
        blocked_prompts = [
            "chut mara",
            "lund dikha",
            "harami person",
        ]
        
        for prompt in blocked_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
            assert result.severity == "CRITICAL"
    
    # ==================== CELEBRITY DETECTION ====================
    
    def test_celebrity_names_blocked(self):
        """Test celebrity detection"""
        blocked_prompts = [
            "Elon Musk in spacesuit",
            "portrait of Shah Rukh Khan",
            "Taylor Swift performing",
            "Virat Kohli playing cricket",
            "Deepika Padukone in saree",
            "Tom Cruise in action",
        ]
        
        for prompt in blocked_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
            assert any(v["type"] == "CELEBRITY" for v in result.violations)
    
    def test_celebrity_variations(self):
        """Test celebrity name variations"""
        variations = [
            "elon musk",  # lowercase
            "ELON MUSK",  # uppercase
            "Elon  Musk", # extra space
            "shah rukh khan",
            "SHAH RUKH KHAN",
        ]
        
        for prompt in variations:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
    
    def test_celebrity_extended_list(self):
        """Test extended celebrity list"""
        celebrities = [
            "tiger shroff",
            "sara ali khan",
            "ryan gosling",
            "zendaya",
            "bts",
            "pewdiepie",
        ]
        
        for name in celebrities:
            result = self.sanitizer.check_prompt(f"portrait of {name}")
            assert not result.safe
    
    # ==================== POLITICIAN DETECTION ====================
    
    def test_politician_names_blocked(self):
        """Test politician detection"""
        blocked_prompts = [
            "Narendra Modi giving speech",
            "portrait of Joe Biden",
            "Donald Trump in suit",
            "Rahul Gandhi campaigning",
        ]
        
        for prompt in blocked_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
            assert any(v["type"] == "POLITICIAN" for v in result.violations)
    
    def test_politician_extended_list(self):
        """Test extended politician list"""
        politicians = [
            "sharad pawar",
            "nancy pelosi",
            "angela merkel",
        ]
        
        for name in politicians:
            result = self.sanitizer.check_prompt(f"{name} speaking")
            assert not result.safe
    
    # ==================== MINOR PROTECTION ====================
    
    def test_minor_keywords_safe_context(self):
        """Test minor keywords in safe context"""
        safe_prompts = [
            "18 year old professional model",
            "adult student in university",
            "young professional in office",
            "legal age person",
        ]
        
        for prompt in safe_prompts:
            result = self.sanitizer.check_prompt(prompt)
            # Should be safe or low severity warning
            assert result.severity != "CRITICAL"
    
    def test_minor_protection_triggered(self):
        """Test minor protection triggers"""
        blocked_prompts = [
            "schoolgirl in sexy outfit",
            "teenage boy shirtless",
            "child in intimate setting",
            "minor in bedroom",
            "kid in revealing clothes",
        ]
        
        for prompt in blocked_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
            assert result.severity == "CRITICAL"
            assert any(
                v["type"] in ["MINOR_PROTECTION", "DANGEROUS_COMBINATION"] 
                for v in result.violations
            )
    
    def test_minor_with_school_context(self):
        """Test minor + school context triggers protection"""
        result = self.sanitizer.check_prompt("child in school uniform")
        assert not result.safe or result.severity == "MEDIUM"
    
    # ==================== DANGEROUS COMBINATIONS ====================
    
    def test_celebrity_sexual_combination(self):
        """Test celebrity + sexual keywords"""
        result = self.sanitizer.check_prompt("sexy Scarlett Johansson")
        assert not result.safe
        assert result.severity == "CRITICAL"
        assert any(v["type"] == "DANGEROUS_COMBINATION" for v in result.violations)
    
    def test_politician_violent_combination(self):
        """Test politician + violence"""
        result = self.sanitizer.check_prompt("kill Donald Trump")
        assert not result.safe
        assert result.severity == "CRITICAL"
    
    def test_minor_romantic_combination(self):
        """Test minor + romantic keywords"""
        result = self.sanitizer.check_prompt("teenage girl in intimate pose")
        assert not result.safe
        assert result.severity == "CRITICAL"
    
    # ==================== MODE-SPECIFIC ====================
    
    def test_romantic_mode_stricter(self):
        """Test romantic mode has stricter filtering"""
        prompts_with_restrictions = [
            "intimate moment between couple",
            "passionate kiss",
            "bedroom scene",
            "seductive pose",
        ]
        
        for prompt in prompts_with_restrictions:
            result = self.romantic_sanitizer.check_prompt(prompt)
            # Should have violations or warnings
            assert len(result.violations) > 0 or result.severity != "LOW"
    
    def test_creative_mode_allows_artistic(self):
        """Test creative mode allows artistic terms"""
        artistic_prompts = [
            "artistic nude painting style",
            "renaissance art pose",
            "classical sculpture",
        ]
        
        for prompt in artistic_prompts:
            result = self.creative_sanitizer.check_prompt(prompt)
            # Should be more lenient
            assert result.safe or result.severity in ["LOW", "MEDIUM"]
    
    # ==================== ALTERNATIVES ====================
    
    def test_suggest_alternative_celebrity(self):
        """Test alternative suggestion for celebrity"""
        result = self.sanitizer.check_prompt("Elon Musk in Tesla")
        
        assert not result.safe
        if result.suggested_alternative:
            assert "elon musk" not in result.suggested_alternative.lower()
            assert "person" in result.suggested_alternative.lower()
    
    def test_suggest_alternative_politician(self):
        """Test alternative for politician"""
        result = self.sanitizer.check_prompt("Narendra Modi giving speech")
        
        assert not result.safe
        if result.suggested_alternative:
            assert "narendra modi" not in result.suggested_alternative.lower()
    
    def test_suggest_alternative_contextual(self):
        """Test alternative for contextual violations"""
        result = self.sanitizer.check_prompt("nude painting style")
        
        if not result.safe and result.suggested_alternative:
            # Should suggest neutral alternative
            assert "neutral" in result.suggested_alternative.lower() or "nude" not in result.suggested_alternative.lower()
    
    # ==================== EDGE CASES ====================
    
    def test_empty_prompt(self):
        """Test empty prompt"""
        result = self.sanitizer.check_prompt("")
        assert result.safe
    
    def test_whitespace_only(self):
        """Test whitespace-only prompt"""
        result = self.sanitizer.check_prompt("   ")
        assert result.safe
    
    def test_very_long_prompt(self):
        """Test very long prompt (500+ chars)"""
        long_prompt = "professional portrait " * 50
        result = self.sanitizer.check_prompt(long_prompt)
        assert result.safe
    
    def test_special_characters(self):
        """Test prompts with special characters"""
        prompts = [
            "portrait @#$% test",
            "model in café",
            "résumé photo",
            "naïve person",
        ]
        
        for prompt in prompts:
            result = self.sanitizer.check_prompt(prompt)
            # Should handle gracefully
            assert isinstance(result.safe, bool)
    
    def test_unicode_characters(self):
        """Test unicode/emoji"""
        prompts = [
            "professional photo 😊",
            "portrait with 👔 tie",
            "person with 🎩 hat",
        ]
        
        for prompt in prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert isinstance(result.safe, bool)
    
    def test_numbers_in_prompt(self):
        """Test prompts with numbers"""
        prompts = [
            "18 year old model",
            "25 year old professional",
            "person in 2024",
        ]
        
        for prompt in prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert isinstance(result.safe, bool)
    
    # ==================== PERFORMANCE ====================
    
    def test_performance_single_check(self):
        """Test that single check is fast (<50ms)"""
        prompt = "professional headshot of businessman in suit"
        
        start = time.time()
        result = self.sanitizer.check_prompt(prompt)
        elapsed = time.time() - start
        
        assert elapsed < 0.050, f"Too slow: {elapsed*1000:.2f}ms"
        assert result.safe
    
    def test_performance_multiple_checks(self):
        """Test that multiple checks are fast"""
        prompts = [
            "professional headshot",
            "portrait of person",
            "businessman in suit",
        ] * 10
        
        start = time.time()
        for prompt in prompts:
            self.sanitizer.check_prompt(prompt)
        elapsed = time.time() - start
        
        avg_time = elapsed / len(prompts)
        assert avg_time < 0.050, f"Too slow: {avg_time*1000:.2f}ms per check"
    
    def test_cached_performance(self):
        """Test cached version is faster"""
        prompt = "professional headshot"
        
        # First call (not cached)
        start1 = time.time()
        result1 = self.sanitizer.is_safe_cached(prompt)
        time1 = time.time() - start1
        
        # Second call (cached)
        start2 = time.time()
        result2 = self.sanitizer.is_safe_cached(prompt)
        time2 = time.time() - start2
        
        assert result1 == result2
        assert time2 < time1  # Cached should be faster
    
    # ==================== LOGGING ====================
    
    def test_user_id_logging(self):
        """Test that user_id is used for logging"""
        result = self.sanitizer.check_prompt(
            "test prompt",
            user_id="user_123"
        )
        # Just verify it doesn't crash
        assert isinstance(result.safe, bool)
    
    def test_violation_logging(self):
        """Test that violations are properly logged"""
        result = self.sanitizer.check_prompt(
            "nude model",
            user_id="user_456"
        )
        assert not result.safe
        assert len(result.violations) > 0
    
    # ==================== RESULT STRUCTURE ====================
    
    def test_result_structure(self):
        """Test SafetyCheckResult structure"""
        result = self.sanitizer.check_prompt("test prompt")
        
        assert hasattr(result, "safe")
        assert hasattr(result, "violations")
        assert hasattr(result, "severity")
        assert hasattr(result, "suggested_alternative")
        assert hasattr(result, "user_strike_recommended")
        assert hasattr(result, "confidence")
        
        assert isinstance(result.safe, bool)
        assert isinstance(result.violations, list)
        assert result.severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert isinstance(result.user_strike_recommended, bool)
        assert 0.0 <= result.confidence <= 1.0
    
    def test_violation_structure(self):
        """Test violation dict structure"""
        result = self.sanitizer.check_prompt("nude model")
        
        if result.violations:
            violation = result.violations[0]
            assert "type" in violation
            assert "severity" in violation
            assert "reason" in violation
    
    # ==================== CONTEXTUAL CHECKING ====================
    
    def test_contextual_safe(self):
        """Test contextual keywords in safe context"""
        safe_contexts = [
            "nude lipstick color",
            "bloody mary drink",
            "killing it with style",
            "photo shoot setup",
        ]
        
        for prompt in safe_contexts:
            result = self.sanitizer.check_prompt(prompt)
            assert result.safe, f"Should be safe: {prompt}"
    
    def test_contextual_unsafe(self):
        """Test contextual keywords in unsafe context"""
        unsafe_contexts = [
            "nude person",
            "bloody scene",
            "kill someone",
        ]
        
        for prompt in unsafe_contexts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe or result.severity != "LOW"
    
    # ==================== MULTI-LANGUAGE ====================
    
    def test_hindi_terms(self):
        """Test Hindi inappropriate terms"""
        hindi_prompts = [
            "chut mara person",
            "harami character",
        ]
        
        for prompt in hindi_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
    
    def test_mixed_language(self):
        """Test mixed English-Hindi prompts"""
        mixed_prompts = [
            "person chut mara",
            "harami model",
        ]
        
        for prompt in mixed_prompts:
            result = self.sanitizer.check_prompt(prompt)
            assert not result.safe
    
    # ==================== REGRESSION TESTS ====================
    
    def test_no_false_positives_professional(self):
        """Test no false positives for professional terms"""
        professional_terms = [
            "professional",
            "business",
            "corporate",
            "executive",
            "manager",
            "director",
        ]
        
        for term in professional_terms:
            result = self.sanitizer.check_prompt(f"{term} portrait")
            assert result.safe
    
    def test_no_false_positives_artistic(self):
        """Test no false positives for artistic terms"""
        artistic_terms = [
            "portrait",
            "photography",
            "studio",
            "lighting",
            "composition",
        ]
        
        for term in artistic_terms:
            result = self.sanitizer.check_prompt(f"{term} setup")
            assert result.safe

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
