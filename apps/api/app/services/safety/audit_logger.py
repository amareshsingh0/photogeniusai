"""
Comprehensive Safety Audit Logging System for PhotoGenius AI
Logs all safety checks with retention policies and analytics
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import json
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Types of audit events"""
    # Pre-generation
    PRE_GEN_BLOCK = "PRE_GEN_BLOCK"
    PRE_GEN_ALLOW = "PRE_GEN_ALLOW"
    PROMPT_VIOLATION = "PROMPT_VIOLATION"
    RATE_LIMIT = "RATE_LIMIT"
    USER_BANNED = "USER_BANNED"
    
    # Post-generation
    POST_GEN_BLOCK = "POST_GEN_BLOCK"
    POST_GEN_QUARANTINE = "POST_GEN_QUARANTINE"
    POST_GEN_ALLOW = "POST_GEN_ALLOW"
    NSFW_DETECTED = "NSFW_DETECTED"
    UNDERAGE_DETECTED = "UNDERAGE_DETECTED"
    
    # User actions
    STRIKE_ADDED = "STRIKE_ADDED"
    STRIKE_REMOVED = "STRIKE_REMOVED"
    USER_APPEAL = "USER_APPEAL"
    
    # System
    SYSTEM_ERROR = "SYSTEM_ERROR"

@dataclass
class AuditLogEntry:
    """Single audit log entry"""
    event_type: str
    user_id: Optional[str]
    generation_id: Optional[str]
    stage: str  # PRE_GENERATION or POST_GENERATION
    action: str  # ALLOW, BLOCK, QUARANTINE
    violations: Optional[Dict]
    scores: Optional[Dict]
    prompt: Optional[str]
    image_url: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Optional[Dict]
    timestamp: datetime
    expires_at: datetime

