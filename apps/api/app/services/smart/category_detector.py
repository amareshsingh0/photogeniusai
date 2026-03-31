"""
Category Detector - Detects image category for better prompt optimization

Categories:
- portrait: People, faces, headshots
- landscape: Nature, scenery, outdoor
- product: Objects, items, commercial
- architecture: Buildings, structures
- food: Meals, dishes, cuisine
- animal: Pets, wildlife
- abstract: Patterns, geometric, design
- interior: Room, indoor spaces
- general: Default fallback
"""

from typing import Dict, List


class CategoryDetector:
    """AI-powered category detection for prompt optimization"""

    # Keywords for each category
    CATEGORIES: Dict[str, List[str]] = {
        'portrait': [
            'person', 'people', 'face', 'portrait', 'headshot',
            'selfie', 'man', 'woman', 'child', 'human', 'model',
            'actor', 'celebrity', 'character', 'businessman',
            'expression', 'smile', 'eyes', 'looking'
        ],
        'landscape': [
            'landscape', 'scenery', 'nature', 'outdoor', 'mountain',
            'valley', 'hill', 'forest', 'river', 'lake', 'ocean',
            'sea', 'beach', 'sky', 'sunset', 'sunrise', 'clouds',
            'horizon', 'vista', 'countryside', 'wilderness'
        ],
        'product': [
            'product', 'object', 'item', 'commercial', 'showcase',
            'bottle', 'package', 'box', 'gadget', 'device',
            'phone', 'watch', 'jewelry', 'cosmetic', 'perfume',
            'advertisement', 'catalog', 'ecommerce'
        ],
        'architecture': [
            'building', 'architecture', 'house', 'structure',
            'skyscraper', 'tower', 'bridge', 'monument', 'cathedral',
            'temple', 'castle', 'palace', 'facade', 'exterior',
            'modern', 'urban', 'city', 'downtown'
        ],
        'food': [
            'food', 'meal', 'dish', 'cuisine', 'cooking', 'recipe',
            'plate', 'restaurant', 'dessert', 'pizza', 'burger',
            'sushi', 'cake', 'bread', 'fruit', 'vegetable',
            'gourmet', 'delicious', 'appetizing'
        ],
        'animal': [
            'animal', 'pet', 'dog', 'cat', 'bird', 'wildlife',
            'horse', 'lion', 'tiger', 'elephant', 'wolf',
            'bear', 'deer', 'fox', 'rabbit', 'fish',
            'creature', 'mammal', 'reptile'
        ],
        'abstract': [
            'abstract', 'pattern', 'geometric', 'design', 'texture',
            'shapes', 'lines', 'circles', 'triangles', 'colors',
            'gradient', 'mandala', 'fractal', 'minimalist',
            'artistic', 'decorative', 'wallpaper'
        ],
        'interior': [
            'interior', 'room', 'indoor', 'living room', 'bedroom',
            'kitchen', 'bathroom', 'office', 'studio', 'loft',
            'furniture', 'decor', 'cozy', 'modern interior',
            'apartment', 'house interior', 'design interior'
        ]
    }

    DEFAULT_CATEGORY = 'general'

    def detect_category(self, prompt: str) -> str:
        """
        Detect image category from prompt

        Args:
            prompt: User's input prompt

        Returns:
            str: Detected category

        Example:
            >>> detector = CategoryDetector()
            >>> detector.detect_category("professional headshot")
            'portrait'
            >>> detector.detect_category("mountain landscape at sunset")
            'landscape'
            >>> detector.detect_category("delicious pizza on wooden table")
            'food'
        """
        if not prompt:
            return self.DEFAULT_CATEGORY

        prompt_lower = prompt.lower()

        # Score each category
        scores = {}
        for category, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            scores[category] = score

        # Get highest scoring category
        best_category = max(scores, key=scores.get)

        # If no keywords matched, return general
        if scores[best_category] == 0:
            return self.DEFAULT_CATEGORY

        return best_category

    def get_category_confidence(self, prompt: str) -> Dict[str, float]:
        """
        Get confidence scores for all categories

        Args:
            prompt: User's input prompt

        Returns:
            dict: Category names to confidence scores (0-1)
        """
        if not prompt:
            return {cat: 0.0 for cat in self.CATEGORIES.keys()}

        prompt_lower = prompt.lower()

        # Count matches
        scores = {}
        total_matches = 0

        for category, keywords in self.CATEGORIES.items():
            matches = sum(1 for kw in keywords if kw in prompt_lower)
            scores[category] = matches
            total_matches += matches

        # Normalize
        if total_matches == 0:
            return {cat: 0.0 for cat in self.CATEGORIES.keys()}

        return {
            cat: score / total_matches
            for cat, score in scores.items()
        }

    def get_matched_keywords(self, prompt: str, category: str) -> List[str]:
        """
        Get keywords that matched for a specific category

        Args:
            prompt: User's input prompt
            category: Category to check

        Returns:
            list: Matched keywords
        """
        if category not in self.CATEGORIES:
            return []

        prompt_lower = prompt.lower()
        return [
            kw for kw in self.CATEGORIES[category]
            if kw in prompt_lower
        ]

    def explain_detection(self, prompt: str) -> Dict:
        """
        Explain why a category was detected

        Args:
            prompt: User's input prompt

        Returns:
            dict: Detection explanation
        """
        detected_category = self.detect_category(prompt)
        confidences = self.get_category_confidence(prompt)
        matched_keywords = self.get_matched_keywords(prompt, detected_category)

        return {
            'detected_category': detected_category,
            'confidence': confidences.get(detected_category, 0.0),
            'matched_keywords': matched_keywords,
            'all_scores': confidences
        }


# Singleton instance
category_detector = CategoryDetector()
