"""
Control Image Generator for Multi-ControlNet.

Generates depth maps, OpenPose skeletons, and canny edges from scene graph.
Ensures perfect structure: all heads visible, no body merging, correct proportions.
P0: Multi-ControlNet with guided diffusion — Task 4.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np  # type: ignore[reportMissingImports]

try:
    import cv2  # type: ignore[reportMissingImports]

    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

try:
    from PIL import Image  # type: ignore[reportMissingImports]

    HAS_PIL = True
except ImportError:
    Image = None
    HAS_PIL = False


def _draw_line_numpy(
    img: np.ndarray,
    pt1: Tuple[int, int],
    pt2: Tuple[int, int],
    color: Tuple[int, ...],
    thickness: int = 2,
) -> None:
    """Draw a line on img (H,W,C) using numpy."""
    x1, y1 = int(pt1[0]), int(pt1[1])
    x2, y2 = int(pt2[0]), int(pt2[1])
    h, w = img.shape[0], img.shape[1]
    n = max(abs(x2 - x1), abs(y2 - y1), 1)
    for i in range(n + 1):
        t = i / n
        x = int(x1 + t * (x2 - x1))
        y = int(y1 + t * (y2 - y1))
        for dy in range(-thickness, thickness + 1):
            for dx in range(-thickness, thickness + 1):
                if 0 <= y + dy < h and 0 <= x + dx < w:
                    img[y + dy, x + dx] = color


def _draw_circle_numpy(
    img: np.ndarray,
    center: Tuple[int, int],
    radius: int,
    color: Tuple[int, ...],
    fill: bool = True,
) -> None:
    """Draw a circle on img (H,W,C) using numpy."""
    cy, cx = int(center[1]), int(center[0])
    h, w = img.shape[0], img.shape[1]
    Y, X = np.ogrid[:h, :w]
    mask = (X - cx) ** 2 + (Y - cy) ** 2 <= radius**2
    if fill:
        img[mask] = color
    else:
        r_out = radius + 1
        mask_out = (X - cx) ** 2 + (Y - cy) ** 2 <= r_out**2
        img[mask_out & ~mask] = color


class ControlImageGenerator:
    """
    Generate control images from scene graph layout.

    Creates:
    1. Depth map - Spatial relationships and layering
    2. OpenPose map - Complete human skeletons for each person
    3. Canny edge map - Edge preservation
    """

    def __init__(self) -> None:
        self.default_size = (1024, 1024)

    def generate_all_controls(
        self,
        scene_graph: Dict[str, Any],
        width: int = 1024,
        height: int = 1024,
    ) -> Dict[str, Any]:
        """
        Generate all control images from scene graph.

        Args:
            scene_graph: From SceneGraphCompiler
            width: Output width
            height: Output height

        Returns:
            depth: PIL Image or ndarray (grayscale depth map)
            openpose: PIL Image or ndarray (skeleton visualization)
            canny: PIL Image or ndarray (edge map)
        """
        layout = scene_graph.get("layout", {})

        if not layout or "entities" not in layout:
            return self._generate_empty_controls(width, height)

        entities = layout["entities"]

        depth_map = self._create_depth_map(entities, width, height)
        openpose_map = self._create_openpose_map(entities, width, height)
        canny_map = self._create_canny_map(openpose_map)

        if HAS_PIL and Image is not None:
            return {
                "depth": Image.fromarray(depth_map).convert("RGB"),
                "openpose": Image.fromarray(openpose_map).convert("RGB"),
                "canny": Image.fromarray(canny_map).convert("RGB"),
            }
        return {
            "depth": depth_map,
            "openpose": openpose_map,
            "canny": canny_map,
        }

    def _generate_empty_controls(self, width: int, height: int) -> Dict[str, Any]:
        """Generate empty control images (fallback)."""
        empty = np.ones((height, width, 3), dtype=np.uint8) * 128
        if HAS_PIL and Image is not None:
            img = Image.fromarray(empty)
            return {"depth": img, "openpose": img.copy(), "canny": img.copy()}
        return {
            "depth": empty.copy(),
            "openpose": empty.copy(),
            "canny": empty.copy(),
        }

    def _create_depth_map(
        self,
        entities: List[Dict[str, Any]],
        width: int,
        height: int,
    ) -> np.ndarray:
        """
        Create depth map with proper layering.

        Background: far depth (~0.85). People: foreground (~0.20–0.30).
        Objects: mid depth (~0.40). Returns (height, width, 3) uint8.
        """
        depth_map = np.ones((height, width), dtype=np.float32) * 0.85

        people = [
            e
            for e in entities
            if (e if isinstance(e, dict) else {}).get("type") == "person"
        ]
        for person in people:
            p = person if isinstance(person, dict) else getattr(person, "__dict__", {})
            bbox = p.get("bbox") if isinstance(p, dict) else None
            if not bbox or len(bbox) < 4:
                continue

            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
            x1 = max(0, min(x1, width - 1))
            x2 = max(0, min(x2, width))
            y1 = max(0, min(y1, height - 1))
            y2 = max(0, min(y2, height))

            if x2 <= x1 or y2 <= y1:
                continue

            person_height = y2 - y1
            if person_height > 0:
                depth_gradient = np.linspace(0.20, 0.30, person_height)
                for i, y in enumerate(range(y1, y2)):
                    if y < height:
                        depth_map[y, x1:x2] = depth_gradient[
                            min(i, len(depth_gradient) - 1)
                        ]

        objects = [
            e
            for e in entities
            if (e if isinstance(e, dict) else {}).get("type") in ("umbrella", "object")
        ]
        for obj in objects:
            o = obj if isinstance(obj, dict) else getattr(obj, "__dict__", {})
            if not isinstance(o, dict) or "center" not in o or "radius" not in o:
                continue
            center = o["center"]
            radius = float(o.get("radius", 50))
            cx, cy = int(center[0]), int(center[1])
            Y, X = np.ogrid[:height, :width]
            dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            mask = dist <= radius
            depth_map[mask] = 0.40

        depth_map_uint8 = (depth_map * 255).astype(np.uint8)
        depth_rgb = np.stack([depth_map_uint8] * 3, axis=-1)
        return depth_rgb

    def _create_openpose_map(
        self,
        entities: List[Dict[str, Any]],
        width: int,
        height: int,
    ) -> np.ndarray:
        """
        Create OpenPose skeleton map with complete skeletons per person.

        Each person: 1 head, spine, 2 arms, 2 legs. No merged limbs.
        Returns (height, width, 3) uint8.
        """
        pose_map = np.zeros((height, width, 3), dtype=np.uint8)
        color = (255, 255, 255)
        thickness = 5

        people = [
            e
            for e in entities
            if (e if isinstance(e, dict) else {}).get("type") == "person"
        ]

        for person in people:
            p = person if isinstance(person, dict) else getattr(person, "__dict__", {})
            if not isinstance(p, dict):
                continue

            bbox = p.get("bbox")
            head_pos = p.get("head_position")
            head_radius = int(p.get("head_radius", 20))

            if not bbox or len(bbox) < 4 or not head_pos:
                continue

            x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
            person_height = max(1, y2 - y1)
            person_width = max(1, x2 - x1)
            cx = (x1 + x2) // 2

            head_radius = max(15, min(head_radius, person_height // 5))
            head_x, head_y = int(head_pos[0]), int(head_pos[1])
            head_pos_int = (head_x, head_y)

            neck = (head_x, head_y + head_radius + 15)
            shoulder_width = max(1, person_width // 2)
            shoulder_left = (int(neck[0] - shoulder_width), neck[1] + 15)
            shoulder_right = (int(neck[0] + shoulder_width), neck[1] + 15)
            torso_center = (cx, int(y1 + person_height * 0.5))
            hip_width = max(1, person_width // 3)
            hip_left = (int(cx - hip_width), int(y1 + person_height * 0.55))
            hip_right = (int(cx + hip_width), int(y1 + person_height * 0.55))

            elbow_left = (
                int(shoulder_left[0] - person_width * 0.15),
                int(shoulder_left[1] + person_height * 0.22),
            )
            elbow_right = (
                int(shoulder_right[0] + person_width * 0.15),
                int(shoulder_right[1] + person_height * 0.22),
            )
            wrist_left = (
                int(elbow_left[0] - person_width * 0.1),
                int(elbow_left[1] + person_height * 0.18),
            )
            wrist_right = (
                int(elbow_right[0] + person_width * 0.1),
                int(elbow_right[1] + person_height * 0.18),
            )

            knee_left = (hip_left[0], int(y1 + person_height * 0.75))
            knee_right = (hip_right[0], int(y1 + person_height * 0.75))
            ankle_left = (knee_left[0], int(y2 - 25))
            ankle_right = (knee_right[0], int(y2 - 25))

            def draw_line(a: Tuple[int, int], b: Tuple[int, int]) -> None:
                if HAS_CV2 and cv2 is not None:
                    cv2.line(pose_map, a, b, color, thickness)
                else:
                    _draw_line_numpy(pose_map, a, b, color, thickness)

            def draw_circle(center: Tuple[int, int], r: int, fill: bool = True) -> None:
                if HAS_CV2 and cv2 is not None:
                    cv2.circle(pose_map, center, r, color, -1 if fill else 2)
                else:
                    _draw_circle_numpy(pose_map, center, r, color, fill=fill)

            draw_circle(head_pos_int, head_radius)
            draw_line(neck, torso_center)
            draw_line(shoulder_left, shoulder_right)
            draw_line(torso_center, hip_left)
            draw_line(torso_center, hip_right)
            draw_line(shoulder_left, elbow_left)
            draw_line(elbow_left, wrist_left)
            draw_line(shoulder_right, elbow_right)
            draw_line(elbow_right, wrist_right)
            draw_line(hip_left, knee_left)
            draw_line(knee_left, ankle_left)
            draw_line(hip_right, knee_right)
            draw_line(knee_right, ankle_right)

            joints = [
                neck,
                shoulder_left,
                shoulder_right,
                elbow_left,
                elbow_right,
                wrist_left,
                wrist_right,
                torso_center,
                hip_left,
                hip_right,
                knee_left,
                knee_right,
                ankle_left,
                ankle_right,
            ]
            for joint in joints:
                jx, jy = int(joint[0]), int(joint[1])
                if 0 <= jx < width and 0 <= jy < height:
                    draw_circle((jx, jy), 8)

        return pose_map

    def _create_canny_map(self, openpose_map: np.ndarray) -> np.ndarray:
        """Create Canny edge map from OpenPose skeleton. Returns (H, W, 3) uint8."""
        if openpose_map.ndim == 3:
            gray = np.dot(openpose_map[..., :3], [0.299, 0.587, 0.114]).astype(np.uint8)
        else:
            gray = openpose_map.astype(np.uint8)

        if HAS_CV2 and cv2 is not None:
            edges = cv2.Canny(gray, 50, 150)
            edges_rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
            return edges_rgb

        edges = np.where(gray > 50, 255, 0).astype(np.uint8)
        edges_rgb = np.stack([edges] * 3, axis=-1)
        return edges_rgb

    def visualize_controls(
        self,
        controls: Dict[str, Any],
        save_path: Optional[str] = None,
    ) -> Any:
        """
        Create side-by-side visualization of all control images.

        Useful for debugging and verification.
        """
        depth = (
            np.array(controls["depth"])
            if hasattr(controls["depth"], "__array__")
            else np.asarray(controls["depth"])
        )
        openpose = (
            np.array(controls["openpose"])
            if hasattr(controls["openpose"], "__array__")
            else np.asarray(controls["openpose"])
        )
        canny = (
            np.array(controls["canny"])
            if hasattr(controls["canny"], "__array__")
            else np.asarray(controls["canny"])
        )
        if depth.ndim == 2:
            depth = np.stack([depth] * 3, axis=-1)
        if openpose.ndim == 2:
            openpose = np.stack([openpose] * 3, axis=-1)
        if canny.ndim == 2:
            canny = np.stack([canny] * 3, axis=-1)

        combined = np.concatenate([depth, openpose, canny], axis=1)

        if HAS_PIL and Image is not None:
            combined_img = Image.fromarray(combined)
            if save_path:
                combined_img.save(save_path)
            return combined_img
        if save_path and HAS_CV2 and cv2 is not None:
            cv2.imwrite(save_path, cv2.cvtColor(combined, cv2.COLOR_RGB2BGR))
        return combined
