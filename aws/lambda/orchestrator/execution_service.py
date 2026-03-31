"""
Engine execution orchestration.

Wraps engine invocations (realtime, ultra, identity_v2, etc.) with tracing/metrics.
Supports registered callables and optional async execute_plan via Modal App.lookup.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from services.observability import (
        Metrics,
        StructuredLogger,
        trace_function,
        track_engine_call,
        tracked_engine_call,
    )
except ImportError:
    trace_function = lambda n=None: (lambda f: f)  # type: ignore[assignment, misc]
    track_engine_call = lambda _: (lambda f: f)  # type: ignore[assignment, misc]
    tracked_engine_call = lambda _en, fn, *a, **k: fn(*a, **k)  # type: ignore[assignment, misc]
    Metrics = None  # type: ignore[assignment, misc]
    StructuredLogger = None  # type: ignore[assignment, misc]

try:
    from services.routing_service import EngineType
except ImportError:
    EngineType = None  # type: ignore[assignment, misc]


def _log():
    logger_cls = StructuredLogger
    if logger_cls is not None:
        return logger_cls(__name__)
    return logger


# Map engine name -> (modal app name, method name for .remote)
ENGINE_APP_MAP: Dict[str, tuple] = {
    "realtime": ("realtime-engine", "generate_realtime_batch"),
    "ultra_high_res": ("ultra-high-res", "generate_ultra"),
    "identity_v2": ("photogenius-identity-v2", "generate_ultimate"),
    "creative": ("photogenius-creative-engine", "generate_creative"),
    "composition": ("photogenius-composition-engine", "compose"),
    "finish": ("photogenius-finish-engine", "finish"),
    "standard": ("photogenius-generation-service", "generate"),
}


class ExecutionService:
    """Orchestrate execution across engines via injected callables."""

    def __init__(self) -> None:
        self._realtime_fn: Optional[Callable[..., Any]] = None
        self._ultra_fn: Optional[Callable[..., Any]] = None
        self._identity_v2_fn: Optional[Callable[..., Any]] = None
        self._creative_fn: Optional[Callable[..., Any]] = None
        self._composition_fn: Optional[Callable[..., Any]] = None
        self._finish_fn: Optional[Callable[..., Any]] = None
        self._engine_apps: Dict[str, Any] = {}
        self._engine_app_map: Dict[str, tuple] = dict(ENGINE_APP_MAP)
        _log().info("ExecutionService initialized")

    def _get_engine_app(self, engine: str) -> Any:
        """Resolve Modal app for engine (with caching)."""
        if engine not in self._engine_apps:
            try:
                from modal import App as ModalApp  # type: ignore[reportMissingImports]

                app_name, method_name = self._engine_app_map.get(engine, ("", ""))
                if not app_name:
                    raise RuntimeError("Unknown engine: %s" % engine)
                app = ModalApp.lookup(app_name)
                fn = getattr(app, method_name, None)
                if fn is None:
                    raise RuntimeError(
                        "App %s has no attribute %s" % (app_name, method_name)
                    )
                self._engine_apps[engine] = (app, fn)
            except Exception as e:
                _log().error("Engine lookup failed for %s: %s" % (engine, e))
                raise
        return self._engine_apps[engine]

    @trace_function("execution.execute_plan")
    async def execute_plan(
        self,
        plan: Dict[str, Any],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Execute generation plan (async). Uses Modal App.lookup when configured,
        otherwise falls back to registered callables.
        """
        _log().info("Executing generation plan")
        results: List[Dict[str, Any]] = []

        if params.get("creative", 0) > 0 or params.get("style"):
            try:
                out = await self._run_engine("creative", "creative", params)
                if isinstance(out, list):
                    results.extend(out)
                else:
                    results.append(out)  # type: ignore[arg-type]
            except Exception as e:
                _log().error("Creative engine failed: %s" % e)
                raise

        if plan.get("requires_composition") and params.get("reference_images"):
            try:
                out = await self._run_engine("composition", "composition", params)
                if isinstance(out, list):
                    results.extend(out)
                else:
                    results.append(out)  # type: ignore[arg-type]
            except Exception as e:
                _log().error("Composition engine failed: %s" % e)
                raise

        if params.get("identity_id"):
            try:
                out = await self._run_engine("identity_v2", "identity_v2", params)
                res = out.get("results", []) if isinstance(out, dict) else out
                if isinstance(res, list):
                    results.extend(res)
                else:
                    results.append(res)  # type: ignore[arg-type]
            except Exception as e:
                _log().error("Identity engine failed: %s" % e)
                raise
        elif not results:
            tier = (params.get("quality_tier") or "BALANCED").upper()
            use_standard = tier in ("BALANCED", "PREMIUM", "ULTRA")
            engine = "standard" if use_standard else "realtime"
            try:
                out = await self._run_engine(engine, engine, params)
                if isinstance(out, dict) and "images_base64" in out:
                    for b64 in out.get("images_base64") or []:
                        results.append(
                            {
                                "image_base64": b64,
                                "prompt": params.get("prompt", ""),
                                "negative_prompt": "",
                            }
                        )
                elif isinstance(out, list):
                    results.extend(out)
                else:
                    results.append(out)  # type: ignore[arg-type]
            except Exception as e:
                _log().error("%s engine failed: %s" % (engine, e))
                raise

        if plan.get("requires_finish") and results:
            raw_paths = [
                r.get("image_path") or r.get("image_base64")
                for r in results
                if r.get("image_path") or r.get("image_base64")
            ]
            img_paths: List[str] = [p for p in raw_paths if p is not None]
            if img_paths:
                up = params.get("upscale", True)
                ff = params.get("face_fix", True)
                cg = params.get("color_grade")
                finished = await asyncio.to_thread(
                    self.execute_finish,
                    img_paths,
                    up,
                    ff,
                    cg,
                )
                if isinstance(finished, list):
                    results = finished
                else:
                    results = [finished]  # type: ignore[list-item]

        return results

    async def _run_engine(
        self,
        engine: str,
        track_name: str,
        params: Dict[str, Any],
    ) -> Any:
        """Run engine via Modal lookup or registered callable."""
        attr = "_%s_fn" % engine.replace("-", "_")
        fn = getattr(self, attr, None)
        if callable(fn):
            return await asyncio.to_thread(
                tracked_engine_call,  # type: ignore[reportArgumentType]
                track_name,
                lambda: fn(**params),
            )
        _, remote_fn = self._get_engine_app(engine)
        return await asyncio.to_thread(
            tracked_engine_call,  # type: ignore[reportArgumentType]
            track_name,
            lambda: remote_fn.remote(**params),
        )

    def register_realtime(self, fn: Callable[..., Any]) -> None:
        self._realtime_fn = fn

    def register_ultra(self, fn: Callable[..., Any]) -> None:
        self._ultra_fn = fn

    def register_identity_v2(self, fn: Callable[..., Any]) -> None:
        self._identity_v2_fn = fn

    def register_creative(self, fn: Callable[..., Any]) -> None:
        self._creative_fn = fn

    def register_composition(self, fn: Callable[..., Any]) -> None:
        self._composition_fn = fn

    def register_finish(self, fn: Callable[..., Any]) -> None:
        self._finish_fn = fn

    @trace_function("execution.realtime")
    def execute_realtime(self, **params: Any) -> Any:
        """Run realtime engine. Raises if not registered."""
        if not self._realtime_fn:
            raise RuntimeError("Realtime engine not registered")
        fn = self._realtime_fn
        return tracked_engine_call("realtime", lambda: fn(**params))

    @trace_function("execution.ultra")
    def execute_ultra(self, **params: Any) -> Any:
        """Run ultra high-res engine. Raises if not registered."""
        if not self._ultra_fn:
            raise RuntimeError("Ultra high-res engine not registered")
        fn = self._ultra_fn
        return tracked_engine_call("ultra_high_res", lambda: fn(**params))

    @trace_function("execution.identity_v2")
    def execute_identity_v2(self, **params: Any) -> Any:
        """Run identity v2 engine. Raises if not registered."""
        if not self._identity_v2_fn:
            raise RuntimeError("Identity v2 engine not registered")
        fn = self._identity_v2_fn
        return tracked_engine_call("identity_v2", lambda: fn(**params))

    @trace_function("execution.creative")
    def execute_creative(self, **params: Any) -> Any:
        fn = self._creative_fn
        if fn is None:
            raise RuntimeError("Creative engine not registered")
        return tracked_engine_call("creative", lambda: fn(**params))

    @trace_function("execution.composition")
    def execute_composition(self, **params: Any) -> Any:
        if not self._composition_fn:
            raise RuntimeError("Composition engine not registered")
        fn = self._composition_fn
        return tracked_engine_call("composition", lambda: fn(**params))

    @trace_function("execution.finish")
    def execute_finish(
        self,
        image_paths: List[str],
        upscale: bool = True,
        face_fix: bool = True,
        color_grade: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not self._finish_fn:
            raise RuntimeError("Finish engine not registered")
        fn = self._finish_fn
        return tracked_engine_call(
            "finish",
            lambda: fn(
                image_paths=image_paths,
                upscale=upscale,
                face_fix=face_fix,
                color_grade=color_grade,
            ),
        )

    def has_engine(self, engine: str) -> bool:
        m = {
            "realtime": self._realtime_fn,
            "ultra_high_res": self._ultra_fn,
            "identity_v2": self._identity_v2_fn,
            "creative": self._creative_fn,
            "composition": self._composition_fn,
            "finish": self._finish_fn,
        }
        return bool(m.get(engine))
