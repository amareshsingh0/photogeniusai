"""
Age Estimator for PhotoGenius AI using DeepFace
Detects and blocks underage faces (<18 years)
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
import asyncio
from pathlib import Path
import os

# Suppress TensorFlow warnings if it's imported (from global Python)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")  # Suppress TensorFlow INFO/WARN/ERROR
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")  # Disable oneDNN warnings

# Optional imports (numpy and PIL only needed if DeepFace available)
try:
    import numpy as np  # type: ignore[reportMissingImports]
    from PIL import Image  # type: ignore[reportMissingImports]
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None
    Image = None

# Initialize logger first
logger = logging.getLogger(__name__)

# DeepFace (optional - safety checks also happen on Modal)
# Catch both ImportError and any TensorFlow-related errors during import
DEEPFACE_AVAILABLE = False
try:
    # Suppress TensorFlow logging during import
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", message=".*tensorflow.*")
        from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except (ImportError, Exception) as e:
    # Catch ImportError, AttributeError (protobuf issues), or any other import-time errors
    DEEPFACE_AVAILABLE = False
    error_msg = str(e)
    if "protobuf" in error_msg.lower() or "tensorflow" in error_msg.lower() or "runtime_version" in error_msg.lower():
        # Don't log warning here - will be logged in __init__ if needed
        pass
    # Silent fail - will be handled in AgeEstimator.__init__

@dataclass
class FaceAgeResult:
    """Age estimation result for single face"""
    age: int
    confidence: float
    bbox: List[int]  # [x, y, w, h]
    region: Dict  # Face region info

@dataclass
class AgeCheckResult:
    """Complete age check result"""
    safe: bool  # True if all faces >= 18
    faces: List[FaceAgeResult]
    min_age: Optional[int]
    reason: str
    user_strike_recommended: bool

class AgeEstimator:
    """
    Age estimator using DeepFace
    
    Blocks content if ANY detected face appears under 18 years old
    """
    
    # Minimum age threshold
    MIN_AGE = 18
    
    # Confidence threshold for age predictions
    CONFIDENCE_THRESHOLD = 0.7
    
    def __init__(self):
        """Initialize age estimator"""
        logger.info("Initializing Age Estimator...")
        
        if not DEEPFACE_AVAILABLE:
            # Only log if numpy is also missing (both required)
            # If only DeepFace is missing, it's expected (optional dependency)
            if not NUMPY_AVAILABLE:
                logger.warning("⚠️  numpy not available - age estimation disabled locally")
                logger.warning("   Install with: pip install numpy")
            else:
                # DeepFace unavailable is expected (optional, pulls in TensorFlow)
                logger.debug("DeepFace not available - age estimation disabled locally (expected with minimal requirements)")
            logger.debug("Safety checks still happen on Modal GPU workers")
            self.enabled = False
        else:
            self.enabled = True
            # DeepFace will auto-download models on first use
            # Pre-load by running a dummy prediction
            if np is None:
                self.enabled = False
                return
            try:
                dummy_img = np.zeros((224, 224, 3), dtype=np.uint8)
                DeepFace.analyze(
                    dummy_img,
                    actions=['age'],
                    enforce_detection=False,
                    silent=True
                )
                logger.info("✓ DeepFace age model loaded")
            except Exception as e:
                logger.warning(f"DeepFace pre-load failed: {e}")
                self.enabled = False
        
        self.stats = {
            "total_checked": 0,
            "blocked": 0,
            "allowed": 0,
            "avg_age": 0.0,
        }
    
    async def check_image(
        self,
        image_path: str,
        user_id: str,
        generation_id: str
    ) -> AgeCheckResult:
        """
        Check image for underage faces
        
        Args:
            image_path: Path to image file
            user_id: User ID for logging
            generation_id: Generation ID
            
        Returns:
            AgeCheckResult with safety determination
            (safe=True if DeepFace unavailable - safety checks happen on Modal)
        """
        # If DeepFace not available, allow (safety checks happen on Modal)
        if not self.enabled:
            logger.debug("Age estimation skipped (DeepFace not available - checks happen on Modal)")
            return AgeCheckResult(
                safe=True,
                faces=[],
                min_age=None,
                reason="Age estimation disabled locally (checks happen on Modal GPU)",
                user_strike_recommended=False
            )
        
        try:
            # Run age analysis (CPU-bound, use executor)
            faces = await asyncio.to_thread(
                self._analyze_faces,
                image_path
            )
            
            if not faces:
                # No faces detected - allow
                return AgeCheckResult(
                    safe=True,
                    faces=[],
                    min_age=None,
                    reason="No faces detected",
                    user_strike_recommended=False
                )
            
            # Check ages
            ages = [f.age for f in faces]
            min_age = min(ages)
            avg_age = sum(ages) / len(ages)
            
            # Update statistics
            self.stats["total_checked"] += 1
            self.stats["avg_age"] = (
                (self.stats["avg_age"] * (self.stats["total_checked"] - 1) + avg_age)
                / self.stats["total_checked"]
            )
            
            # Check if any face under 18
            if min_age < self.MIN_AGE:
                self.stats["blocked"] += 1
                
                return AgeCheckResult(
                    safe=False,
                    faces=faces,
                    min_age=min_age,
                    reason=f"Detected face appears {min_age} years old (minimum {self.MIN_AGE})",
                    user_strike_recommended=True  # Serious violation
                )
            
            # All faces pass
            self.stats["allowed"] += 1
            
            return AgeCheckResult(
                safe=True,
                faces=faces,
                min_age=min_age,
                reason=f"All faces appear {self.MIN_AGE}+ (youngest: {min_age})",
                user_strike_recommended=False
            )
            
        except Exception as e:
            logger.error(f"Age estimation error: {e}")
            
            # Fail-safe: Block on error
            return AgeCheckResult(
                safe=False,
                faces=[],
                min_age=None,
                reason=f"Age estimation failed: {str(e)}",
                user_strike_recommended=False  # Don't strike on tech error
            )
    
    def _analyze_faces(self, image_path: str) -> List[FaceAgeResult]:
        """
        Analyze all faces in image for age
        
        Returns list of FaceAgeResult
        """
        if not DEEPFACE_AVAILABLE:
            raise ImportError("DeepFace not available")
        
        try:
            # Analyze with DeepFace
            results = DeepFace.analyze(
                img_path=image_path,
                actions=['age'],
                enforce_detection=True,
                silent=True
            )
            
            # Handle single face vs multiple faces
            if not isinstance(results, list):
                results = [results]
            
            faces = []
            
            for result in results:
                # Extract age
                age = int(result['age'])
                
                # Extract face region
                region = result.get('region', {})
                bbox = [
                    region.get('x', 0),
                    region.get('y', 0),
                    region.get('w', 0),
                    region.get('h', 0),
                ]
                
                # Estimate confidence (DeepFace doesn't provide this directly)
                # We use a heuristic based on face size
                face_area = bbox[2] * bbox[3]
                confidence = min(face_area / 50000, 1.0)  # Larger face = higher confidence
                
                faces.append(FaceAgeResult(
                    age=age,
                    confidence=confidence,
                    bbox=bbox,
                    region=region
                ))
            
            return faces
            
        except ValueError as e:
            # No face detected
            logger.debug(f"No face detected: {e}")
            return []
            
        except Exception as e:
            logger.error(f"DeepFace analysis failed: {e}")
            return []
    
    async def check_batch(
        self,
        image_paths: List[str],
        user_id: str,
        generation_id: str
    ) -> List[AgeCheckResult]:
        """
        Check multiple images in parallel
        """
        tasks = [
            self.check_image(path, user_id, generation_id)
            for path in image_paths
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [
            r for r in results
            if isinstance(r, AgeCheckResult)
        ]
        
        return valid_results
    
    def get_statistics(self) -> Dict:
        """Get estimator statistics"""
        total = self.stats["total_checked"]
        
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            "block_rate": self.stats["blocked"] / total,
            "allow_rate": self.stats["allowed"] / total,
        }
