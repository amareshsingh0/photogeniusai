"""
PhotoGenius AI - Comprehensive Health Check System

Provides health endpoints for all AI services for beta deployment monitoring.
Uses HTTP checks to service URLs (env SERVICE_URL_*) and Redis/S3. No Modal. AWS-compatible.
"""

import os
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

try:
    from fastapi import FastAPI, Query  # type: ignore[reportMissingImports]
    from fastapi.responses import JSONResponse  # type: ignore[reportMissingImports]
except ImportError:
    FastAPI = None  # type: ignore[misc, assignment]
    Query = None  # type: ignore[misc, assignment]
    JSONResponse = None  # type: ignore[misc, assignment]


class ServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health status for a single service"""

    name: str
    status: ServiceStatus
    latency_ms: Optional[float] = None
    message: Optional[str] = None
    last_check: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemHealth:
    """Overall system health"""

    status: ServiceStatus
    services: List[ServiceHealth]
    timestamp: str
    version: str = "1.0.0"


# Service registry: env SERVICE_URL_<NAME> for HTTP health check (e.g. SERVICE_URL_ORCHESTRATOR)
SERVICE_REGISTRY = {
    "orchestrator": {"env_key": "SERVICE_URL_ORCHESTRATOR"},
    "identity_v2": {"env_key": "SERVICE_URL_IDENTITY_V2"},
    "creative": {"env_key": "SERVICE_URL_CREATIVE"},
    "realtime": {"env_key": "SERVICE_URL_REALTIME"},
    "ultra_high_res": {"env_key": "SERVICE_URL_ULTRA_HIGH_RES"},
    "composition": {"env_key": "SERVICE_URL_COMPOSITION"},
    "finish": {"env_key": "SERVICE_URL_FINISH"},
    "refinement": {"env_key": "SERVICE_URL_REFINEMENT"},
    "quality_scorer": {"env_key": "SERVICE_URL_QUALITY_SCORER"},
    "text_renderer": {"env_key": "SERVICE_URL_TEXT_RENDERER"},
}


async def check_service_health(
    service_name: str, config: Dict[str, Any], timeout: float = 10.0
) -> ServiceHealth:
    """
    Check health of a single service via HTTP (AWS/ECS/Lambda URL) or report not configured.
    """
    start_time = time.time()
    url = os.environ.get(config.get("env_key", ""))

    if not url:
        return ServiceHealth(
            name=service_name,
            status=ServiceStatus.UNKNOWN,
            message="Service URL not configured (set env SERVICE_URL_*)",
            last_check=datetime.utcnow().isoformat(),
        )

    try:
        import httpx  # type: ignore[reportMissingImports]

        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                url.rstrip("/") + "/health" if not url.endswith("health") else url
            )
        latency = (time.time() - start_time) * 1000
        status = (
            ServiceStatus.HEALTHY if r.status_code == 200 else ServiceStatus.DEGRADED
        )
        return ServiceHealth(
            name=service_name,
            status=status,
            latency_ms=round(latency, 2),
            message=None if r.status_code == 200 else f"HTTP {r.status_code}",
            last_check=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        return ServiceHealth(
            name=service_name,
            status=ServiceStatus.UNHEALTHY,
            message=f"Error: {str(e)[:100]}",
            last_check=datetime.utcnow().isoformat(),
        )


async def check_all_services(
    services: Optional[List[str]] = None, parallel: bool = True
) -> SystemHealth:
    """Check health of all services."""
    services_to_check = services or list(SERVICE_REGISTRY.keys())
    configs = {
        name: SERVICE_REGISTRY[name]
        for name in services_to_check
        if name in SERVICE_REGISTRY
    }

    if parallel:
        tasks = [
            check_service_health(name, configs[name])
            for name in services_to_check
            if name in configs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        service_healths = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                service_healths.append(
                    ServiceHealth(
                        name=services_to_check[i],
                        status=ServiceStatus.UNKNOWN,
                        message=f"Check failed: {str(result)[:100]}",
                        last_check=datetime.utcnow().isoformat(),
                    )
                )
            else:
                service_healths.append(result)
    else:
        service_healths = []
        for name in services_to_check:
            if name in configs:
                result = await check_service_health(name, configs[name])
                service_healths.append(result)

    unhealthy_count = sum(
        1 for s in service_healths if s.status == ServiceStatus.UNHEALTHY
    )
    degraded_count = sum(
        1 for s in service_healths if s.status == ServiceStatus.DEGRADED
    )

    if unhealthy_count > len(service_healths) // 2:
        overall_status = ServiceStatus.UNHEALTHY
    elif unhealthy_count > 0 or degraded_count > 0:
        overall_status = ServiceStatus.DEGRADED
    else:
        overall_status = ServiceStatus.HEALTHY

    return SystemHealth(
        status=overall_status,
        services=service_healths,
        timestamp=datetime.utcnow().isoformat(),
    )


def check_external_dependencies() -> Dict[str, Any]:
    """Check external dependencies (Redis, S3)."""
    dependencies = {}

    try:
        import redis  # type: ignore[reportMissingImports]

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url, socket_timeout=5)
        r.ping()
        dependencies["redis"] = {"status": "healthy", "url": redis_url[:30] + "..."}
    except Exception as e:
        dependencies["redis"] = {"status": "unhealthy", "error": str(e)[:50]}

    try:
        import boto3  # type: ignore[reportMissingImports]

        s3 = boto3.client("s3")
        bucket = os.environ.get("S3_BUCKET", "photogenius-generated")
        s3.head_bucket(Bucket=bucket)
        dependencies["s3"] = {"status": "healthy", "bucket": bucket}
    except Exception as e:
        dependencies["s3"] = {"status": "degraded", "error": str(e)[:50]}

    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        dependencies["database"] = {"status": "configured", "type": "postgresql"}
    else:
        dependencies["database"] = {"status": "not_configured"}

    return dependencies


async def health_check(
    services: Optional[List[str]] = None, include_dependencies: bool = False
) -> Dict[str, Any]:
    """Main health check. Returns response dict. No Modal .remote()."""
    system_health = await check_all_services(services)
    response = {
        "status": system_health.status.value,
        "timestamp": system_health.timestamp,
        "version": system_health.version,
        "services": [
            {
                "name": s.name,
                "status": s.status.value,
                "latency_ms": s.latency_ms,
                "message": s.message,
            }
            for s in system_health.services
        ],
        "summary": {
            "total": len(system_health.services),
            "healthy": sum(
                1 for s in system_health.services if s.status == ServiceStatus.HEALTHY
            ),
            "degraded": sum(
                1 for s in system_health.services if s.status == ServiceStatus.DEGRADED
            ),
            "unhealthy": sum(
                1 for s in system_health.services if s.status == ServiceStatus.UNHEALTHY
            ),
        },
    }
    if include_dependencies:
        response["dependencies"] = check_external_dependencies()
    return response


# ==================== FastAPI (run with uvicorn) ====================

if FastAPI is not None and Query is not None and JSONResponse is not None:
    _Query = Query
    _JSONResponse = JSONResponse
    health_api = FastAPI(
        title="PhotoGenius Health API",
        description="Health check endpoints for PhotoGenius AI services",
        version="1.0.0",
    )

    @health_api.get("/health")
    async def api_health(
        services: Optional[str] = _Query(
            None, description="Comma-separated list of services"
        ),
        dependencies: bool = _Query(False, description="Include dependency checks"),
    ):
        service_list = [s.strip() for s in services.split(",")] if services else None
        try:
            result = await health_check(
                services=service_list, include_dependencies=dependencies
            )
            status_code = 200 if result["status"] == "healthy" else 503
            return _JSONResponse(content=result, status_code=status_code)
        except Exception as e:
            return _JSONResponse(
                content={"status": "error", "message": str(e)}, status_code=500
            )

    @health_api.get("/ping")
    async def api_ping():
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    @health_api.get("/ready")
    async def api_ready():
        try:
            result = await health_check(
                services=["orchestrator", "identity_v2", "realtime"],
                include_dependencies=False,
            )
            if result["summary"]["healthy"] >= 2:
                return {"status": "ready"}
            return _JSONResponse(
                content={"status": "not_ready", "reason": "Core services unhealthy"},
                status_code=503,
            )
        except Exception as e:
            return _JSONResponse(
                content={"status": "not_ready", "error": str(e)}, status_code=503
            )

else:
    health_api = None  # type: ignore[assignment]


if __name__ == "__main__":
    import asyncio

    async def main():
        print("Testing health check system...")
        result = await check_all_services()
        print(f"\nOverall status: {result.status.value}")
        for service in result.services:
            print(
                f"  - {service.name}: {service.status.value} ({service.latency_ms}ms)"
            )
        print("\nDependencies:")
        for name, status in check_external_dependencies().items():
            print(f"  - {name}: {status}")

    asyncio.run(main())
