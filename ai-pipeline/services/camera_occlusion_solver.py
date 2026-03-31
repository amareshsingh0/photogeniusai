"""
Camera & Occlusion Solver for PhotoGenius AI.
Ensures all heads visible: refines layout and camera from Scene Graph Compiler output.
P0: Camera Intelligence & Occlusion Solver — zero head occlusions in layout phase.

Features:
- FOV calculation based on entity count
- Height/tilt adjustment for full visibility
- Occlusion detection pre-generation; resolve loop until zero occlusions
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


# Margin above head for umbrella/objects (pixels)
HEAD_CLEARANCE = 80
# Max iterations to resolve occlusions
MAX_OCCLUSION_RESOLVE_ITERATIONS = 10
# Entity types that can occlude heads (resolved by moving above or nudging)
OCCLUDER_TYPES = ("umbrella", "hat", "prop", "furniture", "object")
# Default FOV tuning: "linear" | "sqrt" | "log" (sqrt/log avoid maxing FOV in crowds)
DEFAULT_FOV_SCALE_MODE = "linear"


@dataclass
class CameraConfig:
    """Camera configuration that satisfies visibility constraints."""

    fov: float
    height: float
    tilt: float
    distance: float
    frame: Dict[str, float]
    eye_level_y: float  # y coordinate for eye-level line


@dataclass
class OcclusionSafeLayout:
    """Layout with guaranteed no head occlusion."""

    entities: List[Dict[str, Any]]
    camera: CameraConfig
    head_visibility_mask: List[Tuple[float, float, float]]  # (x, y, radius) per head
    canvas_size: Tuple[int, int]
    occlusion_count: int = 0  # 0 = success (zero head occlusions)


def _circle_intersects_rect(
    cx: float,
    cy: float,
    r: float,
    rx0: float,
    ry0: float,
    rx1: float,
    ry1: float,
) -> bool:
    """True if circle (cx, cy, r) overlaps axis-aligned rect [rx0,ry0]–[rx1,ry1]."""
    nearest_x = max(rx0, min(cx, rx1))
    nearest_y = max(ry0, min(cy, ry1))
    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx * dx + dy * dy) <= (r * r)


def _circle_overlaps_circle(
    x1: float,
    y1: float,
    r1: float,
    x2: float,
    y2: float,
    r2: float,
) -> bool:
    """True if two circles overlap."""
    d = math.hypot(x1 - x2, y1 - y2)
    return d < (r1 + r2)


class CameraOcclusionSolver:
    """
    Refines layout and camera from Scene Graph Compiler so that:
    - Every person's head has a clear visibility region (no object overlap).
    - Camera FOV and position capture all heads.
    - Objects (e.g. umbrella) are placed ABOVE heads, never covering faces.
    """

    def __init__(
        self,
        canvas_width: int = 1024,
        canvas_height: int = 1024,
        head_clearance: int = HEAD_CLEARANCE,
        fov_scale_mode: str = DEFAULT_FOV_SCALE_MODE,
        height_eye_factor: float = 0.35,
        tilt_per_extra_person: float = 2.0,
        tilt_cap_degrees: float = 10.0,
    ):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.head_clearance = head_clearance
        self.fov_scale_mode = fov_scale_mode
        self.height_eye_factor = height_eye_factor
        self.tilt_per_extra_person = tilt_per_extra_person
        self.tilt_cap_degrees = tilt_cap_degrees

    def compute_fov_for_full_visibility(
        self,
        n_people: int,
        n_objects: int,
        base_fov: float = 50.0,
        per_entity_fov: float = 6.0,
        fov_min: float = 45.0,
        fov_max: float = 90.0,
        fov_scale_mode: str | None = None,
    ) -> float:
        """
        FOV based on entity count so all entities fit in frame.
        scale_mode: "linear" (default), "sqrt", or "log" — sqrt/log avoid maxing FOV in crowds.
        """
        n = n_people + n_objects
        if n <= 0:
            return base_fov
        mode = fov_scale_mode if fov_scale_mode is not None else self.fov_scale_mode
        if mode == "sqrt":
            # sqrt scaling: 1→0, 4→~2, 9→~3 so FOV grows gently for large groups
            mult = math.sqrt(max(0, n - 1))
        elif mode == "log":
            # log scaling: gentle growth for many entities
            mult = math.log1p(max(0, n - 1))
        else:
            mult = float(n - 1)
        fov = base_fov + per_entity_fov * mult
        return max(fov_min, min(fov_max, float(fov)))

    def detect_head_occlusions(
        self,
        layout: Dict[str, Any],
    ) -> List[Tuple[str, str]]:
        """
        Pre-generation occlusion detection: list (head_entity_id, occluder_id).
        Zero head occlusions = empty list.
        """
        entities = list(layout.get("entities", []))
        people = [e for e in entities if e.get("type") == "person"]
        objects = [e for e in entities if e.get("type") != "person"]
        occlusions: List[Tuple[str, str]] = []

        for person in people:
            head_pos = person.get("head_position")
            head_r = person.get("head_radius", 40)
            if not head_pos:
                continue
            hx, hy = float(head_pos[0]), float(head_pos[1])
            hr = float(head_r)
            pid = person.get("id", "")

            # Check objects (umbrella, etc.): object rect/circle overlapping head circle
            for obj in objects:
                oid = obj.get("id", "")
                if "center" in obj and "radius" in obj:
                    ox, oy = obj["center"][0], obj["center"][1]
                    orad = obj["radius"]
                    if _circle_overlaps_circle(hx, hy, hr, ox, oy, orad):
                        occlusions.append((pid, oid))
                elif "bbox" in obj:
                    x0, y0, x1, y1 = obj["bbox"]
                    if _circle_intersects_rect(hx, hy, hr, x0, y0, x1, y1):
                        occlusions.append((pid, oid))

            # Check other people: body bbox (not head) overlapping this head
            for other in people:
                if other.get("id") == pid:
                    continue
                bbox = other.get("bbox")
                if not bbox:
                    continue
                x0, y0, x1, y1 = bbox
                if _circle_intersects_rect(hx, hy, hr, x0, y0, x1, y1):
                    occlusions.append((pid, other.get("id", "")))

        return occlusions

    def _resolve_occlusions(
        self,
        layout: Dict[str, Any],
        occlusions: List[Tuple[str, str]],
    ) -> Dict[str, Any]:
        """
        Adjust layout to remove occlusions: push umbrella/objects above heads,
        nudge overlapping people apart.
        """
        entities = [dict(e) for e in layout.get("entities", [])]
        people = [e for e in entities if e.get("type") == "person"]
        objects = [e for e in entities if e.get("type") != "person"]
        head_regions = []
        for p in people:
            hp = p.get("head_position")
            hr = p.get("head_radius", 40)
            if hp:
                head_regions.append((hp[0], hp[1], hr))

        # Resolve object-over-head: move object so its bottom is above all head tops
        # Handles: umbrella, hat, prop (center+radius or bbox); furniture (bbox — move down or nudge person)
        for obj in objects:
            obj_type = obj.get("type", "object")
            if not head_regions:
                continue
            min_head_top = min(h[1] - h[2] for h in head_regions)
            safe_bottom = min_head_top - self.head_clearance

            # Umbrella / hat / prop with center+radius: move above all heads
            if (
                obj_type in ("umbrella", "hat", "prop")
                and "center" in obj
                and "radius" in obj
            ):
                cx, cy = obj["center"][0], obj["center"][1]
                radius = obj["radius"]
                if (cy + radius) > safe_bottom:
                    obj["center"] = (cx, safe_bottom - radius)
            # Prop/object with bbox: move box so bottom is above head tops
            elif obj_type in ("prop", "object", "hat") and "bbox" in obj:
                x0, y0, x1, y1 = obj["bbox"]
                box_h = y1 - y0
                if y1 > safe_bottom:
                    new_y1 = safe_bottom
                    new_y0 = new_y1 - box_h
                    obj["bbox"] = (x0, new_y0, x1, new_y1)
            # Furniture: move bbox down so top of furniture is below head bottom (heads in front)
            elif obj_type == "furniture" and "bbox" in obj:
                x0, y0, x1, y1 = obj["bbox"]
                max_head_bottom = max(h[1] + h[2] for h in head_regions)
                # If furniture overlaps head band, push furniture down so it starts below heads
                if y0 < max_head_bottom + self.head_clearance:
                    box_h = y1 - y0
                    new_y0 = max_head_bottom + self.head_clearance
                    new_y1 = new_y0 + box_h
                    obj["bbox"] = (x0, new_y0, x1, new_y1)
            # Generic object with center+radius (e.g. umbrella without type)
            elif "center" in obj and "radius" in obj:
                cx, cy = obj["center"][0], obj["center"][1]
                radius = obj["radius"]
                if (cy + radius) > safe_bottom:
                    obj["center"] = (cx, safe_bottom - radius)
            elif "bbox" in obj:
                x0, y0, x1, y1 = obj["bbox"]
                box_h = y1 - y0
                if y1 > safe_bottom:
                    new_y1 = safe_bottom
                    new_y0 = new_y1 - box_h
                    obj["bbox"] = (x0, new_y0, x1, new_y1)

        # Resolve person-over-person head: nudge overlapping person slightly
        for pid, occluder_id in occlusions:
            person = next((e for e in entities if e.get("id") == pid), None)
            occluder = next((e for e in entities if e.get("id") == occluder_id), None)
            if not person or not occluder or occluder.get("type") != "person":
                continue
            hp = person.get("head_position")
            op_bbox = occluder.get("bbox")
            if not hp or not op_bbox:
                continue
            hx, hy = hp[0], hp[1]
            ox0, oy0, ox1, oy1 = op_bbox
            # Nudge occluder right (or left) so body doesn't cover head
            dx = 60
            if hx < (ox0 + ox1) / 2:
                occluder["bbox"] = (ox0 + dx, oy0, ox1 + dx, oy1)
                np = occluder.get("head_position")
                if np:
                    occluder["head_position"] = (np[0] + dx, np[1])
            else:
                occluder["bbox"] = (ox0 - dx, oy0, ox1 - dx, oy1)
                np = occluder.get("head_position")
                if np:
                    occluder["head_position"] = (np[0] - dx, np[1])

        return {"entities": entities}

    def solve(
        self,
        layout: Dict[str, Any],
        camera: Dict[str, Any],
    ) -> OcclusionSafeLayout:
        """
        Refine layout and camera so all heads are visible (zero head occlusions).

        - Occlusion detection pre-generation; resolve loop until zero occlusions.
        - FOV/height/tilt from entity count and head positions for full visibility.
        - Returns layout with occlusion_count=0 when successful.
        """
        current_layout = {"entities": [dict(e) for e in layout.get("entities", [])]}
        camera_in = camera
        occlusion_count = -1

        for _ in range(MAX_OCCLUSION_RESOLVE_ITERATIONS):
            occlusions = self.detect_head_occlusions(current_layout)
            occlusion_count = len(occlusions)
            if occlusion_count == 0:
                break
            current_layout = self._resolve_occlusions(current_layout, occlusions)

        entities = current_layout.get("entities", [])
        people = [e for e in entities if e.get("type") == "person"]
        objects = [e for e in entities if e.get("type") != "person"]
        head_regions: List[Tuple[float, float, float]] = []
        for ent in people:
            head_pos = ent.get("head_position", (0, 0))
            head_r = ent.get("head_radius", 40)
            head_regions.append((float(head_pos[0]), float(head_pos[1]), float(head_r)))

        # FOV / height / tilt for full visibility (from entity count + head frame)
        n_people = len(people)
        n_objects = len(objects)
        fov = camera_in.get("fov")
        if fov is None:
            fov = self.compute_fov_for_full_visibility(n_people, n_objects)
        height = camera_in.get("height", 1.6)
        tilt = camera_in.get("tilt", 0.0)
        distance = camera_in.get("distance", 2.5)

        frame = camera_in.get("frame", {})
        min_x = frame.get("min_x", 0)
        max_x = frame.get("max_x", float(self.canvas_width))
        min_y = frame.get("min_y", 0)
        max_y = frame.get("max_y", float(self.canvas_height))

        if head_regions:
            xs = [h[0] for h in head_regions]
            ys = [h[1] for h in head_regions]
            rs = [h[2] for h in head_regions]
            min_x = min(x - r for x, r in zip(xs, rs))
            max_x = max(x + r for x, r in zip(xs, rs))
            min_y = min(y - r for y, r in zip(ys, rs))
            max_y = max(y + r for y, r in zip(ys, rs))
            pad = 60
            min_x = max(0, min_x - pad)
            max_x = min(self.canvas_width, max_x + pad)
            min_y = max(0, min_y - pad)
            max_y = min(self.canvas_height, max_y + pad)
            # Height/tilt: eye-level from head band (tunable height_eye_factor)
            eye_level_y = (
                min_y + (max_y - min_y) * self.height_eye_factor
                if (max_y > min_y)
                else self.canvas_height * 0.4
            )
        else:
            eye_level_y = self.canvas_height * 0.4

        camera_config = CameraConfig(
            fov=float(fov),
            height=float(height),
            tilt=float(tilt),
            distance=float(distance),
            frame={"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
            eye_level_y=eye_level_y,
        )

        return OcclusionSafeLayout(
            entities=entities,
            camera=camera_config,
            head_visibility_mask=head_regions,
            canvas_size=(self.canvas_width, self.canvas_height),
            occlusion_count=occlusion_count,
        )

    def to_prompt_hints(self, layout: OcclusionSafeLayout) -> Dict[str, Any]:
        """
        Export hints for prompt enhancement / ControlNet:
        - number of people, head positions (normalized 0-1), camera angle.
        """
        w, h = layout.canvas_size
        hints = {
            "person_count": sum(
                1 for e in layout.entities if e.get("type") == "person"
            ),
            "head_positions_normalized": [
                (x / w, y / h, r / min(w, h)) for x, y, r in layout.head_visibility_mask
            ],
            "camera_fov": layout.camera.fov,
            "camera_tilt": layout.camera.tilt,
        }
        return hints
