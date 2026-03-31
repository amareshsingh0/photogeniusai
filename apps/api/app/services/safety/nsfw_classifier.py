"""
Production-grade NSFW Classifier for PhotoGenius AI
Uses NudeNet with mode-specific thresholds and quarantine system
"""
import numpy as np  # type: ignore[reportMissingImports]
from PIL import Image  # type: ignore[reportMissingImports]
import io
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
from pathlib import Path
import json
from datetime import datetime, timedelta
import shutil

# NudeNet
from nudenet import NudeDetector  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

class SafetyAction(Enum):
    """Safety action to take"""
    ALLOW = "ALLOW"
    QUARANTINE = "QUARANTINE"
    BLOCK = "BLOCK"

@dataclass
class NSFWDetection:
    """Single NSFW detection result"""
    class_name: str
    confidence: float
    box: List[int]  # [x, y, width, height]

@dataclass
class NSFWCheckResult:
    """Complete NSFW check result"""
    action: SafetyAction
    nsfw_score: float  # 0-1
    detections: List[NSFWDetection]
    reasoning: str
    user_strike_recommended: bool
    metadata: Dict

class NSFWClassifier:
    """
    Production-grade NSFW classifier with mode-specific thresholds
    
    Uses NudeNet for detection with three-tier action system:
    - BLOCK: Definitely NSFW, delete immediately
    - QUARANTINE: Borderline, needs human review
    - ALLOW: Safe content
    """
    
    # ==================== THRESHOLDS BY MODE ====================
    THRESHOLDS = {
        "REALISM": {
            "BLOCK": 0.60,      # >= 0.60 = BLOCK
            "QUARANTINE": 0.40,  # 0.40-0.60 = QUARANTINE
            # < 0.40 = ALLOW
        },
        "CREATIVE": {
            "BLOCK": 0.70,
            "QUARANTINE": 0.50,
        },
        "ROMANTIC": {
            "BLOCK": 0.30,      # Strictest
            "QUARANTINE": 0.20,
        }
    }
    
    # ==================== BODY PART CATEGORIES ====================
    EXPOSED_PARTS = [
        "EXPOSED_ANUS",
        "EXPOSED_ARMPITS",
        "EXPOSED_BELLY",
        "EXPOSED_BREAST_F",
        "EXPOSED_BUTTOCKS",
        "EXPOSED_FEET",
        "EXPOSED_GENITALIA_F",
        "EXPOSED_GENITALIA_M",
    ]
    
    COVERED_PARTS = [
        "COVERED_BREAST_F",
        "COVERED_BUTTOCKS",
        "COVERED_GENITALIA_F",
        "COVERED_GENITALIA_M",
    ]
    
    # Critical parts that trigger instant block
    CRITICAL_PARTS = [
        "EXPOSED_ANUS",
        "EXPOSED_GENITALIA_F",
        "EXPOSED_GENITALIA_M",
    ]
    
    # High severity parts
    HIGH_SEVERITY_PARTS = [
        "EXPOSED_BREAST_F",
        "EXPOSED_BUTTOCKS",
    ]
    
    def __init__(self):
        """Initialize NSFW classifier"""
        logger.info("Initializing NSFW Classifier...")
        
        try:
            # Initialize NudeNet detector
            self.detector = NudeDetector()
            logger.info("✓ NudeNet detector loaded")
        except Exception as e:
            logger.error(f"Failed to load NudeNet: {e}")
            raise
        
        # Statistics
        self.stats = {
            "total_checked": 0,
            "blocked": 0,
            "quarantined": 0,
            "allowed": 0,
        }
    
    async def classify_image(
        self,
        image_path: str,
        mode: str,
        user_id: str,
        generation_id: str,
        threshold_override: Optional[Dict[str, float]] = None
    ) -> NSFWCheckResult:
        """
        Classify image for NSFW content
        
        Args:
            image_path: Path to image file or URL
            mode: Generation mode (REALISM/CREATIVE/ROMANTIC)
            user_id: User ID for logging
            generation_id: Generation ID for tracking
            threshold_override: Optional custom thresholds
            
        Returns:
            NSFWCheckResult with action and details
        """
        try:
            # Get thresholds
            thresholds = threshold_override or self.THRESHOLDS.get(
                mode.upper(),
                self.THRESHOLDS["REALISM"]
            )
            
            # Run detection (CPU-bound, run in executor)
            detections = await asyncio.to_thread(
                self._detect_nudity,
                image_path
            )
            
            # Calculate aggregate score
            nsfw_score = self._calculate_nsfw_score(detections)
            
            # Determine action
            action = self._determine_action(nsfw_score, detections, thresholds)
            
            # Generate reasoning
            reasoning = self._generate_reasoning(detections, nsfw_score, action)
            
            # Check if user strike recommended
            user_strike = self._should_add_strike(action, detections)
            
            # Update statistics
            self.stats["total_checked"] += 1
            self.stats[action.value.lower()] += 1
            
            # Create result
            result = NSFWCheckResult(
                action=action,
                nsfw_score=nsfw_score,
                detections=[
                    NSFWDetection(
                        class_name=d["class"],
                        confidence=d["score"],
                        box=d["box"]
                    )
                    for d in detections
                ],
                reasoning=reasoning,
                user_strike_recommended=user_strike,
                metadata={
                    "mode": mode,
                    "user_id": user_id,
                    "generation_id": generation_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "thresholds": thresholds,
                    "num_detections": len(detections),
                }
            )
            
            # Log result
            await self._log_check(result, image_path, user_id, generation_id)
            
            # Handle quarantine/block
            if action in [SafetyAction.QUARANTINE, SafetyAction.BLOCK]:
                await self._handle_unsafe_image(
                    image_path,
                    result,
                    user_id,
                    generation_id
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in NSFW classification: {e}", exc_info=True)
            # Fail-safe: Block on error
            return NSFWCheckResult(
                action=SafetyAction.BLOCK,
                nsfw_score=1.0,
                detections=[],
                reasoning=f"Classification error: {str(e)}",
                user_strike_recommended=False,
                metadata={
                    "error": str(e),
                    "mode": mode,
                    "user_id": user_id,
                }
            )
    
    def _detect_nudity(self, image_path: str) -> List[Dict]:
        """
        Run NudeNet detection
        
        Returns list of detections with class, score, box
        """
        try:
            # Detect with NudeNet
            detections = self.detector.detect(image_path)
            
            return detections
            
        except Exception as e:
            logger.error(f"NudeNet detection failed: {e}")
            return []
    
    def _calculate_nsfw_score(self, detections: List[Dict]) -> float:
        """
        Calculate aggregate NSFW score (0-1)
        
        Uses weighted scoring based on body part severity
        """
        if not detections:
            return 0.0
        
        # Weight by body part severity
        weights = {
            "EXPOSED_GENITALIA_F": 1.0,
            "EXPOSED_GENITALIA_M": 1.0,
            "EXPOSED_ANUS": 1.0,
            "EXPOSED_BREAST_F": 0.8,
            "EXPOSED_BUTTOCKS": 0.7,
            "EXPOSED_BELLY": 0.3,
            "EXPOSED_FEET": 0.1,
            "EXPOSED_ARMPITS": 0.1,
            "COVERED_GENITALIA_F": 0.5,
            "COVERED_GENITALIA_M": 0.5,
            "COVERED_BREAST_F": 0.4,
            "COVERED_BUTTOCKS": 0.3,
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for detection in detections:
            class_name = detection["class"]
            confidence = detection["score"]
            weight = weights.get(class_name, 0.5)
            
            total_score += confidence * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Normalize to 0-1 range
        normalized_score = min(total_score / total_weight, 1.0)
        
        return normalized_score
    
    def _determine_action(
        self,
        nsfw_score: float,
        detections: List[Dict],
        thresholds: Dict[str, float]
    ) -> SafetyAction:
        """
        Determine action based on score and detections
        """
        # Check for critical parts (instant block)
        has_critical = any(
            d["class"] in self.CRITICAL_PARTS
            for d in detections
        )
        
        if has_critical:
            return SafetyAction.BLOCK
        
        # Check score against thresholds
        if nsfw_score >= thresholds["BLOCK"]:
            return SafetyAction.BLOCK
        elif nsfw_score >= thresholds["QUARANTINE"]:
            return SafetyAction.QUARANTINE
        else:
            return SafetyAction.ALLOW
    
    def _generate_reasoning(
        self,
        detections: List[Dict],
        score: float,
        action: SafetyAction
    ) -> str:
        """
        Generate human-readable reasoning
        """
        if not detections:
            return "No NSFW content detected"
        
        # Summarize detections
        detected_parts = [d.get("class", "") for d in detections]
        unique_parts = set(detected_parts)
        
        if action == SafetyAction.BLOCK:
            critical_detected = [
                p for p in unique_parts if p in self.CRITICAL_PARTS
            ]
            if critical_detected:
                return f"Critical NSFW content detected: {', '.join(critical_detected)}"
            else:
                return f"High NSFW score ({score:.2f}): {len(unique_parts)} body parts detected"
        
        elif action == SafetyAction.QUARANTINE:
            return f"Borderline NSFW score ({score:.2f}): {', '.join(list(unique_parts)[:3])} detected"
        
        else:
            return f"Low NSFW score ({score:.2f}): Safe content"
    
    def _should_add_strike(
        self,
        action: SafetyAction,
        detections: List[Dict]
    ) -> bool:
        """
        Determine if user should receive a strike
        """
        # Only strikes for BLOCK action
        if action != SafetyAction.BLOCK:
            return False
        
        # Check if critical parts detected
        has_critical = any(
            d["class"] in self.CRITICAL_PARTS
            for d in detections
        )
        
        return has_critical
    
    async def _log_check(
        self,
        result: NSFWCheckResult,
        image_path: str,
        user_id: str,
        generation_id: str
    ):
        """
        Log NSFW check to database
        """
        try:
            # This would log to SafetyAuditLog table
            log_data = {
                "event_type": f"NSFW_CHECK_{result.action.value}",
                "user_id": user_id,
                "generation_id": generation_id,
                "stage": "POST_GENERATION",
                "action": result.action.value,
                "scores": {
                    "nsfw_score": result.nsfw_score,
                    "num_detections": len(result.detections),
                },
                "violations": [
                    {
                        "class": d.class_name,
                        "confidence": d.confidence,
                    }
                    for d in result.detections
                ],
                "image_url": image_path,
                "timestamp": datetime.utcnow(),
            }
            
            logger.info(f"NSFW Check logged: {result.action.value} (score={result.nsfw_score:.2f})")
            
            # TODO: Actually save to database
            # await SafetyAuditLog.create(log_data)
            
        except Exception as e:
            logger.error(f"Failed to log NSFW check: {e}")
    
    async def _handle_unsafe_image(
        self,
        image_path: str,
        result: NSFWCheckResult,
        user_id: str,
        generation_id: str
    ):
        """
        Handle quarantine or block action
        """
        try:
            if result.action == SafetyAction.BLOCK:
                # Delete image immediately
                await self._delete_image(image_path)
                logger.warning(f"BLOCKED image deleted: {generation_id}")
                
            elif result.action == SafetyAction.QUARANTINE:
                # Move to quarantine folder
                await self._quarantine_image(
                    image_path,
                    result,
                    user_id,
                    generation_id
                )
                logger.warning(f"Image QUARANTINED: {generation_id}")
                
        except Exception as e:
            logger.error(f"Error handling unsafe image: {e}")
    
    async def _delete_image(self, image_path: str):
        """Delete image file"""
        try:
            path = Path(image_path)
            if path.exists():
                await asyncio.to_thread(path.unlink)
                logger.info(f"Deleted image: {image_path}")
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
    
    async def _quarantine_image(
        self,
        image_path: str,
        result: NSFWCheckResult,
        user_id: str,
        generation_id: str
    ):
        """
        Move image to quarantine folder with metadata
        """
        try:
            # Create quarantine path
            quarantine_dir = Path(f"/quarantine/{user_id}/{generation_id}")
            await asyncio.to_thread(quarantine_dir.mkdir, parents=True, exist_ok=True)
            
            # Copy image
            source = Path(image_path)
            dest = quarantine_dir / source.name
            await asyncio.to_thread(shutil.copy2, source, dest)
            
            # Save metadata
            metadata = {
                "nsfw_score": result.nsfw_score,
                "detections": [
                    {
                        "class": d.class_name,
                        "confidence": d.confidence,
                        "box": d.box,
                    }
                    for d in result.detections
                ],
                "reasoning": result.reasoning,
                "quarantined_at": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "generation_id": generation_id,
            }
            
            metadata_path = quarantine_dir / "metadata.json"
            await asyncio.to_thread(
                metadata_path.write_text,
                json.dumps(metadata, indent=2)
            )
            
            logger.info(f"Image quarantined: {dest}")
            
        except Exception as e:
            logger.error(f"Failed to quarantine image: {e}")
    
    async def batch_classify(
        self,
        image_paths: List[str],
        mode: str,
        user_id: str,
        generation_id: str
    ) -> List[NSFWCheckResult]:
        """
        Classify multiple images in parallel
        
        Args:
            image_paths: List of image paths
            mode: Generation mode
            user_id: User ID
            generation_id: Generation ID
            
        Returns:
            List of NSFWCheckResult
        """
        tasks = [
            self.classify_image(path, mode, user_id, generation_id)
            for path in image_paths
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [
            r for r in results
            if isinstance(r, NSFWCheckResult)
        ]
        
        return valid_results
    
    def get_statistics(self) -> Dict:
        """Get classifier statistics"""
        total = self.stats["total_checked"]
        
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "block_rate": self.stats["blocked"] / total,
            "quarantine_rate": self.stats["quarantined"] / total,
            "allow_rate": self.stats["allowed"] / total,
        }


# ==================== QUARANTINE MANAGER ====================

class QuarantineManager:
    """
    Manage quarantined images
    """
    
    def __init__(self, quarantine_dir: str = "/quarantine"):
        self.quarantine_dir = Path(quarantine_dir)
    
    async def list_quarantined(
        self,
        limit: int = 50,
        older_than: Optional[datetime] = None
    ) -> List[Dict]:
        """
        List quarantined images for review
        """
        quarantined = []
        
        try:
            # Walk quarantine directory
            for user_dir in self.quarantine_dir.iterdir():
                if not user_dir.is_dir():
                    continue
                
                for gen_dir in user_dir.iterdir():
                    if not gen_dir.is_dir():
                        continue
                    
                    metadata_path = gen_dir / "metadata.json"
                    if not metadata_path.exists():
                        continue
                    
                    # Load metadata
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    
                    # Check age filter
                    if older_than:
                        quarantined_at = datetime.fromisoformat(
                            metadata["quarantined_at"]
                        )
                        if quarantined_at > older_than:
                            continue
                    
                    # Find image file
                    image_files = list(gen_dir.glob("*.png")) + list(gen_dir.glob("*.jpg"))
                    if not image_files:
                        continue
                    
                    quarantined.append({
                        "user_id": metadata["user_id"],
                        "generation_id": metadata["generation_id"],
                        "image_path": str(image_files[0]),
                        "nsfw_score": metadata["nsfw_score"],
                        "quarantined_at": metadata["quarantined_at"],
                        "detections": metadata["detections"],
                    })
                    
                    if len(quarantined) >= limit:
                        return quarantined
            
            return quarantined
            
        except Exception as e:
            logger.error(f"Failed to list quarantined images: {e}")
            return []
    
    async def approve_image(self, generation_id: str, reviewed_by: str):
        """
        Approve quarantined image (mark as safe)
        """
        # Update database record
        # Move image back to normal storage
        logger.info(f"Image approved: {generation_id} by {reviewed_by}")
    
    async def reject_image(self, generation_id: str, reviewed_by: str):
        """
        Reject quarantined image (confirm as NSFW)
        """
        # Update database record
        # Keep in quarantine or delete
        logger.info(f"Image rejected: {generation_id} by {reviewed_by}")
    
    async def cleanup_old(self, days: int = 30):
        """
        Delete quarantined images older than X days
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        deleted_count = 0
        
        try:
            for user_dir in self.quarantine_dir.iterdir():
                if not user_dir.is_dir():
                    continue
                
                for gen_dir in user_dir.iterdir():
                    if not gen_dir.is_dir():
                        continue
                    
                    metadata_path = gen_dir / "metadata.json"
                    if not metadata_path.exists():
                        continue
                    
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                    
                    quarantined_at = datetime.fromisoformat(
                        metadata["quarantined_at"]
                    )
                    
                    if quarantined_at < cutoff:
                        # Delete entire directory
                        await asyncio.to_thread(shutil.rmtree, gen_dir)
                        deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old quarantined images")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup quarantine: {e}")
            return deleted_count


# ==================== CONFIGURATION ====================

NSFW_CONFIG = {
    "thresholds": NSFWClassifier.THRESHOLDS,
    "quarantine_retention_days": 30,
    "auto_cleanup_enabled": True,
    "batch_size": 10,
    "max_concurrent_checks": 5,
}
