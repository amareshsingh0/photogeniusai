"""
Advanced Quality Scoring for Best-of-N selection.

Multi-criteria evaluation:
- Face match % (ArcFace similarity via InsightFace)
- Aesthetic score (CLIP-based)
- Technical quality (sharpness, artifacts, exposure)
- Composition analysis (rule of thirds, balance)
- Mode-specific weighting
"""

import torch  # type: ignore[reportMissingImports]
import numpy as np  # type: ignore[reportMissingImports]
from dataclasses import dataclass
from typing import Optional, List, Dict
from PIL import Image  # type: ignore[reportMissingImports]
import cv2  # type: ignore[reportMissingImports]
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Quality report card for a generated image."""
    overall_score: float           # 0-100
    face_match_percent: Optional[float]  # 0-100, None if no identity
    aesthetic_score: float         # 0-100 (CLIP-based)
    technical_quality: float       # 0-100
    composition_score: float       # 0-100
    prompt_adherence: float        # 0-100 (CLIP similarity)
    
    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "face_match_percent": self.face_match_percent,
            "aesthetic_score": self.aesthetic_score,
            "technical_quality": self.technical_quality,
            "composition_score": self.composition_score,
            "prompt_adherence": self.prompt_adherence,
        }


class QualityScorer:
    """
    Advanced multi-criteria quality scorer for generated images.
    
    Evaluates:
    1. Face Match: ArcFace similarity to reference embedding
    2. Aesthetic: CLIP-based aesthetic quality assessment
    3. Technical: Sharpness, noise, exposure, color balance
    4. Composition: Rule of thirds, balance, center focus
    5. Prompt Adherence: CLIP similarity to prompt (optional)
    
    Features:
    - Mode-specific weighting
    - Batch processing with async optimization
    - Graceful degradation when models unavailable
    - Performance optimizations
    """
    
    # Mode-specific weights
    SCORE_WEIGHTS = {
        "REALISM": {
            "face_match": 0.50,
            "aesthetic": 0.25,
            "technical": 0.20,
            "composition": 0.05,
        },
        "CREATIVE": {
            "face_match": 0.30,
            "aesthetic": 0.45,
            "technical": 0.15,
            "composition": 0.10,
        },
        "ROMANTIC": {
            "face_match": 0.40,
            "aesthetic": 0.35,
            "technical": 0.15,
            "composition": 0.10,
        },
    }
    
    def __init__(self):
        """Initialize quality scorer with models"""
        logger.info("Initializing Advanced Quality Scorer...")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Initialize face analyzer (InsightFace/ArcFace)
        self.face_analyzer = None
        try:
            from insightface.app import FaceAnalysis  # type: ignore[reportMissingImports]
            self.face_analyzer = FaceAnalysis(name='buffalo_l')
            self.face_analyzer.prepare(ctx_id=0 if self.device == "cuda" else -1, det_size=(640, 640))
            logger.info("✓ Face analyzer (ArcFace) loaded")
        except Exception as e:
            logger.warning(f"Face analyzer not available: {e}")
            self.face_analyzer = None
        
        # Initialize CLIP model for aesthetic and prompt adherence
        self.clip_model = None
        self.clip_preprocess = None
        self._clip_module = None
        try:
            import clip  # type: ignore[reportMissingImports]
            self._clip_module = clip
            self.clip_model, self.clip_preprocess = clip.load(
                "ViT-B/32",
                device=self.device
            )
            self.clip_model.eval()
            logger.info("✓ CLIP model loaded")
        except Exception as e:
            logger.warning(f"CLIP model not available: {e}")
            self.clip_model = None
            self.clip_preprocess = None
            self._clip_module = None
        
        # Cache for performance
        self._clip_cache = {}
        
        logger.info("[OK] Quality Scorer initialized")
    
    async def score_image(
        self,
        image: Image.Image,
        reference_embedding: Optional[np.ndarray] = None,
        mode: str = "REALISM",
    ) -> Dict[str, float]:
        """
        Score single image (simplified API)
        
        Args:
            image: PIL Image to score
            reference_embedding: Reference face embedding
            mode: Generation mode
            
        Returns:
            Dict with all scores (face_match_score, aesthetic_score, technical_score, composition_score, total_score)
        """
        # Use score_single internally and convert to dict
        report = await self.score_single(
            image=image,
            reference_embedding=reference_embedding,
            mode=mode,
        )
        
        # Convert to simple dict format
        scores = {
            "face_match_score": report.face_match_percent if report.face_match_percent is not None else 50.0,
            "aesthetic_score": report.aesthetic_score,
            "technical_score": report.technical_quality,
            "composition_score": report.composition_score,
            "total_score": report.overall_score,
        }
        
        return scores
    
    async def score_batch(
        self,
        images: List[Image.Image],
        reference_embedding: Optional[np.ndarray] = None,
        mode: str = "REALISM",
        prompt: Optional[str] = None,
    ) -> List[Dict[str, float]]:
        """
        Score a batch of images with parallel processing
        
        Args:
            images: List of PIL Images
            reference_embedding: Optional face embedding for identity matching
            mode: Generation mode (affects scoring weights)
            prompt: Optional prompt for adherence scoring
            
        Returns:
            List of score dictionaries
        """
        # Process in parallel batches for performance
        batch_size = 4  # Process 4 images at a time
        
        all_scores = []
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            tasks = [
                self.score_single(
                    image=img,
                    reference_embedding=reference_embedding,
                    mode=mode,
                    prompt=prompt,
                )
                for img in batch
            ]
            batch_reports = await asyncio.gather(*tasks)
            
            # Convert to dict format
            for report in batch_reports:
                all_scores.append({
                    "total_score": report.overall_score,
                    "face_match": report.face_match_percent or 0.0,
                    "aesthetic": report.aesthetic_score,
                    "technical": report.technical_quality,
                    "composition": report.composition_score,
                    "prompt_adherence": report.prompt_adherence,
                })
        
        return all_scores
    
    async def score_single(
        self,
        image: Image.Image,
        reference_embedding: Optional[np.ndarray] = None,
        mode: str = "REALISM",
        prompt: Optional[str] = None,
    ) -> QualityReport:
        """
        Score a single image on all criteria
        
        Args:
            image: PIL Image
            reference_embedding: Optional face embedding for identity matching
            mode: Generation mode
            prompt: Optional prompt for adherence scoring
            
        Returns:
            QualityReport with all scores
        """
        # Calculate individual scores in parallel where possible
        face_match_task = self._score_face_match(image, reference_embedding)
        aesthetic_task = self._score_aesthetic(image)
        technical_task = self._score_technical(image)
        composition_task = self._score_composition(image)
        prompt_adherence_task = self._score_prompt_adherence(image, prompt)
        
        # Wait for all scores
        face_match, aesthetic, technical, composition, prompt_adherence = await asyncio.gather(
            face_match_task,
            aesthetic_task,
            technical_task,
            composition_task,
            prompt_adherence_task,
        )
        
        # Calculate weighted overall score based on mode
        weights = self._get_mode_weights(mode)
        
        # Build weighted score
        components = []
        if face_match is not None:
            components.append(face_match * weights["face_match"])
        else:
            # If no face match, redistribute weights
            remaining_weight = weights["face_match"]
            weights["aesthetic"] += remaining_weight * 0.5
            weights["technical"] += remaining_weight * 0.3
            weights["composition"] += remaining_weight * 0.2
        
        components.append(aesthetic * weights["aesthetic"])
        components.append(technical * weights["technical"])
        components.append(composition * weights["composition"])
        
        # Normalize by sum of used weights
        total_weight = sum(w for k, w in weights.items() if k != "face_match" or face_match is not None)
        overall_score = sum(components) / total_weight if total_weight > 0 else 0
        
        return QualityReport(
            overall_score=overall_score,
            face_match_percent=face_match,
            aesthetic_score=aesthetic,
            technical_quality=technical,
            composition_score=composition,
            prompt_adherence=prompt_adherence,
        )
    
    def _get_mode_weights(self, mode: str) -> Dict[str, float]:
        """Get scoring weights for mode"""
        return self.SCORE_WEIGHTS.get(mode.upper(), self.SCORE_WEIGHTS["REALISM"])
    
    async def _score_face_match(
        self,
        image: Image.Image,
        reference_embedding: Optional[np.ndarray]
    ) -> Optional[float]:
        """
        Score face similarity to reference using ArcFace (InsightFace)
        
        Returns:
            Face match score 0-100, or None if no reference
        """
        if reference_embedding is None:
            return None
        
        if self.face_analyzer is None:
            logger.debug("Face analyzer not available, skipping face match")
            return None
        
        try:
            # Convert PIL to numpy for InsightFace
            img_array = np.array(image.convert("RGB"))
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # Detect faces
            faces = self.face_analyzer.get(img_array)
            
            if not faces or len(faces) == 0:
                # No face detected - penalize heavily
                logger.debug("No face detected in image")
                return 20.0
            
            # Get largest face (most prominent)
            # bbox format: [x1, y1, x2, y2]
            largest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            
            # Get normalized embedding (ArcFace)
            generated_embedding = largest_face.normed_embedding
            
            # Ensure embeddings are numpy arrays
            if not isinstance(generated_embedding, np.ndarray):
                generated_embedding = np.array(generated_embedding)
            if not isinstance(reference_embedding, np.ndarray):
                reference_embedding = np.array(reference_embedding)
            
            # Normalize embeddings (should already be normalized, but ensure)
            generated_embedding = generated_embedding / (np.linalg.norm(generated_embedding) + 1e-8)
            reference_embedding = reference_embedding / (np.linalg.norm(reference_embedding) + 1e-8)
            
            # Calculate cosine similarity (dot product of normalized vectors)
            similarity = np.dot(generated_embedding, reference_embedding)
            
            # ArcFace similarity typically ranges from ~0.3 (different person) to ~0.9+ (same person)
            # Map to 0-100 scale:
            # 0.3 = 0, 0.6 = 50, 0.9 = 100
            # Using a more nuanced mapping
            if similarity < 0.3:
                score = 0.0
            elif similarity < 0.6:
                # Linear mapping from 0.3 to 0.6 -> 0 to 50
                score = ((similarity - 0.3) / 0.3) * 50
            else:
                # Linear mapping from 0.6 to 0.9 -> 50 to 100
                score = 50 + ((similarity - 0.6) / 0.3) * 50
                score = min(100, score)  # Cap at 100
            
            return float(score)
            
        except Exception as e:
            logger.error(f"Face match scoring failed: {e}", exc_info=True)
            return None
    
    async def _score_aesthetic(self, image: Image.Image) -> float:
        """
        Score aesthetic quality using CLIP
        
        Returns:
            Aesthetic score 0-100
        """
        if self.clip_model is None:
            return await self._score_aesthetic_simple(image)
        
        try:
            # Preprocess image
            image_tensor = self.clip_preprocess(image).unsqueeze(0).to(self.device)
            
            # Define aesthetic prompts (positive and negative)
            positive_prompts = [
                "a high quality professional photograph",
                "a beautiful artistic image",
                "an aesthetically pleasing picture",
                "a well-composed photograph",
                "a visually appealing image",
            ]
            
            negative_prompts = [
                "a low quality photograph",
                "an ugly amateur picture",
                "a poorly composed image",
                "a blurry distorted photo",
                "an unappealing image",
            ]
            
            # Encode image
            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
                # Score against positive prompts
                positive_scores = []
                for prompt in positive_prompts:
                    text = self._clip_module.tokenize([prompt]).to(self.device)
                    text_features = self.clip_model.encode_text(text)
                    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                    
                    similarity = (image_features @ text_features.T).item()
                    positive_scores.append(similarity)
                
                # Score against negative prompts
                negative_scores = []
                for prompt in negative_prompts:
                    text = self._clip_module.tokenize([prompt]).to(self.device)
                    text_features = self.clip_model.encode_text(text)
                    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                    
                    similarity = (image_features @ text_features.T).item()
                    negative_scores.append(similarity)
            
            # Calculate final score
            avg_positive = np.mean(positive_scores)
            avg_negative = np.mean(negative_scores)
            
            # Score = positive - negative, normalized to 0-100
            # CLIP similarities typically range from -0.5 to 0.5
            # We want to map this to 0-100
            raw_score = avg_positive - avg_negative
            # Normalize: assume range is roughly -0.5 to 0.5
            score = max(0, min(100, (raw_score + 0.5) * 100))
            
            return float(score)
            
        except Exception as e:
            logger.error(f"CLIP aesthetic scoring failed: {e}", exc_info=True)
            return await self._score_aesthetic_simple(image)
    
    async def _score_aesthetic_simple(self, image: Image.Image) -> float:
        """
        Simple aesthetic scoring without CLIP (fallback)
        
        Uses basic heuristics:
        - Color variety
        - Contrast
        - Saturation balance
        """
        try:
            # Convert to numpy
            img_array = np.array(image.convert("RGB"))
            
            # Convert to HSV
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # 1. Color variety (higher is better, but not too high)
            color_variety = np.std(hsv[:, :, 0]) / 180.0 * 100
            # Penalize if too uniform or too chaotic
            if color_variety < 20:
                color_variety = color_variety * 0.5  # Too uniform
            elif color_variety > 80:
                color_variety = 100 - (color_variety - 80) * 0.5  # Too chaotic
            
            # 2. Contrast (higher is better, but moderate)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            contrast = gray.std() / 128.0 * 100
            contrast = min(100, contrast)  # Cap at 100
            
            # 3. Saturation (moderate is better)
            saturation = hsv[:, :, 1].mean() / 255.0 * 100
            # Ideal saturation around 40-60%
            if 40 <= saturation <= 60:
                saturation_score = 100
            else:
                saturation_score = 100 - abs(saturation - 50) * 2
            
            # 4. Brightness balance
            brightness = hsv[:, :, 2].mean() / 255.0 * 100
            # Ideal brightness around 50-70%
            if 50 <= brightness <= 70:
                brightness_score = 100
            else:
                brightness_score = 100 - abs(brightness - 60) * 1.5
            
            # Weighted average
            score = (
                color_variety * 0.25 +
                contrast * 0.30 +
                saturation_score * 0.25 +
                brightness_score * 0.20
            )
            
            return min(100, max(0, float(score)))
            
        except Exception as e:
            logger.error(f"Simple aesthetic scoring failed: {e}", exc_info=True)
            return 50.0
    
    async def _score_technical(self, image: Image.Image) -> float:
        """
        Score technical quality (sharpness, noise, exposure, artifacts)
        
        Returns:
            Technical quality score 0-100
        """
        try:
            # Convert to numpy
            img_array = np.array(image.convert("RGB"))
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # 1. Sharpness (Laplacian variance)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            # Normalize: good images typically have 500-2000
            if laplacian_var < 100:
                sharpness_score = 0
            elif laplacian_var < 500:
                sharpness_score = (laplacian_var - 100) / 400 * 50
            elif laplacian_var < 2000:
                sharpness_score = 50 + (laplacian_var - 500) / 1500 * 50
            else:
                sharpness_score = 100
            
            # 2. Noise level (lower is better)
            # Use local standard deviation as proxy
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            noise = np.abs(gray.astype(float) - blurred.astype(float)).mean()
            # Normalize: good images have noise < 5
            noise_score = max(0, 100 - noise * 10)
            
            # 3. Exposure (neither over nor under)
            mean_brightness = gray.mean()
            ideal_brightness = 128
            exposure_score = 100 - abs(mean_brightness - ideal_brightness) / ideal_brightness * 100
            exposure_score = max(0, exposure_score)
            
            # 4. Color balance
            color_balance = self._check_color_balance(img_array)
            
            # 5. Artifact detection (check for compression artifacts)
            artifacts = self._detect_artifacts(img_array)
            
            # Weighted average
            technical_score = (
                sharpness_score * 0.35 +
                noise_score * 0.25 +
                exposure_score * 0.20 +
                color_balance * 0.15 +
                artifacts * 0.05
            )
            
            return min(100, max(0, float(technical_score)))
            
        except Exception as e:
            logger.error(f"Technical scoring failed: {e}", exc_info=True)
            return 50.0
    
    def _check_color_balance(self, img_array: np.ndarray) -> float:
        """
        Check color balance (no extreme color cast)
        
        Returns:
            Color balance score 0-100
        """
        try:
            # Calculate mean for each channel
            r_mean = img_array[:, :, 0].mean()
            g_mean = img_array[:, :, 1].mean()
            b_mean = img_array[:, :, 2].mean()
            
            # Calculate max deviation from average
            avg_mean = (r_mean + g_mean + b_mean) / 3
            max_deviation = max(
                abs(r_mean - avg_mean),
                abs(g_mean - avg_mean),
                abs(b_mean - avg_mean)
            )
            
            # Score (lower deviation = better)
            # Good balance: deviation < 10
            if max_deviation < 10:
                score = 100
            elif max_deviation < 30:
                score = 100 - (max_deviation - 10) * 2
            else:
                score = max(0, 100 - (max_deviation - 30) * 1.5)
            
            return float(score)
            
        except Exception as e:
            logger.error(f"Color balance check failed: {e}")
            return 75.0
    
    def _detect_artifacts(self, img_array: np.ndarray) -> float:
        """
        Detect compression/encoding artifacts
        
        Returns:
            Artifact score 0-100 (higher = fewer artifacts)
        """
        try:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Check for block artifacts (JPEG compression)
            # Divide into 8x8 blocks and check variance
            block_size = 8
            h, w = gray.shape
            block_variances = []
            
            for i in range(0, h - block_size, block_size):
                for j in range(0, w - block_size, block_size):
                    block = gray[i:i+block_size, j:j+block_size]
                    block_variances.append(block.var())
            
            if not block_variances:
                return 100.0
            
            # High variance differences between blocks indicate artifacts
            variance_std = np.std(block_variances)
            # Normalize: low std = good, high std = artifacts
            if variance_std < 100:
                score = 100
            elif variance_std < 500:
                score = 100 - (variance_std - 100) / 4
            else:
                score = max(0, 100 - (variance_std - 500) / 10)
            
            return float(score)
            
        except Exception as e:
            logger.error(f"Artifact detection failed: {e}")
            return 85.0
    
    async def _score_composition(self, image: Image.Image) -> float:
        """
        Score composition quality
        
        Checks:
        - Rule of thirds
        - Balance (left vs right, top vs bottom)
        - Center focus (for portraits)
        
        Returns:
            Composition score 0-100
        """
        try:
            # Convert to numpy
            img_array = np.array(image.convert("RGB"))
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            height, width = gray.shape
            
            # 1. Rule of thirds
            # Divide image into 9 parts (3x3 grid)
            third_h = height // 3
            third_w = width // 3
            
            # Calculate interest (edge density) in each region
            thirds_interest = []
            for i in range(3):
                for j in range(3):
                    y_start = i * third_h
                    y_end = (i + 1) * third_h if i < 2 else height
                    x_start = j * third_w
                    x_end = (j + 1) * third_w if j < 2 else width
                    
                    region = gray[y_start:y_end, x_start:x_end]
                    edges = cv2.Canny(region, 50, 150)
                    interest = edges.sum() / (region.size + 1e-8)
                    thirds_interest.append(interest)
            
            # Good composition has interest at intersection points
            # (positions 1, 2, 5, 7 in 3x3 grid, 0-indexed)
            intersection_indices = [1, 2, 5, 7]
            intersection_interest = np.mean([thirds_interest[i] for i in intersection_indices])
            avg_interest = np.mean(thirds_interest)
            
            if avg_interest > 0:
                rule_of_thirds_score = min(100, (intersection_interest / avg_interest) * 60 + 40)
            else:
                rule_of_thirds_score = 50.0
            
            # 2. Balance (left vs right, top vs bottom)
            left_half = gray[:, :width//2]
            right_half = gray[:, width//2:]
            top_half = gray[:height//2, :]
            bottom_half = gray[height//2:, :]
            
            left_interest = cv2.Canny(left_half, 50, 150).sum()
            right_interest = cv2.Canny(right_half, 50, 150).sum()
            top_interest = cv2.Canny(top_half, 50, 150).sum()
            bottom_interest = cv2.Canny(bottom_half, 50, 150).sum()
            
            # Calculate balance ratios
            lr_balance = min(left_interest, right_interest) / max(left_interest, right_interest, 1)
            tb_balance = min(top_interest, bottom_interest) / max(top_interest, bottom_interest, 1)
            
            balance_score = ((lr_balance + tb_balance) / 2) * 100
            
            # 3. Center focus (for portraits - subject should be centered)
            center_h = slice(height//4, 3*height//4)
            center_w = slice(width//4, 3*width//4)
            center = gray[center_h, center_w]
            
            center_interest = cv2.Canny(center, 50, 150).sum() / (center.size + 1e-8)
            total_interest = cv2.Canny(gray, 50, 150).sum() / (gray.size + 1e-8)
            
            if total_interest > 0:
                center_focus_score = min(100, (center_interest / total_interest) * 80)
            else:
                center_focus_score = 50.0
            
            # Weighted average
            composition_score = (
                rule_of_thirds_score * 0.40 +
                balance_score * 0.35 +
                center_focus_score * 0.25
            )
            
            return min(100, max(0, float(composition_score)))
            
        except Exception as e:
            logger.error(f"Composition scoring failed: {e}", exc_info=True)
            return 60.0
    
    async def _score_prompt_adherence(self, image: Image.Image, prompt: Optional[str] = None) -> float:
        """
        Score prompt adherence using CLIP similarity
        
        Returns:
            Prompt adherence score 0-100, or default if no prompt
        """
        if prompt is None or self.clip_model is None:
            return 85.0  # Default score if no prompt or CLIP unavailable
        if self.clip_preprocess is None or self._clip_module is None:
            return 85.0
        try:
            # Preprocess image
            image_tensor = self.clip_preprocess(image).unsqueeze(0).to(self.device)
            
            # Encode image and prompt
            with torch.no_grad():
                image_features = self.clip_model.encode_image(image_tensor)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
                text = self._clip_module.tokenize([prompt]).to(self.device)
                text_features = self.clip_model.encode_text(text)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                
                # Calculate cosine similarity
                similarity = (image_features @ text_features.T).item()
            
            # CLIP similarities typically range from 0.2 to 0.4 for good matches
            # Map to 0-100 scale
            if similarity < 0.2:
                score = similarity / 0.2 * 50  # 0-50
            elif similarity < 0.4:
                score = 50 + (similarity - 0.2) / 0.2 * 50  # 50-100
            else:
                score = 100  # Cap at 100
            
            return max(0, min(100, float(score)))
            
        except Exception as e:
            logger.error(f"Prompt adherence scoring failed: {e}", exc_info=True)
            return 85.0


# Legacy function for backward compatibility
def score(image_url: str, prompt: str, identity_embedding: Optional[bytes] = None) -> QualityReport:
    """
    Score a generated image for quality (legacy function).
    
    Args:
        image_url: URL to the generated image
        prompt: Original prompt for CLIP similarity
        identity_embedding: Optional face embedding for match scoring
    
    Returns:
        QualityReport with all scores
    
    Note: This is a placeholder implementation.
    Use QualityScorer class for production use.
    """
    # Placeholder scores
    return QualityReport(
        overall_score=85.0,
        face_match_percent=92.0 if identity_embedding else None,
        aesthetic_score=75.0,
        technical_quality=88.0,
        composition_score=80.0,
        prompt_adherence=90.0,
    )


def select_best(candidates: list[tuple[str, QualityReport]]) -> tuple[str, QualityReport]:
    """
    Select the best image from N candidates.
    
    Args:
        candidates: List of (image_url, QualityReport) tuples
    
    Returns:
        Best (image_url, QualityReport) based on overall_score
    """
    return max(candidates, key=lambda x: x[1].overall_score)