class SafetyAuditLogger:
    """
    Safety audit logger with retention and analytics
    
    Features:
    - 180-day retention policy
    - Query capabilities
    - Analytics aggregation
    - Export functionality
    - Privacy compliance
    - Performance optimization
    """
    
    RETENTION_DAYS = 180
    
    def __init__(self, log_dir: Optional[str] = None):
        """
        Initialize audit logger
        
        Args:
            log_dir: Directory for file logging (defaults to ./logs/safety)
        """
        # Use provided log dir or default to project logs directory
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            # Default to logs directory in project root
            project_root = Path(__file__).resolve().parents[4]  # safety -> services -> app -> api -> root
            self.log_dir = project_root / "logs" / "safety"
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            "total_logs": 0,
            "blocks": 0,
            "quarantines": 0,
            "strikes": 0,
        }
        
        logger.info(f"Safety Audit Logger initialized (log_dir: {self.log_dir})")
    
    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        generation_id: Optional[str] = None,
        stage: Optional[str] = None,
        action: Optional[str] = None,
        violations: Optional[Dict] = None,
        scores: Optional[Dict] = None,
        prompt: Optional[str] = None,
        image_url: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict] = None,
        db_session: Any = None
    ):
        """
        Log safety audit event
        
        Args:
            event_type: Type of event
            user_id: User ID (optional)
            generation_id: Generation ID (optional)
            stage: Safety stage
            action: Action taken
            violations: Safety violations
            scores: Safety scores
            prompt: User prompt (truncated)
            image_url: Generated image URL
            ip_address: Client IP
            user_agent: Client user agent
            metadata: Additional metadata
            db_session: Database session
        """
        try:
            # Create log entry
            now = datetime.utcnow()
            expires_at = now + timedelta(days=self.RETENTION_DAYS)
            
            entry = AuditLogEntry(
                event_type=event_type.value,
                user_id=user_id,
                generation_id=generation_id,
                stage=stage or "UNKNOWN",
                action=action or "UNKNOWN",
                violations=violations,
                scores=scores,
                prompt=prompt[:500] if prompt else None,  # Truncate for privacy
                image_url=image_url,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,  # Truncate
                metadata=metadata,
                timestamp=now,
                expires_at=expires_at
            )
            
            # Save to database
            await self._save_to_db(entry, db_session)
            
            # Update statistics
            self.stats["total_logs"] += 1
            if action == "BLOCK":
                self.stats["blocks"] += 1
            elif action == "QUARANTINE":
                self.stats["quarantines"] += 1
            elif event_type == AuditEventType.STRIKE_ADDED:
                self.stats["strikes"] += 1
            
            # Log to file for redundancy
            self._log_to_file(entry)
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}", exc_info=True)
    
    async def _save_to_db(
        self,
        entry: AuditLogEntry,
        db_session: Any
    ):
        """Save audit log to database"""
        try:
            if db_session is None:
                # If no session provided, skip DB save (file logging still happens)
                logger.debug(f"Audit log skipped DB (no session): {entry.event_type}")
                return
            
            from app.models.safety import SafetyAuditLog
            
            audit_log = SafetyAuditLog(
                event_type=entry.event_type,
                user_id=entry.user_id,
                generation_id=entry.generation_id,
                stage=entry.stage,
                action=entry.action,
                violations=entry.violations,
                scores=entry.scores,
                prompt=entry.prompt,
                image_url=entry.image_url,
                ip_address=entry.ip_address,
                user_agent=entry.user_agent,
                extra_metadata=entry.metadata,  # Maps to 'metadata' column in DB
                timestamp=entry.timestamp,
                expires_at=entry.expires_at
            )
            db_session.add(audit_log)
            await db_session.flush()
            
            logger.debug(f"Audit log saved to DB: {entry.event_type}")
            
        except Exception as e:
            logger.error(f"Failed to save audit log to DB: {e}", exc_info=True)
    
    def _log_to_file(self, entry: AuditLogEntry):
        """Log to file for redundancy"""
        try:
            # Daily log file
            log_file = self.log_dir / f"safety_{entry.timestamp.date()}.log"
            
            # Convert entry to dict and serialize
            entry_dict = asdict(entry)
            # Convert datetime objects to ISO strings
            entry_dict["timestamp"] = entry.timestamp.isoformat()
            entry_dict["expires_at"] = entry.expires_at.isoformat()
            
            # Append to file
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry_dict, default=str) + "\n")
                
        except Exception as e:
            logger.error(f"Failed to log to file: {e}", exc_info=True)
    
    # ==================== QUERY METHODS ====================
    
    async def query_by_user(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        limit: int = 100,
        db_session: Any = None
    ) -> List[Dict]:
        """
        Query audit logs by user
        
        Args:
            user_id: User ID
            start_date: Start date filter
            end_date: End date filter
            event_types: Filter by event types
            limit: Max results
            db_session: Database session
            
        Returns:
            List of audit log entries as dictionaries
        """
        try:
            if db_session is None:
                logger.warning("No database session provided for query")
                return []
            
            from app.models.safety import SafetyAuditLog
            from sqlalchemy import select, and_  # type: ignore[reportMissingImports]
            
            conditions = [SafetyAuditLog.user_id == user_id]
            
            if start_date:
                conditions.append(SafetyAuditLog.timestamp >= start_date)
            if end_date:
                conditions.append(SafetyAuditLog.timestamp <= end_date)
            if event_types:
                event_type_values = [e.value for e in event_types]
                conditions.append(SafetyAuditLog.event_type.in_(event_type_values))
            
            query = select(SafetyAuditLog).where(and_(*conditions))
            query = query.order_by(SafetyAuditLog.timestamp.desc()).limit(limit)
            
            result = await db_session.execute(query)
            logs = result.scalars().all()
            
            return [log.to_dict() for log in logs]
            
        except Exception as e:
            logger.error(f"Failed to query logs by user: {e}", exc_info=True)
            return []
    
    async def query_by_generation(
        self,
        generation_id: str,
        db_session: Any = None
    ) -> List[Dict]:
        """
        Query all audit logs for a specific generation
        
        Args:
            generation_id: Generation ID
            db_session: Database session
            
        Returns:
            List of audit log entries for this generation
        """
        try:
            if db_session is None:
                logger.warning("No database session provided for query")
                return []
            
            from app.models.safety import SafetyAuditLog
            from sqlalchemy import select  # type: ignore[reportMissingImports]
            
            query = select(SafetyAuditLog).where(
                SafetyAuditLog.generation_id == generation_id
            ).order_by(SafetyAuditLog.timestamp.asc())
            
            result = await db_session.execute(query)
            logs = result.scalars().all()
            
            return [log.to_dict() for log in logs]
        except Exception as e:
            logger.error(f"Failed to query logs by generation: {e}", exc_info=True)
            return []
    
    async def query_violations(
        self,
        violation_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        db_session: Any = None
    ) -> List[Dict]:
        """
        Query logs by violation type
        
        Args:
            violation_type: e.g., "CELEBRITY", "NSFW", "UNDERAGE", "EXPLICIT"
            start_date: Start date filter
            end_date: End date filter
            limit: Max results
            db_session: Database session
            
        Returns:
            List of audit log entries with matching violations
        """
        try:
            if db_session is None:
                logger.warning("No database session provided for query")
                return []
            
            from app.models.safety import SafetyAuditLog
            from sqlalchemy import select, and_, text, cast  # type: ignore[reportMissingImports]
            from sqlalchemy.dialects.postgresql import JSONB  # type: ignore[reportMissingImports]
            
            # Query logs with violations containing the specified type
            # First, get all logs with violations in date range
            conditions = [SafetyAuditLog.violations.isnot(None)]
            
            if start_date:
                conditions.append(SafetyAuditLog.timestamp >= start_date)
            if end_date:
                conditions.append(SafetyAuditLog.timestamp <= end_date)
            
            # Fetch logs (we'll filter by violation type in Python for reliability)
            # This approach works with all PostgreSQL versions
            query = select(SafetyAuditLog).where(and_(*conditions))
            query = query.order_by(SafetyAuditLog.timestamp.desc()).limit(limit * 2)  # Fetch more for filtering
            
            result = await db_session.execute(query)
            all_logs = result.scalars().all()
            
            # Filter by violation type in Python
            filtered_logs = []
            for log in all_logs:
                if log.violations:
                    # Check if any violation matches the type
                    if isinstance(log.violations, list):
                        for violation in log.violations:
                            if isinstance(violation, dict) and violation.get("type") == violation_type:
                                filtered_logs.append(log)
                                break
                    elif isinstance(log.violations, dict):
                        if log.violations.get("type") == violation_type:
                            filtered_logs.append(log)
                
                # Stop if we have enough results
                if len(filtered_logs) >= limit:
                    break
            
            return [log.to_dict() for log in filtered_logs]
        except Exception as e:
            logger.error(f"Failed to query violations: {e}", exc_info=True)
            return []
    
    # ==================== ANALYTICS ====================
    
    async def get_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        db_session: Any = None
    ) -> Dict:
        """
        Get safety analytics for date range
        
        Args:
            start_date: Start date
            end_date: End date
            db_session: Database session
            
        Returns:
            Aggregated statistics dictionary
        """
        try:
            if db_session is None:
                logger.warning("No database session provided for analytics")
                return {}
            
            # Analytics structure with actual database queries:
            analytics = {
                "total_checks": 0,
                "blocks": 0,
                "quarantines": 0,
                "allows": 0,
                "by_event_type": {},
                "by_violation_type": {},
                "top_violated_prompts": [],
                "users_banned": 0,
                "strikes_added": 0,
                "nsfw_average_score": 0.0,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
            
            from app.models.safety import SafetyAuditLog
            from sqlalchemy import select, func, and_  # type: ignore[reportMissingImports]
            
            # Total checks
            total_query = select(func.count(SafetyAuditLog.id)).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date
                )
            )
            result = await db_session.execute(total_query)
            analytics["total_checks"] = result.scalar() or 0
            
            # Blocks, quarantines, allows
            action_query = select(
                SafetyAuditLog.action,
                func.count(SafetyAuditLog.id)
            ).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date
                )
            ).group_by(SafetyAuditLog.action)
            
            result = await db_session.execute(action_query)
            for action, count in result:
                if action == "BLOCK":
                    analytics["blocks"] = count
                elif action == "QUARANTINE":
                    analytics["quarantines"] = count
                elif action == "ALLOW":
                    analytics["allows"] = count
            
            # Event type breakdown
            event_query = select(
                SafetyAuditLog.event_type,
                func.count(SafetyAuditLog.id)
            ).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date
                )
            ).group_by(SafetyAuditLog.event_type)
            
            result = await db_session.execute(event_query)
            for event_type, count in result:
                analytics["by_event_type"][event_type] = count
            
            # Average NSFW score (using JSONB extraction)
            # Get all logs with scores in date range
            nsfw_logs_query = select(SafetyAuditLog.scores).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date,
                    SafetyAuditLog.scores.isnot(None)
                )
            )
            result = await db_session.execute(nsfw_logs_query)
            scores_list = result.scalars().all()
            
            # Calculate average from extracted scores
            nsfw_scores = []
            for score_obj in scores_list:
                if isinstance(score_obj, dict) and 'nsfw_score' in score_obj:
                    try:
                        nsfw_scores.append(float(score_obj['nsfw_score']))
                    except (ValueError, TypeError):
                        pass
            
            analytics["nsfw_average_score"] = (
                sum(nsfw_scores) / len(nsfw_scores) if nsfw_scores else 0.0
            )
            
            # Users banned count
            banned_query = select(func.count(SafetyAuditLog.id)).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date,
                    SafetyAuditLog.event_type == "USER_BANNED"
                )
            )
            result = await db_session.execute(banned_query)
            analytics["users_banned"] = result.scalar() or 0
            
            # Strikes added count
            strikes_query = select(func.count(SafetyAuditLog.id)).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date,
                    SafetyAuditLog.event_type == "STRIKE_ADDED"
                )
            )
            result = await db_session.execute(strikes_query)
            analytics["strikes_added"] = result.scalar() or 0
            
            # Violation type breakdown
            # Get all logs with violations in date range
            violation_logs_query = select(SafetyAuditLog.violations).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date,
                    SafetyAuditLog.violations.isnot(None)
                )
            )
            result = await db_session.execute(violation_logs_query)
            violations_list = result.scalars().all()
            
            violation_type_counts = {}
            for violations in violations_list:
                if isinstance(violations, list):
                    for violation in violations:
                        if isinstance(violation, dict):
                            v_type = violation.get("type", "UNKNOWN")
                            violation_type_counts[v_type] = \
                                violation_type_counts.get(v_type, 0) + 1
            
            analytics["by_violation_type"] = violation_type_counts
            
            # Top violated prompts (sample of blocked prompts)
            top_prompts_query = select(SafetyAuditLog.prompt).where(
                and_(
                    SafetyAuditLog.timestamp >= start_date,
                    SafetyAuditLog.timestamp <= end_date,
                    SafetyAuditLog.action == "BLOCK",
                    SafetyAuditLog.prompt.isnot(None)
                )
            ).order_by(SafetyAuditLog.timestamp.desc()).limit(10)
            
            result = await db_session.execute(top_prompts_query)
            top_prompts = [p for p in result.scalars().all() if p]
            analytics["top_violated_prompts"] = top_prompts[:5]  # Top 5
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get analytics: {e}", exc_info=True)
            return {}
    
    async def get_user_analytics(
        self,
        user_id: str,
        db_session: Any = None
    ) -> Dict:
        """
        Get safety analytics for specific user
        
        Args:
            user_id: User ID
            db_session: Database session
            
        Returns:
            User-specific analytics dictionary
        """
        try:
            if db_session is None:
                logger.warning("No database session provided for user analytics")
                return {}
            
            analytics = {
                "total_checks": 0,
                "violations": 0,
                "strikes": 0,
                "blocks": 0,
                "last_violation": None,
                "violation_types": {},
            }
            
            from app.models.safety import SafetyAuditLog
            from sqlalchemy import select  # type: ignore[reportMissingImports]
            
            # Get user's logs
            query = select(SafetyAuditLog).where(
                SafetyAuditLog.user_id == user_id
            ).order_by(SafetyAuditLog.timestamp.desc())
            
            result = await db_session.execute(query)
            logs = result.scalars().all()
            
            analytics["total_checks"] = len(logs)
            
            for log in logs:
                if log.action == "BLOCK":
                    analytics["blocks"] += 1
                if log.violations:
                    analytics["violations"] += 1
                    if not analytics["last_violation"]:
                        analytics["last_violation"] = log.timestamp.isoformat() if log.timestamp else None
                    # Count violation types
                    if isinstance(log.violations, list):
                        for violation in log.violations:
                            if isinstance(violation, dict):
                                v_type = violation.get("type", "UNKNOWN")
                                analytics["violation_types"][v_type] = \
                                    analytics["violation_types"].get(v_type, 0) + 1
                if log.event_type == "STRIKE_ADDED":
                    analytics["strikes"] += 1
            
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get user analytics: {e}", exc_info=True)
            return {}
    
    # ==================== RETENTION & CLEANUP ====================
    
    async def cleanup_expired_logs(
        self,
        db_session: Any = None
    ) -> int:
        """
        Delete logs older than retention period
        
        Args:
            db_session: Database session
            
        Returns:
            Number of deleted logs
        """
        try:
            if db_session is None:
                logger.warning("No database session provided for cleanup")
                return 0
            
            cutoff_date = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS)
            
            from app.models.safety import SafetyAuditLog
            from sqlalchemy import delete  # type: ignore[reportMissingImports]
            
            delete_query = delete(SafetyAuditLog).where(
                SafetyAuditLog.expires_at < cutoff_date
            )
            
            result = await db_session.execute(delete_query)
            await db_session.commit()
            
            deleted_count = result.rowcount
            
            logger.info(f"Cleaned up {deleted_count} expired audit logs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired logs: {e}", exc_info=True)
            return 0
    
    # ==================== EXPORT ====================
    
    async def export_logs(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        format: str = "json",
        db_session: Any = None
    ) -> bytes:
        """
        Export audit logs
        
        Args:
            user_id: Optional user filter
            start_date: Start date
            end_date: End date
            format: Export format (json, csv)
            db_session: Database session
            
        Returns:
            Exported data as bytes
        """
        try:
            if db_session is None:
                logger.warning("No database session provided for export")
                return b""
            
            # Query logs - handle case where user_id is None (query all users)
            from app.models.safety import SafetyAuditLog
            from sqlalchemy import select, and_  # type: ignore[reportMissingImports]
            
            conditions = []
            if user_id:
                conditions.append(SafetyAuditLog.user_id == user_id)
            if start_date:
                conditions.append(SafetyAuditLog.timestamp >= start_date)
            if end_date:
                conditions.append(SafetyAuditLog.timestamp <= end_date)
            
            query = select(SafetyAuditLog)
            if conditions:
                query = query.where(and_(*conditions))
            query = query.order_by(SafetyAuditLog.timestamp.desc()).limit(10000)
            
            result = await db_session.execute(query)
            logs_objects = result.scalars().all()
            logs = [log.to_dict() for log in logs_objects]
            
            if format == "json":
                return json.dumps(logs, indent=2, default=str).encode('utf-8')
            
            elif format == "csv":
                import csv
                import io
                
                if not logs:
                    return b""
                
                output = io.StringIO()
                
                # Get all possible fieldnames from logs
                fieldnames = set()
                for log in logs:
                    fieldnames.update(log.keys())
                fieldnames = sorted(list(fieldnames))
                
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for log in logs:
                    # Convert dict values to strings
                    row = {}
                    for key, value in log.items():
                        if isinstance(value, (dict, list)):
                            row[key] = json.dumps(value)
                        elif value is None:
                            row[key] = ""
                        else:
                            row[key] = str(value)
                    writer.writerow(row)
                
                return output.getvalue().encode('utf-8')
            
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            logger.error(f"Failed to export logs: {e}", exc_info=True)
            return b""
    
    def get_statistics(self) -> Dict:
        """Get audit logger statistics"""
        return self.stats.copy()


# ==================== GLOBAL INSTANCE ====================

audit_logger = SafetyAuditLogger()


# ==================== INTEGRATION EXAMPLE ====================

async def log_safety_check_example():
    """
    Example of logging safety checks with dual pipeline
    """
    from .dual_pipeline import dual_pipeline, SafetyStage
    
    # After pre-generation check
    pre_result = await dual_pipeline.pre_generation_check(
        user_id="user_123",
        prompt="test prompt",
        mode="REALISM",
        identity_id="identity_456",
        db_session=None
    )
    
    # Log the result
    await audit_logger.log_event(
        event_type=AuditEventType.PRE_GEN_BLOCK if not pre_result.allowed else AuditEventType.PRE_GEN_ALLOW,
        user_id="user_123",
        stage=SafetyStage.PRE_GENERATION.value,
        action="BLOCK" if not pre_result.allowed else "ALLOW",
        violations={"items": pre_result.violations} if pre_result.violations else None,
        prompt="test prompt",
        ip_address="192.168.1.1",
        metadata=pre_result.metadata
    )
