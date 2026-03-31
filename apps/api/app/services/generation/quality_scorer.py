"""
Quality Scorer - Score and rank generated images

Adapted from ai-pipeline for AWS/FastAPI (no Modal dependencies)
"""

from typing import Dict, List, Optional
import base64
import io
from PIL import Image


class QualityScorer:
    """
    Score generated images for quality

    Metrics:
    - Aesthetic score (composition, lighting, colors)
    - Technical quality (sharpness, noise, artifacts)
    - Prompt adherence (how well it matches prompt)
    """

    def __init__(self):
        """Initialize quality scorer"""
        # TODO: Load quality assessment models when available
        self.aesthetic_model = None
        self.technical_model = None

    async def score_image(
        self,
        image_url: str,
        prompt: str,
        mode: str = 'REALISM'
    ) -> Dict:
        """
        Score a generated image

        Args:
            image_url: URL or base64 of image
            prompt: Original prompt
            mode: Generation mode

        Returns:
            dict: Quality scores
        """
        # Placeholder implementation
        # TODO: Implement actual quality scoring with models

        return {
            'overall_score': 0.85,
            'aesthetic_score': 0.88,
            'technical_score': 0.82,
            'prompt_adherence': 0.85,
            'composition': 0.87,
            'lighting': 0.89,
            'color_harmony': 0.86,
            'sharpness': 0.84,
            'noise_level': 0.90,
            'artifacts': 0.88
        }

    async def rank_images(
        self,
        images: List[Dict],
        prompt: str,
        mode: str = 'REALISM'
    ) -> List[Dict]:
        """
        Rank multiple images by quality

        Args:
            images: List of image dicts with 'url' or 'data'
            prompt: Original prompt
            mode: Generation mode

        Returns:
            list: Images sorted by quality (best first)
        """
        # Score each image
        scored_images = []
        for img in images:
            score = await self.score_image(
                image_url=img.get('url') or img.get('data'),
                prompt=prompt,
                mode=mode
            )
            scored_images.append({
                **img,
                'scores': score,
                'overall_score': score['overall_score']
            })

        # Sort by overall score
        scored_images.sort(key=lambda x: x['overall_score'], reverse=True)

        return scored_images

    def get_score_explanation(self, scores: Dict) -> str:
        """
        Get human-readable explanation of scores

        Args:
            scores: Score dict from score_image()

        Returns:
            str: Explanation
        """
        overall = scores['overall_score']

        if overall >= 0.9:
            quality = "Excellent"
        elif overall >= 0.8:
            quality = "Very Good"
        elif overall >= 0.7:
            quality = "Good"
        elif overall >= 0.6:
            quality = "Fair"
        else:
            quality = "Poor"

        explanation = f"{quality} quality image (score: {overall:.2f}). "

        # Highlight strengths
        strengths = []
        if scores.get('aesthetic_score', 0) >= 0.85:
            strengths.append("excellent composition")
        if scores.get('lighting', 0) >= 0.85:
            strengths.append("great lighting")
        if scores.get('sharpness', 0) >= 0.85:
            strengths.append("sharp details")

        if strengths:
            explanation += f"Strengths: {', '.join(strengths)}. "

        # Highlight weaknesses
        weaknesses = []
        if scores.get('noise_level', 1.0) < 0.7:
            weaknesses.append("some noise")
        if scores.get('artifacts', 1.0) < 0.7:
            weaknesses.append("minor artifacts")
        if scores.get('prompt_adherence', 0) < 0.7:
            weaknesses.append("could match prompt better")

        if weaknesses:
            explanation += f"Areas for improvement: {', '.join(weaknesses)}."

        return explanation


# Singleton instance
quality_scorer = QualityScorer()
