"""
Complete Dual Pipeline Safety System for PhotoGenius AI
Integrates PromptSanitizer, NSFWClassifier, and AgeEstimator
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from pathlib import Path

from .prompt_sanitizer import PromptSanitizer, SafetyCheckResult as PromptCheckResult
from .nsfw_classifier import NSFWClassifier, SafetyAction, NSFWCheckResult
from .age_estimator import AgeEstimator, AgeCheckResult

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
_audit_logger = None
_AuditEventType = None

def _get_audit_logger():
    """Lazy import audit logger"""
    global _audit_logger, _AuditEventType
    if _audit_logger is None:
        from .audit_logger import audit_logger, AuditEventType
        _audit_logger = audit_logger
        _AuditEventType = AuditEventType
    assert _AuditEventType is not None
    return _audit_logger, _AuditEventType

class SafetyStage(Enum):
    """Safety check stage"""
    PRE_GENERATION = "PRE_GENERATION"
    POST_GENERATION = "POST_GENERATION"

@dataclass
class PreGenerationResult:
    """Result of pre-generation safety checks"""
    allowed: bool
    violations: List[Dict[str, Any]]
    severity: str
    reason: str
    user_strike_added: bool
    metadata: Dict[str, Any]
    modified_prompt: Optional[str] = None

@dataclass
class PostGenerationResult:
    """Result of post-generation safety checks"""
    safe: bool
    action: str  # ALLOW, QUARANTINE, BLOCK
    violations: List[Dict[str, Any]]
    user_strike_added: bool
    image_deleted: bool
    metadata: Dict[str, Any]

class DualPipelineSafety:
    """
    Dual Pipeline Safety System
    
    STAGE 1 (PRE-GENERATION):
    - Runs BEFORE consuming GPU resources
    - Checks: Prompt sanitization, user status, rate limits
    - Fast: <100ms
    - Blocks: Invalid prompts, banned users, rate limit violations
    
    STAGE 2 (POST-GENERATION):
    - Runs AFTER image generation
    - Checks: NSFW content, age estimation
    - Slower: 2-5 seconds
    - Actions: ALLOW, QUARANTINE (review), BLOCK (delete)
    """
    
    # Strike thresholds
    MAX_STRIKES = 3
    STRIKE_EXPIRY_DAYS = 90
    
    # Auto-ban conditions
    AUTO_BAN_CRITICAL_STRIKES = 2  # 2 critical violations = instant ban
    
    def __init__(self):
        """Initialize dual pipeline"""
        logger.info("Initializing Dual Pipeline Safety System...")
        
        # Initialize components
        self.prompt_sanitizer = PromptSanitizer()
        self.nsfw_classifier = NSFWClassifier()
        self.age_estimator = AgeEstimator()
        
        # Statistics
        self.stats = {
            "pre_gen_checks": 0,
            "pre_gen_blocks": 0,
            "post_gen_checks": 0,
            "post_gen_blocks": 0,
            "strikes_added": 0,
            "users_banned": 0,
        }
        
        logger.info("✓ Dual Pipeline Safety System initialized")
    
    # ==================== PRE-GENERATION CHECKS ====================
    
    async def pre_generation_check(
        self,
        user_id: str,
        prompt: str,
        mode: str,
        identity_id: str,
        db_session: Any = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PreGenerationResult:
        """
        Stage 1: Pre-generation safety checks
        
        Checks performed:
        1. User status (banned, strikes)
        2. Prompt sanitization
        3. Rate limiting
        4. Identity consent verification
        
        Args:
            user_id: User ID
            prompt: User's prompt
            mode: Generation mode
            identity_id: Identity being used (optional)
            db_session: Database session (optional)
            
        Returns:
            PreGenerationResult with allow/block decision
        """
        self.stats["pre_gen_checks"] += 1
        violations = []
        severity = "LOW"
        
        try:
            # ===== CHECK 1: USER STATUS =====
            user_check = await self._check_user_status(user_id, db_session)
            
            if not user_check["allowed"]:
                self.stats["pre_gen_blocks"] += 1
                
                result = PreGenerationResult(
                    allowed=False,
                    violations=[{
                        "type": "USER_STATUS",
                        "reason": user_check["reason"],
                        "severity": "CRITICAL"
                    }],
                    severity="CRITICAL",
                    reason=user_check["reason"],
                    user_strike_added=False,
                    metadata={
                        "user_id": user_id,
                        "stage": SafetyStage.PRE_GENERATION.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
                # Log audit event
                try:
                    audit_logger, AuditEventType = _get_audit_logger()
                    asyncio.create_task(audit_logger.log_event(
                        event_type=AuditEventType.PRE_GEN_BLOCK,
                        user_id=user_id,
                        stage=SafetyStage.PRE_GENERATION.value,
                        action="BLOCK",
                        violations={"items": result.violations} if result.violations else None,
                        metadata=result.metadata,
                        db_session=db_session
                    ))
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")
                
                return result
            
            # ===== CHECK 2: PROMPT SANITIZATION =====
            prompt_result = self.prompt_sanitizer.check_prompt(
                prompt=prompt,
                user_id=user_id
            )
            
            # Log adversarial detections if any
            if hasattr(self.prompt_sanitizer, 'adversarial_detector'):
                adv_result = self.prompt_sanitizer.adversarial_detector.detect_and_sanitize(prompt)
                if adv_result.get("is_adversarial"):
                    await self._log_adversarial_detection(
                        user_id=user_id,
                        prompt=prompt,
                        adv_result=adv_result,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        db_session=db_session
                    )
            
            if not prompt_result.safe:
                violations.extend([
                    {
                        "type": v.get("type", "PROMPT_VIOLATION"),
                        "reason": v.get("reason", "Unsafe content"),
                        "severity": v.get("severity", "MEDIUM"),
                        "keyword": v.get("keyword") or v.get("name"),
                    }
                    for v in prompt_result.violations
                ])
                
                severity = prompt_result.severity
                
                # Add user strike if recommended
                user_strike_added = False
                if prompt_result.user_strike_recommended:
                    user_strike_added = await self._add_user_strike(
                        user_id=user_id,
                        reason=f"Unsafe prompt: {prompt[:100]}",
                        severity=severity,
                        db_session=db_session
                    )
                    self.stats["strikes_added"] += 1
                
                self.stats["pre_gen_blocks"] += 1
                
                result = PreGenerationResult(
                    allowed=False,
                    violations=violations,
                    severity=severity,
                    reason=f"Prompt contains unsafe content: {', '.join([v.get('reason', '') for v in violations[:3]])}",
                    user_strike_added=user_strike_added,
                    modified_prompt=prompt_result.suggested_alternative,
                    metadata={
                        "user_id": user_id,
                        "prompt": prompt[:200],
                        "mode": mode,
                        "suggested_alternative": prompt_result.suggested_alternative,
                        "stage": SafetyStage.PRE_GENERATION.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
                # Log audit event
                try:
                    audit_logger, AuditEventType = _get_audit_logger()
                    asyncio.create_task(audit_logger.log_event(
                        event_type=AuditEventType.PRE_GEN_BLOCK,
                        user_id=user_id,
                        stage=SafetyStage.PRE_GENERATION.value,
                        action="BLOCK",
                        violations={"items": violations} if violations else None,
                        prompt=prompt,
                        metadata=result.metadata,
                        db_session=db_session
                    ))
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")
                
                return result
            
            # ===== CHECK 3: RATE LIMITING =====
            rate_limit_check = await self._check_rate_limit(user_id, db_session)
            
            if not rate_limit_check["allowed"]:
                self.stats["pre_gen_blocks"] += 1
                
                result = PreGenerationResult(
                    allowed=False,
                    violations=[{
                        "type": "RATE_LIMIT",
                        "reason": rate_limit_check["reason"],
                        "severity": "MEDIUM"
                    }],
                    severity="MEDIUM",
                    reason=rate_limit_check["reason"],
                    user_strike_added=False,
                    metadata={
                        "user_id": user_id,
                        "retry_after": rate_limit_check.get("retry_after"),
                        "stage": SafetyStage.PRE_GENERATION.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
                # Log audit event
                try:
                    audit_logger, AuditEventType = _get_audit_logger()
                    asyncio.create_task(audit_logger.log_event(
                        event_type=AuditEventType.RATE_LIMIT,
                        user_id=user_id,
                        stage=SafetyStage.PRE_GENERATION.value,
                        action="BLOCK",
                        violations={"items": result.violations} if result.violations else None,
                        metadata=result.metadata,
                        db_session=db_session
                    ))
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")
                
                return result
            
            # ===== CHECK 4: IDENTITY CONSENT =====
            consent_check = await self._check_identity_consent(identity_id, db_session)
            
            if not consent_check["allowed"]:
                result = PreGenerationResult(
                    allowed=False,
                    violations=[{
                        "type": "CONSENT",
                        "reason": consent_check["reason"],
                        "severity": "HIGH"
                    }],
                    severity="HIGH",
                    reason=consent_check["reason"],
                    user_strike_added=False,
                    metadata={
                        "identity_id": identity_id,
                        "stage": SafetyStage.PRE_GENERATION.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
                # Log audit event
                try:
                    audit_logger, AuditEventType = _get_audit_logger()
                    asyncio.create_task(audit_logger.log_event(
                        event_type=AuditEventType.PRE_GEN_BLOCK,
                        user_id=user_id,
                        stage=SafetyStage.PRE_GENERATION.value,
                        action="BLOCK",
                        violations={"items": result.violations} if result.violations else None,
                        metadata=result.metadata,
                        db_session=db_session
                    ))
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")
                
                return result
            
            # ===== ALL CHECKS PASSED =====
            result = PreGenerationResult(
                allowed=True,
                violations=[],
                severity="LOW",
                reason="All pre-generation checks passed",
                user_strike_added=False,
                modified_prompt=prompt,  # Use original prompt if safe
                metadata={
                    "user_id": user_id,
                    "prompt_safe": True,
                    "stage": SafetyStage.PRE_GENERATION.value,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            
            # Log audit event (non-blocking)
            try:
                audit_logger, AuditEventType = _get_audit_logger()
                asyncio.create_task(audit_logger.log_event(
                    event_type=AuditEventType.PRE_GEN_ALLOW,
                    user_id=user_id,
                    stage=SafetyStage.PRE_GENERATION.value,
                    action="ALLOW",
                    metadata=result.metadata,
                    db_session=db_session
                ))
            except Exception as e:
                logger.error(f"Failed to log audit event: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Pre-generation check error: {e}")
            
            # Fail-safe: Block on error
            self.stats["pre_gen_blocks"] += 1
            
            return PreGenerationResult(
                allowed=False,
                violations=[{
                    "type": "SYSTEM_ERROR",
                    "reason": f"Safety check failed: {str(e)}",
                    "severity": "HIGH"
                }],
                severity="HIGH",
                reason="Safety system error - request blocked",
                user_strike_added=False,
                metadata={
                    "error": str(e),
                    "stage": SafetyStage.PRE_GENERATION.value,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
    
    # ==================== POST-GENERATION CHECKS ====================
    
    async def post_generation_check(
        self,
        image_path: str,
        user_id: str,
        generation_id: str,
        mode: str,
        db_session: Any
    ) -> PostGenerationResult:
        """
        Stage 2: Post-generation safety checks
        
        Checks performed:
        1. NSFW content detection
        2. Age estimation
        3. Quarantine/block decision
        
        Args:
            image_path: Path to generated image
            user_id: User ID
            generation_id: Generation ID
            mode: Generation mode
            db_session: Database session (optional)
            
        Returns:
            PostGenerationResult with safety action
        """
        self.stats["post_gen_checks"] += 1
        violations = []
        user_strike_added = False
        image_deleted = False
        
        try:
            # Run checks in parallel for performance
            nsfw_check, age_check = await asyncio.gather(
                self.nsfw_classifier.classify_image(
                    image_path=image_path,
                    mode=mode,
                    user_id=user_id,
                    generation_id=generation_id
                ),
                self.age_estimator.check_image(
                    image_path=image_path,
                    user_id=user_id,
                    generation_id=generation_id
                ),
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(nsfw_check, Exception):
                logger.error(f"NSFW check failed: {nsfw_check}")
                nsfw_check = NSFWCheckResult(
                    action=SafetyAction.BLOCK,
                    nsfw_score=1.0,
                    detections=[],
                    reasoning="NSFW check failed",
                    user_strike_recommended=False,
                    metadata={}
                )
            
            if isinstance(age_check, Exception):
                logger.error(f"Age check failed: {age_check}")
                age_check = AgeCheckResult(
                    safe=False,
                    faces=[],
                    min_age=None,
                    reason="Age check failed",
                    user_strike_recommended=False
                )
            assert not isinstance(age_check, Exception)
            assert not isinstance(nsfw_check, Exception)

            # ===== EVALUATE RESULTS =====
            
            # Age check (highest priority)
            if not age_check.safe:
                violations.append({
                    "type": "UNDERAGE",
                    "severity": "CRITICAL",
                    "reason": age_check.reason,
                    "min_age": age_check.min_age,
                })
                
                # Add strike for underage content
                if age_check.user_strike_recommended:
                    user_strike_added = await self._add_user_strike(
                        user_id=user_id,
                        reason=f"Underage face detected: {age_check.reason}",
                        severity="CRITICAL",
                        db_session=db_session
                    )
                    self.stats["strikes_added"] += 1
                
                # Delete image immediately
                await self._delete_image(image_path)
                image_deleted = True
                
                self.stats["post_gen_blocks"] += 1
                
                result = PostGenerationResult(
                    safe=False,
                    action="BLOCK",
                    violations=violations,
                    user_strike_added=user_strike_added,
                    image_deleted=True,
                    metadata={
                        "reason": "Underage content",
                        "generation_id": generation_id,
                        "stage": SafetyStage.POST_GENERATION.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
                # Log audit event
                try:
                    audit_logger, AuditEventType = _get_audit_logger()
                    asyncio.create_task(audit_logger.log_event(
                        event_type=AuditEventType.UNDERAGE_DETECTED,
                        user_id=user_id,
                        generation_id=generation_id,
                        stage=SafetyStage.POST_GENERATION.value,
                        action="BLOCK",
                        violations={"items": violations} if violations else None,
                        scores={"min_age": age_check.min_age} if age_check.min_age else None,
                        image_url=image_path,
                        metadata=result.metadata,
                        db_session=db_session
                    ))
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")
                
                return result
            
            # NSFW check
            if nsfw_check.action == SafetyAction.BLOCK:
                violations.append({
                    "type": "NSFW",
                    "severity": "CRITICAL",
                    "reason": nsfw_check.reasoning,
                    "nsfw_score": nsfw_check.nsfw_score,
                })
                
                # Add strike if recommended
                if nsfw_check.user_strike_recommended:
                    user_strike_added = await self._add_user_strike(
                        user_id=user_id,
                        reason=f"NSFW content: {nsfw_check.reasoning}",
                        severity="CRITICAL",
                        db_session=db_session
                    )
                    self.stats["strikes_added"] += 1
                
                # Delete image
                await self._delete_image(image_path)
                image_deleted = True
                
                self.stats["post_gen_blocks"] += 1
                
                result = PostGenerationResult(
                    safe=False,
                    action="BLOCK",
                    violations=violations,
                    user_strike_added=user_strike_added,
                    image_deleted=True,
                    metadata={
                        "reason": "NSFW content",
                        "nsfw_score": nsfw_check.nsfw_score,
                        "generation_id": generation_id,
                        "stage": SafetyStage.POST_GENERATION.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
                # Log audit event
                try:
                    audit_logger, AuditEventType = _get_audit_logger()
                    asyncio.create_task(audit_logger.log_event(
                        event_type=AuditEventType.NSFW_DETECTED,
                        user_id=user_id,
                        generation_id=generation_id,
                        stage=SafetyStage.POST_GENERATION.value,
                        action="BLOCK",
                        violations={"items": violations} if violations else None,
                        scores={"nsfw_score": nsfw_check.nsfw_score},
                        image_url=image_path,
                        metadata=result.metadata,
                        db_session=db_session
                    ))
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")
                
                return result
            
            elif nsfw_check.action == SafetyAction.QUARANTINE:
                violations.append({
                    "type": "NSFW_BORDERLINE",
                    "severity": "MEDIUM",
                    "reason": nsfw_check.reasoning,
                    "nsfw_score": nsfw_check.nsfw_score,
                })
                
                result = PostGenerationResult(
                    safe=False,
                    action="QUARANTINE",
                    violations=violations,
                    user_strike_added=False,
                    image_deleted=False,
                    metadata={
                        "reason": "Borderline NSFW - requires review",
                        "nsfw_score": nsfw_check.nsfw_score,
                        "generation_id": generation_id,
                        "stage": SafetyStage.POST_GENERATION.value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
                # Log audit event
                try:
                    audit_logger, AuditEventType = _get_audit_logger()
                    asyncio.create_task(audit_logger.log_event(
                        event_type=AuditEventType.POST_GEN_QUARANTINE,
                        user_id=user_id,
                        generation_id=generation_id,
                        stage=SafetyStage.POST_GENERATION.value,
                        action="QUARANTINE",
                        violations={"items": violations} if violations else None,
                        scores={"nsfw_score": nsfw_check.nsfw_score},
                        image_url=image_path,
                        metadata=result.metadata,
                        db_session=db_session
                    ))
                except Exception as e:
                    logger.error(f"Failed to log audit event: {e}")
                
                return result
            
            # ===== ALL CHECKS PASSED =====
            result = PostGenerationResult(
                safe=True,
                action="ALLOW",
                violations=[],
                user_strike_added=False,
                image_deleted=False,
                metadata={
                    "nsfw_score": nsfw_check.nsfw_score,
                    "age_check": "passed",
                    "generation_id": generation_id,
                    "stage": SafetyStage.POST_GENERATION.value,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            
            # Log audit event (non-blocking)
            try:
                audit_logger, AuditEventType = _get_audit_logger()
                asyncio.create_task(audit_logger.log_event(
                    event_type=AuditEventType.POST_GEN_ALLOW,
                    user_id=user_id,
                    generation_id=generation_id,
                    stage=SafetyStage.POST_GENERATION.value,
                    action="ALLOW",
                    scores={"nsfw_score": nsfw_check.nsfw_score},
                    image_url=image_path,
                    metadata=result.metadata,
                    db_session=db_session
                ))
            except Exception as e:
                logger.error(f"Failed to log audit event: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Post-generation check error: {e}")
            
            # Fail-safe: Block and delete on error
            try:
                await self._delete_image(image_path)
                image_deleted = True
            except:
                pass
            
            self.stats["post_gen_blocks"] += 1
            
            return PostGenerationResult(
                safe=False,
                action="BLOCK",
                violations=[{
                    "type": "SYSTEM_ERROR",
                    "severity": "HIGH",
                    "reason": f"Safety check failed: {str(e)}",
                }],
                user_strike_added=False,
                image_deleted=image_deleted,
                metadata={
                    "error": str(e),
                    "stage": SafetyStage.POST_GENERATION.value,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
    
    # ==================== HELPER METHODS ====================
    
    async def _check_user_status(
        self,
        user_id: str,
        db_session: Any
    ) -> Dict[str, Any]:
        """
        Check if user is allowed to generate

        Checks:
        - Is user banned?
        - Does user have strikes?
        - Is user verified?
        """
        try:
            if db_session is None:
                logger.warning("No db_session provided, allowing by default")
                return {"allowed": True}

            from sqlalchemy import text  # type: ignore[reportMissingImports]

            # Query user by clerk_id or uuid
            result = await db_session.execute(
                text("""
                    SELECT id, is_banned, ban_reason, strikes, last_strike_at
                    FROM users
                    WHERE clerk_id = :user_id OR id::text = :user_id
                    LIMIT 1
                """),
                {"user_id": user_id}
            )
            row = result.fetchone()

            if not row:
                logger.warning(f"User not found: {user_id}")
                # New users are allowed
                return {"allowed": True}

            # Check if banned
            if row.is_banned:
                logger.warning(f"Banned user attempted generation: {user_id}")
                return {
                    "allowed": False,
                    "reason": f"Account banned: {row.ban_reason or 'Policy violation'}"
                }

            # Check strike count
            if row.strikes >= self.MAX_STRIKES:
                logger.warning(f"User with max strikes attempted generation: {user_id}")
                return {
                    "allowed": False,
                    "reason": f"Account suspended: {row.strikes} strikes. Contact support."
                }

            # Check if strikes should expire (90 days)
            if row.last_strike_at and row.strikes > 0:
                from datetime import datetime, timedelta
                expiry_date = row.last_strike_at + timedelta(days=self.STRIKE_EXPIRY_DAYS)
                if datetime.utcnow() > expiry_date:
                    # Reset expired strikes
                    await db_session.execute(
                        text("UPDATE users SET strikes = 0, last_strike_at = NULL WHERE id = :id"),
                        {"id": row.id}
                    )
                    await db_session.commit()
                    logger.info(f"Expired strikes reset for user: {user_id}")

            return {"allowed": True}

        except Exception as e:
            logger.error(f"User status check failed: {e}")
            # Fail-safe: Allow on error (don't block legitimate users)
            return {"allowed": True}
    
    async def _check_rate_limit(
        self,
        user_id: str,
        db_session: Any
    ) -> Dict[str, Any]:
        """
        Check rate limits using Redis
        
        Limits:
        - 10 generations per minute
        - 100 generations per hour
        - 1000 generations per day
        """
        try:
            from .rate_limiter import rate_limiter
            return await rate_limiter.check_rate_limit(user_id)
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail-safe: Allow on error
            return {"allowed": True}
    
    async def _check_identity_consent(
        self,
        identity_id: str,
        db_session: Any
    ) -> Dict[str, Any]:
        """
        Verify identity has consent and is ready for generation
        """
        try:
            # Empty identity_id means no identity used (allowed)
            if not identity_id or identity_id == "" or identity_id == "default":
                return {"allowed": True}

            if db_session is None:
                logger.warning("No db_session for identity check, blocking by default")
                return {
                    "allowed": False,
                    "reason": "Identity verification unavailable"
                }

            from sqlalchemy import text  # type: ignore[reportMissingImports]

            # Query identity
            result = await db_session.execute(
                text("""
                    SELECT id, consent_given, training_status, is_deleted
                    FROM identities
                    WHERE id::text = :identity_id
                    LIMIT 1
                """),
                {"identity_id": identity_id}
            )
            row = result.fetchone()

            if not row:
                logger.warning(f"Identity not found: {identity_id}")
                return {
                    "allowed": False,
                    "reason": "Identity not found"
                }

            # Check if deleted
            if row.is_deleted:
                return {
                    "allowed": False,
                    "reason": "Identity has been deleted"
                }

            # Check consent
            if not row.consent_given:
                logger.warning(f"Identity without consent: {identity_id}")
                return {
                    "allowed": False,
                    "reason": "Consent not provided for this identity"
                }

            # Check training status
            if row.training_status != "COMPLETED":
                return {
                    "allowed": False,
                    "reason": f"Identity training not complete: {row.training_status}"
                }

            return {"allowed": True}

        except Exception as e:
            logger.error(f"Consent check failed: {e}")
            # Fail-safe: Block on error (safety first for identity usage)
            return {
                "allowed": False,
                "reason": "Identity verification failed"
            }
    
    async def _add_user_strike(
        self,
        user_id: str,
        reason: str,
        severity: str,
        db_session: Any
    ) -> bool:
        """
        Add strike to user account

        Returns True if strike added, False otherwise
        """
        try:
            if db_session is None:
                logger.warning(f"No db_session, strike not persisted for user {user_id}: {reason}")
                return False

            from sqlalchemy import text  # type: ignore[reportMissingImports]
            from datetime import datetime

            # Get user UUID from clerk_id if needed
            user_result = await db_session.execute(
                text("""
                    SELECT id, strikes FROM users
                    WHERE clerk_id = :user_id OR id::text = :user_id
                    LIMIT 1
                """),
                {"user_id": user_id}
            )
            user_row = user_result.fetchone()

            if not user_row:
                logger.warning(f"User not found for strike: {user_id}")
                return False

            user_uuid = user_row.id
            current_strikes = user_row.strikes or 0
            new_strikes = current_strikes + 1

            # Update strikes
            await db_session.execute(
                text("""
                    UPDATE users
                    SET strikes = :new_strikes,
                        last_strike_at = :now
                    WHERE id = :user_uuid
                """),
                {
                    "new_strikes": new_strikes,
                    "now": datetime.utcnow(),
                    "user_uuid": user_uuid
                }
            )
            await db_session.commit()

            logger.warning(f"Strike added to user {user_id}: {reason} (total: {new_strikes})")

            # Log strike event
            try:
                audit_logger, AuditEventType = _get_audit_logger()
                asyncio.create_task(audit_logger.log_event(
                    event_type=AuditEventType.STRIKE_ADDED,
                    user_id=user_id,
                    metadata={
                        "reason": reason,
                        "severity": severity,
                        "strike_count": new_strikes
                    },
                    db_session=db_session
                ))
            except Exception as e:
                logger.error(f"Failed to log strike event: {e}")

            # Check if should auto-ban
            if severity == "CRITICAL" and new_strikes >= self.AUTO_BAN_CRITICAL_STRIKES:
                await self._ban_user(
                    user_id=user_id,
                    reason=f"Auto-banned after {new_strikes} critical violations",
                    db_session=db_session
                )
                self.stats["users_banned"] += 1
            elif new_strikes >= self.MAX_STRIKES:
                await self._ban_user(
                    user_id=user_id,
                    reason=f"Auto-banned after {new_strikes} strikes (max: {self.MAX_STRIKES})",
                    db_session=db_session
                )
                self.stats["users_banned"] += 1

            return True

        except Exception as e:
            logger.error(f"Failed to add strike: {e}")
            try:
                await db_session.rollback()
            except Exception:
                pass
            return False
    
    async def _log_adversarial_detection(
        self,
        user_id: str,
        prompt: str,
        adv_result: Dict,
        ip_address: Optional[str],
        user_agent: Optional[str],
        db_session: Any
    ):
        """Log adversarial detection to database"""
        try:
            from app.models.safety import AdversarialLog
            from sqlalchemy import text  # type: ignore[reportMissingImports]
            
            # Get user UUID if user_id is clerk_id
            user_uuid = None
            if user_id:
                try:
                    result = await db_session.execute(
                        text("SELECT id FROM users WHERE clerk_id = :clerk_id"),
                        {"clerk_id": user_id}
                    )
                    row = result.fetchone()
                    if row:
                        user_uuid = row.id
                except Exception:
                    pass  # User UUID lookup failed, continue without it
            
            log_entry = AdversarialLog(
                user_id=user_uuid,
                prompt=prompt[:500],  # Truncate
                detections=adv_result.get("detections", []),
                sanitized_prompt=adv_result.get("sanitized_prompt", "")[:500] if adv_result.get("sanitized_prompt") else None,
                was_blocked="true" if adv_result.get("should_block") else "false",
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
            )
            db_session.add(log_entry)
            await db_session.commit()
            logger.info(f"Logged adversarial detection for user {user_id}: {len(adv_result.get('detections', []))} patterns")
        except Exception as e:
            logger.error(f"Failed to log adversarial detection: {e}")
            try:
                await db_session.rollback()
            except Exception:
                pass

    async def _ban_user(
        self,
        user_id: str,
        reason: str,
        db_session: Any
    ):
        """
        Ban user account
        """
        try:
            if db_session is None:
                logger.critical(f"User BANNED (not persisted - no db): {user_id} - {reason}")
                return

            from sqlalchemy import text  # type: ignore[reportMissingImports]
            from datetime import datetime

            # Get user UUID
            user_result = await db_session.execute(
                text("""
                    SELECT id, email, stripe_subscription_id FROM users
                    WHERE clerk_id = :user_id OR id::text = :user_id
                    LIMIT 1
                """),
                {"user_id": user_id}
            )
            user_row = user_result.fetchone()

            if not user_row:
                logger.warning(f"User not found for ban: {user_id}")
                return

            user_uuid = user_row.id
            user_email = user_row.email

            # Ban user in database
            await db_session.execute(
                text("""
                    UPDATE users
                    SET is_banned = true,
                        ban_reason = :reason,
                        banned_at = :now
                    WHERE id = :user_uuid
                """),
                {
                    "reason": reason,
                    "now": datetime.utcnow(),
                    "user_uuid": user_uuid
                }
            )

            # Soft-delete user's pending generations
            await db_session.execute(
                text("""
                    UPDATE generations
                    SET is_deleted = true, deleted_at = :now
                    WHERE user_id = :user_uuid AND is_deleted = false
                """),
                {"now": datetime.utcnow(), "user_uuid": user_uuid}
            )

            await db_session.commit()

            logger.critical(f"User BANNED: {user_id} ({user_email}) - {reason}")

            # Log ban event
            try:
                audit_logger, AuditEventType = _get_audit_logger()
                asyncio.create_task(audit_logger.log_event(
                    event_type=AuditEventType.USER_BANNED,
                    user_id=user_id,
                    metadata={"reason": reason, "email": user_email},
                    db_session=db_session
                ))
            except Exception as e:
                logger.error(f"Failed to log ban event: {e}")

            # Cancel Stripe subscription if exists
            if user_row.stripe_subscription_id:
                try:
                    await self._cancel_stripe_subscription(user_row.stripe_subscription_id)
                except Exception as e:
                    logger.error(f"Failed to cancel subscription for banned user: {e}")

        except Exception as e:
            logger.error(f"Failed to ban user: {e}")
            try:
                await db_session.rollback()
            except Exception:
                pass

    async def _cancel_stripe_subscription(self, subscription_id: str):
        """Cancel Stripe subscription for banned user"""
        try:
            import stripe  # type: ignore[reportMissingImports]
            import os

            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
            if not stripe.api_key:
                logger.warning("STRIPE_SECRET_KEY not set, skipping subscription cancel")
                return

            stripe.Subscription.cancel(subscription_id)
            logger.info(f"Cancelled Stripe subscription: {subscription_id}")

        except Exception as e:
            logger.error(f"Stripe subscription cancel failed: {e}")
    
    async def _delete_image(self, image_path: str):
        """Delete image file"""
        try:
            path = Path(image_path)
            if path.exists():
                await asyncio.to_thread(path.unlink)
                logger.info(f"Image deleted: {image_path}")
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
    
    def get_statistics(self) -> Dict:
        """Get safety system statistics"""
        total_pre = self.stats["pre_gen_checks"]
        total_post = self.stats["post_gen_checks"]
        
        stats = {**self.stats}
        
        if total_pre > 0:
            stats["pre_gen_block_rate"] = self.stats["pre_gen_blocks"] / total_pre
        
        if total_post > 0:
            stats["post_gen_block_rate"] = self.stats["post_gen_blocks"] / total_post
        
        return stats


# ==================== GLOBAL INSTANCE ====================

# Create singleton instance
dual_pipeline = DualPipelineSafety()


# ==================== CONVENIENCE FUNCTIONS ====================

async def run_pre_check(
    user_id: str,
    prompt: str,
    mode: str = "REALISM",
    identity_id: Optional[str] = None,
    db_session: Optional[Any] = None
) -> PreGenerationResult:
    """
    Convenience function for pre-generation check

    Note: identity_id is optional. If not provided, empty string is passed
    and consent check will be skipped (allowed by default for non-identity generations).
    """
    return await dual_pipeline.pre_generation_check(
        user_id=user_id,
        prompt=prompt,
        mode=mode,
        identity_id=identity_id if identity_id is not None else "",
        db_session=db_session
    )


async def run_post_check(
    image_path: str,
    user_id: str,
    generation_id: str,
    mode: str = "REALISM",
    db_session: Optional[Any] = None
) -> PostGenerationResult:
    """
    Convenience function for post-generation check
    """
    return await dual_pipeline.post_generation_check(
        image_path=image_path,
        user_id=user_id,
        generation_id=generation_id,
        mode=mode,
        db_session=db_session
    )


# ==================== INTEGRATION EXAMPLE ====================

async def example_usage():
    """
    Example of using dual pipeline in generation flow
    """
    from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore[reportMissingImports]
    
    # Simulated parameters
    user_id = "user_123"
    prompt = "professional headshot of businessman"
    mode = "REALISM"
    identity_id = "identity_456"
    db_session = None  # Replace with actual session
    
    # ===== STAGE 1: PRE-GENERATION =====
    pre_check = await dual_pipeline.pre_generation_check(
        user_id=user_id,
        prompt=prompt,
        mode=mode,
        identity_id=identity_id,
        db_session=db_session
    )
    
    if not pre_check.allowed:
        print(f"❌ Generation blocked: {pre_check.reason}")
        return {
            "success": False,
            "error": pre_check.reason,
            "violations": pre_check.violations
        }
    
    # ===== GENERATE IMAGE =====
    print("✓ Pre-checks passed - generating image...")
    # generated_image_path = await generate_image(...)
    generated_image_path = "/path/to/generated.png"
    generation_id = "gen_789"
    
    # ===== STAGE 2: POST-GENERATION =====
    post_check = await dual_pipeline.post_generation_check(
        image_path=generated_image_path,
        user_id=user_id,
        generation_id=generation_id,
        mode=mode,
        db_session=db_session
    )
    
    if not post_check.safe:
        print(f"❌ Generated image blocked: {post_check.action}")
        return {
            "success": False,
            "error": f"Image {post_check.action.lower()}",
            "violations": post_check.violations
        }
    
    print("[OK] All safety checks passed!")
    return {
        "success": True,
        "image_path": generated_image_path,
        "generation_id": generation_id
    }
