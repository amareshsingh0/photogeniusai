"""
Job management and status tracking.
Uses local/EFS storage (DATA_DIR). No Modal. AWS-compatible.
"""

import time
import uuid
from typing import Dict, Optional

from .storage import api_data_volume


class JobManager:
    """Manages job status and results"""
    
    def __init__(self):
        self.jobs_file = "/data/jobs.json"
    
    def _load_jobs(self) -> Dict:
        """Load jobs from volume"""
        try:
            if api_data_volume.exists(self.jobs_file):
                import json
                with api_data_volume.open(self.jobs_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_jobs(self, jobs: Dict):
        """Save jobs to volume"""
        try:
            import json
            with api_data_volume.open(self.jobs_file, "w") as f:
                json.dump(jobs, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save jobs: {e}")
    
    def create_job(
        self,
        user_id: str,
        job_type: str,
        request_data: dict
    ) -> str:
        """Create a new job"""
        job_id = f"{job_type}_{uuid.uuid4().hex[:12]}"
        
        jobs = self._load_jobs()
        jobs[job_id] = {
            "user_id": user_id,
            "job_type": job_type,
            "status": "pending",
            "progress": 0,
            "request_data": request_data,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self._save_jobs(jobs)
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        jobs = self._load_jobs()
        return jobs.get(job_id)
    
    def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: int = 0,
        results: Optional[list] = None,
        error: Optional[str] = None
    ):
        """Update job status"""
        jobs = self._load_jobs()
        
        if job_id not in jobs:
            return
        
        jobs[job_id]["status"] = status
        jobs[job_id]["progress"] = progress
        jobs[job_id]["updated_at"] = time.time()
        
        if results is not None:
            jobs[job_id]["results"] = results
        
        if error is not None:
            jobs[job_id]["error"] = error
        
        if status in ["completed", "failed", "cancelled"]:
            jobs[job_id]["completed_at"] = time.time()
        
        self._save_jobs(jobs)


# Global instance
_job_manager = None

def get_job_manager() -> JobManager:
    """Get or create job manager instance"""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
