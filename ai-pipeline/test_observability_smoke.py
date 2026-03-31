"""Smoke test for observability module. Run from ai-pipeline: python test_observability_smoke.py"""
import sys
import importlib.util

spec = importlib.util.spec_from_file_location("obs", "services/observability.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["obs"] = mod
spec.loader.exec_module(mod)

RequestTracker = mod.RequestTracker
StructuredLogger = mod.StructuredLogger
Metrics = mod.Metrics
CircuitBreaker = mod.CircuitBreaker
retry_with_backoff = mod.retry_with_backoff
get_request_id = mod.get_request_id
tracked_engine_call = mod.tracked_engine_call
track_engine_call = mod.track_engine_call

# Circuit breaker smoke
cb = CircuitBreaker("test", mod.CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1))
assert cb.call(lambda: 1) == 1
n = [0]
def fail_twice():
    n[0] += 1
    if n[0] <= 2:
        raise RuntimeError("x")
    return 42
try:
    cb.call(fail_twice)
except RuntimeError:
    pass
try:
    cb.call(fail_twice)
except RuntimeError:
    pass
try:
    cb.call(lambda: 1)
except RuntimeError as e:
    assert "OPEN" in str(e)
import time
time.sleep(0.15)
assert cb.call(fail_twice) == 42

with RequestTracker() as t:
    assert get_request_id() == t.request_id
log = StructuredLogger("test")
log.info("hello", mode="REALISM")
Metrics.requests_total.labels(mode="REALISM", quality_tier="BALANCED", status="success").inc()

@track_engine_call("test_engine")
def foo():
    return 42

assert foo() == 42

def raises():
    raise ValueError("x")

try:
    tracked_engine_call("test", raises)
except ValueError:
    pass

print("observability smoke OK")
