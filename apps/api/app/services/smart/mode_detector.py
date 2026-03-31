"""
Mode Detector - AI automatically detects best generation mode from prompt

Modes:
- REALISM: Photorealistic images
- CINEMATIC: Movie-like, dramatic scenes
- CREATIVE: Artistic, imaginative
- FANTASY: Magical, mythical worlds
- ANIME: Anime/manga style
"""

from typing import Dict, List


class ModeDetector:
    """AI-powered mode detection from user prompts"""

    # Keywords for each mode
    MODES: Dict[str, List[str]] = {
        'REALISM': [
            'realistic', 'photorealistic', 'photo', 'portrait',
            'professional', 'headshot', 'real', 'natural',
            'photography', 'camera', 'lens', 'photograph',
            'studio', 'candid', 'documentary', 'journalist'
        ],
        'CINEMATIC': [
            'cinematic', 'movie', 'film', 'dramatic', 'epic',
            'hollywood', 'scene', 'shot', 'cinematography',
            'lighting', 'volumetric', 'moody', 'atmospheric',
            'blockbuster', 'thriller', 'noir'
        ],
        'CREATIVE': [
            'artistic', 'creative', 'imaginative', 'surreal',
            'abstract', 'unique', 'experimental', 'conceptual',
            'avant-garde', 'expressive', 'original', 'innovative'
        ],
        'FANTASY': [
            'fantasy', 'magical', 'mythical', 'dragon', 'wizard',
            'fairy', 'enchanted', 'mystical', 'ethereal', 'spell',
            'magic', 'sorcerer', 'witch', 'kingdom', 'castle',
            'medieval', 'legend', 'mythological'
        ],
        'ANIME': [
            'anime', 'manga', 'cartoon', 'animated', 'character',
            'kawaii', 'chibi', 'cel', 'cel-shaded', 'japanese',
            'studio ghibli', 'seinen', 'shonen', 'otaku'
        ]
    }

    # Default mode if no keywords match
    DEFAULT_MODE = 'REALISM'

    def detect_mode(self, prompt: str) -> str:
        """
        Analyze prompt and auto-select best generation mode

        Args:
            prompt: User's input prompt

        Returns:
            str: Detected mode (REALISM, CINEMATIC, CREATIVE, FANTASY, or ANIME)

        Example:
            >>> detector = ModeDetector()
            >>> detector.detect_mode("professional headshot of CEO")
            'REALISM'
            >>> detector.detect_mode("cinematic shot of warrior in battle")
            'CINEMATIC'
            >>> detector.detect_mode("anime girl with pink hair")
            'ANIME'
        """
        if not prompt:
            return self.DEFAULT_MODE

        prompt_lower = prompt.lower()

        # Score each mode based on keyword matches
        scores = {}
        for mode, keywords in self.MODES.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            scores[mode] = score

        # Get highest scoring mode
        best_mode = max(scores, key=scores.get)

        # If no keywords matched, default to REALISM
        if scores[best_mode] == 0:
            return self.DEFAULT_MODE

        return best_mode

    def get_mode_confidence(self, prompt: str) -> Dict[str, float]:
        """
        Get confidence scores for all modes

        Args:
            prompt: User's input prompt

        Returns:
            dict: Mode names to confidence scores (0-1)

        Example:
            >>> detector.get_mode_confidence("cinematic photo of a warrior")
            {
                'REALISM': 0.3,
                'CINEMATIC': 0.7,
                'CREATIVE': 0.0,
                'FANTASY': 0.2,
                'ANIME': 0.0
            }
        """
        if not prompt:
            return {mode: 0.0 for mode in self.MODES.keys()}

        prompt_lower = prompt.lower()

        # Count matches for each mode
        scores = {}
        total_matches = 0

        for mode, keywords in self.MODES.items():
            matches = sum(1 for kw in keywords if kw in prompt_lower)
            scores[mode] = matches
            total_matches += matches

        # Normalize to 0-1
        if total_matches == 0:
            return {mode: 0.0 for mode in self.MODES.keys()}

        return {
            mode: score / total_matches
            for mode, score in scores.items()
        }

    def explain_detection(self, prompt: str) -> Dict:
        """
        Explain why a mode was detected

        Args:
            prompt: User's input prompt

        Returns:
            dict: Detection explanation with matched keywords

        Example:
            >>> detector.explain_detection("anime girl with magical powers")
            {
                'detected_mode': 'ANIME',
                'confidence': 0.6,
                'matched_keywords': ['anime', 'magical'],
                'all_scores': {...}
            }
        """
        detected_mode = self.detect_mode(prompt)
        confidences = self.get_mode_confidence(prompt)

        # Find matched keywords for detected mode
        prompt_lower = prompt.lower()
        matched_keywords = [
            kw for kw in self.MODES[detected_mode]
            if kw in prompt_lower
        ]

        return {
            'detected_mode': detected_mode,
            'confidence': confidences[detected_mode],
            'matched_keywords': matched_keywords,
            'all_scores': confidences
        }


# Singleton instance
mode_detector = ModeDetector()
