"""
Creative Graph Builder — STAGE 1 of the Creative OS pipeline.

Builds a node-based layout graph for ad/poster compositions.
Each element (headline, product, CTA, logo zone, background) is a node
with spatial relationships, priority, and sizing constraints.

This replaces flat zone lists with a proper graph that understands:
- Hierarchy: headline > subhead > body > CTA
- Spatial rules: "headline above product", "CTA below everything"
- Reading flow: top→down or left→right depending on culture/platform
- Balance: visual weight distribution across quadrants

Heuristic-based. Boolean flag USE_LLM_GRAPH for future LLM-powered
graph generation (Llama/Qwen).
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Feature Flags
# ══════════════════════════════════════════════════════════════════════════════
USE_LLM_GRAPH = False           # Future: LLM generates the graph from prompt
USE_VISUAL_WEIGHT_MODEL = False # Future: predict visual weight per element


# ══════════════════════════════════════════════════════════════════════════════
# Types
# ══════════════════════════════════════════════════════════════════════════════

class GraphNode(TypedDict):
    """A single element in the creative graph."""
    id: str                      # unique node id ("headline", "product", "cta", ...)
    role: str                    # "text" | "image" | "decoration" | "background"
    priority: int                # 1=highest visual attention, 5=lowest
    # Bounding box as fractions of image (0.0-1.0)
    x: float
    y: float
    w: float
    h: float
    # Visual weight (0.0-1.0) — how much attention this element demands
    visual_weight: float
    # Relationship constraints
    above: Optional[str]         # must be above this node
    below: Optional[str]         # must be below this node
    align: str                   # "center" | "left" | "right"


class CreativeGraph(TypedDict):
    """Complete creative graph for a composition."""
    nodes: List[GraphNode]
    reading_flow: str            # "top_down" | "left_right" | "z_pattern" | "f_pattern"
    visual_balance: float        # 0.0=unbalanced, 1.0=perfectly balanced
    total_text_area: float       # fraction of image covered by text nodes
    dominant_quadrant: str       # "top_left" | "top_right" | "bottom_left" | "bottom_right" | "center"
    hierarchy_depth: int         # how many priority levels (1-5)


# ══════════════════════════════════════════════════════════════════════════════
# Layout Templates — pre-computed compositions for common ad types
# ══════════════════════════════════════════════════════════════════════════════

# Each template is a list of (id, role, priority, x, y, w, h, weight, above, below, align)
_TEMPLATES: Dict[str, List[tuple]] = {
    "poster_standard": [
        # Classic poster: headline top, subject center, CTA bottom
        ("headline",    "text",       1, 0.05, 0.03, 0.90, 0.15, 0.35, None,      "subject",  "center"),
        ("subject",     "image",      2, 0.10, 0.20, 0.80, 0.50, 0.40, "headline", "cta",     "center"),
        ("cta",         "text",       3, 0.15, 0.75, 0.70, 0.10, 0.20, "subject",  None,      "center"),
        ("background",  "background", 5, 0.00, 0.00, 1.00, 1.00, 0.05, None,       None,      "center"),
    ],
    "poster_bold": [
        # Bold poster: huge headline, small subject, strong CTA
        ("headline",    "text",       1, 0.05, 0.05, 0.90, 0.30, 0.50, None,       "subject",  "center"),
        ("subject",     "image",      2, 0.15, 0.38, 0.70, 0.35, 0.25, "headline", "cta",      "center"),
        ("cta",         "text",       3, 0.10, 0.78, 0.80, 0.12, 0.20, "subject",  None,       "center"),
        ("background",  "background", 5, 0.00, 0.00, 1.00, 1.00, 0.05, None,       None,       "center"),
    ],
    "banner_horizontal": [
        # Web banner: text left, image right
        ("headline",    "text",       1, 0.03, 0.10, 0.45, 0.35, 0.35, None,       "cta",      "left"),
        ("subtitle",    "text",       2, 0.03, 0.48, 0.45, 0.15, 0.10, "headline", "cta",      "left"),
        ("cta",         "text",       3, 0.03, 0.68, 0.30, 0.15, 0.20, "subtitle", None,       "left"),
        ("subject",     "image",      2, 0.50, 0.05, 0.48, 0.90, 0.30, None,       None,       "right"),
        ("background",  "background", 5, 0.00, 0.00, 1.00, 1.00, 0.05, None,       None,       "center"),
    ],
    "social_square": [
        # Instagram/social: subject dominant, small text overlay
        ("subject",     "image",      1, 0.00, 0.00, 1.00, 0.75, 0.50, None,       "headline", "center"),
        ("headline",    "text",       2, 0.05, 0.76, 0.90, 0.12, 0.30, "subject",  "cta",      "center"),
        ("cta",         "text",       3, 0.20, 0.90, 0.60, 0.08, 0.15, "headline", None,       "center"),
        ("background",  "background", 5, 0.00, 0.00, 1.00, 1.00, 0.05, None,       None,       "center"),
    ],
    "product_centered": [
        # E-commerce: product hero, minimal text
        ("product",     "image",      1, 0.15, 0.10, 0.70, 0.60, 0.55, None,       "headline", "center"),
        ("headline",    "text",       2, 0.10, 0.73, 0.80, 0.10, 0.25, "product",  "cta",      "center"),
        ("cta",         "text",       3, 0.25, 0.85, 0.50, 0.08, 0.15, "headline", None,       "center"),
        ("background",  "background", 5, 0.00, 0.00, 1.00, 1.00, 0.05, None,       None,       "center"),
    ],
    "editorial_split": [
        # Magazine: full bleed image + text strip
        ("subject",     "image",      1, 0.00, 0.00, 1.00, 0.65, 0.50, None,       "headline", "center"),
        ("headline",    "text",       1, 0.05, 0.67, 0.90, 0.15, 0.30, "subject",  "subtitle", "left"),
        ("subtitle",    "text",       3, 0.05, 0.83, 0.70, 0.08, 0.10, "headline", None,       "left"),
        ("background",  "background", 5, 0.00, 0.00, 1.00, 1.00, 0.05, None,       None,       "center"),
    ],
    "photo_only": [
        # Pure photography — no text zones
        ("subject",     "image",      1, 0.00, 0.00, 1.00, 1.00, 0.95, None,       None,       "center"),
        ("background",  "background", 5, 0.00, 0.00, 1.00, 1.00, 0.05, None,       None,       "center"),
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# Graph Builder
# ══════════════════════════════════════════════════════════════════════════════

class CreativeGraphBuilder:
    """
    Builds a node-based creative graph from intent + creative brief.

    The graph represents the ideal spatial layout of elements before
    any image generation happens. Downstream modules (layout_planner,
    text_overlay) read the graph to position elements precisely.
    """

    def build(
        self,
        creative_type: str,
        is_ad: bool,
        text_heavy: bool,
        has_text_overlay: bool,
        aspect_ratio: float = 1.0,
        cta_strength: float = 0.0,
        goal: str = "aesthetic",
    ) -> CreativeGraph:
        """
        Build creative graph from classified intent.

        Args:
            creative_type: From IntentAnalyzer ("poster", "ad", "photo", etc.)
            is_ad: Whether this is an advertisement
            text_heavy: Whether significant text is expected
            has_text_overlay: Whether text overlay was detected
            aspect_ratio: width/height ratio
            cta_strength: 0.0-1.0 CTA urgency
            goal: "conversion" | "awareness" | "engagement" | "aesthetic"

        Returns:
            CreativeGraph with positioned nodes
        """
        # ── Select template ─────────────────────────────────────────────
        template_name = self._select_template(
            creative_type, is_ad, text_heavy, has_text_overlay, aspect_ratio
        )

        # ── Build nodes from template ───────────────────────────────────
        raw_nodes = _TEMPLATES[template_name]
        nodes: List[GraphNode] = []
        for (nid, role, prio, x, y, w, h, weight, above, below, align) in raw_nodes:
            nodes.append(GraphNode(
                id=nid, role=role, priority=prio,
                x=x, y=y, w=w, h=h,
                visual_weight=weight,
                above=above, below=below, align=align,
            ))

        # ── Adjust CTA size based on strength ───────────────────────────
        if cta_strength > 0.6:
            for n in nodes:
                if n["id"] == "cta":
                    n["h"] = min(n["h"] * 1.3, 0.18)
                    n["visual_weight"] = min(n["visual_weight"] + 0.1, 0.5)

        # ── Adapt to aspect ratio ───────────────────────────────────────
        nodes = self._adapt_aspect(nodes, aspect_ratio)

        # ── Compute metrics ─────────────────────────────────────────────
        visual_balance = self._calc_balance(nodes)
        total_text_area = sum(
            n["w"] * n["h"] for n in nodes if n["role"] == "text"
        )
        dominant_quadrant = self._calc_dominant_quadrant(nodes)
        reading_flow = self._detect_reading_flow(nodes, aspect_ratio)
        hierarchy_depth = len(set(n["priority"] for n in nodes))

        graph = CreativeGraph(
            nodes=nodes,
            reading_flow=reading_flow,
            visual_balance=visual_balance,
            total_text_area=round(total_text_area, 4),
            dominant_quadrant=dominant_quadrant,
            hierarchy_depth=hierarchy_depth,
        )

        logger.info(
            "[GRAPH] template=%s nodes=%d balance=%.2f text_area=%.3f flow=%s",
            template_name, len(nodes), visual_balance, total_text_area, reading_flow,
        )

        return graph

    # ── Template selection ─────────────────────────────────────────────────

    def _select_template(
        self, ctype: str, is_ad: bool, text_heavy: bool,
        has_text: bool, aspect: float
    ) -> str:
        # Wide aspect → banner layout
        if aspect > 2.0:
            return "banner_horizontal"

        # Explicit type mapping
        type_map = {
            "poster": "poster_standard",
            "ad": "poster_bold",
            "banner": "banner_horizontal",
            "social": "social_square",
            "product_shot": "product_centered",
            "editorial": "editorial_split",
        }
        if ctype in type_map:
            return type_map[ctype]

        # Infer from flags
        if is_ad or text_heavy:
            return "poster_standard"
        if has_text:
            return "social_square"

        return "photo_only"

    # ── Aspect ratio adaptation ────────────────────────────────────────────

    def _adapt_aspect(self, nodes: List[GraphNode], aspect: float) -> List[GraphNode]:
        """Adjust node positions for non-square aspect ratios."""
        if 0.85 <= aspect <= 1.15:
            return nodes  # close enough to square

        if aspect > 1.5:
            # Landscape: compress vertical, expand horizontal
            for n in nodes:
                if n["role"] == "text":
                    # Shift text to left side for landscape
                    n["w"] = min(n["w"] * 0.7, 0.50)
        elif aspect < 0.7:
            # Portrait/story: stack elements more vertically
            text_nodes = [n for n in nodes if n["role"] == "text"]
            for i, n in enumerate(text_nodes):
                # Spread text nodes vertically
                n["h"] = min(n["h"] * 1.2, 0.20)

        return nodes

    # ── Balance calculation ────────────────────────────────────────────────

    def _calc_balance(self, nodes: List[GraphNode]) -> float:
        """
        Calculate visual balance score (0.0-1.0).

        Uses quadrant weight distribution: perfect balance = equal weight
        in all 4 quadrants. Score = 1.0 - normalized_deviation.
        """
        quadrant_weights = {"tl": 0.0, "tr": 0.0, "bl": 0.0, "br": 0.0}

        for n in nodes:
            if n["role"] == "background":
                continue
            cx = n["x"] + n["w"] / 2
            cy = n["y"] + n["h"] / 2
            w = n["visual_weight"]

            # Distribute weight to quadrants based on center position
            # Soft assignment: proportional to distance from center
            left_frac = max(0, 1.0 - cx * 2)
            right_frac = max(0, cx * 2 - 1.0)
            top_frac = max(0, 1.0 - cy * 2)
            bottom_frac = max(0, cy * 2 - 1.0)

            # Bilinear interpolation into 4 quadrants
            quadrant_weights["tl"] += w * (1.0 - cx) * (1.0 - cy)
            quadrant_weights["tr"] += w * cx * (1.0 - cy)
            quadrant_weights["bl"] += w * (1.0 - cx) * cy
            quadrant_weights["br"] += w * cx * cy

        total = sum(quadrant_weights.values())
        if total == 0:
            return 1.0

        # Normalize
        values = [v / total for v in quadrant_weights.values()]
        ideal = 0.25  # perfect balance = 25% per quadrant

        # Mean absolute deviation from ideal
        deviation = sum(abs(v - ideal) for v in values) / 4
        # max possible deviation = 0.375 (all weight in one quadrant)
        return round(max(0.0, 1.0 - deviation / 0.375), 3)

    def _calc_dominant_quadrant(self, nodes: List[GraphNode]) -> str:
        """Find which quadrant has the most visual weight."""
        qw = {"top_left": 0.0, "top_right": 0.0, "bottom_left": 0.0, "bottom_right": 0.0}

        for n in nodes:
            if n["role"] == "background":
                continue
            cx = n["x"] + n["w"] / 2
            cy = n["y"] + n["h"] / 2
            w = n["visual_weight"]

            if cx < 0.5 and cy < 0.5:
                qw["top_left"] += w
            elif cx >= 0.5 and cy < 0.5:
                qw["top_right"] += w
            elif cx < 0.5:
                qw["bottom_left"] += w
            else:
                qw["bottom_right"] += w

        # Check if weight is roughly centered
        total = sum(qw.values())
        if total == 0:
            return "center"

        top = (qw["top_left"] + qw["top_right"]) / total
        bottom = (qw["bottom_left"] + qw["bottom_right"]) / total
        left = (qw["top_left"] + qw["bottom_left"]) / total
        right = (qw["top_right"] + qw["bottom_right"]) / total

        if abs(top - bottom) < 0.15 and abs(left - right) < 0.15:
            return "center"

        return max(qw, key=qw.get)

    def _detect_reading_flow(self, nodes: List[GraphNode], aspect: float) -> str:
        """Detect the natural reading flow of the composition."""
        text_nodes = sorted(
            [n for n in nodes if n["role"] == "text"],
            key=lambda n: n["priority"]
        )
        if len(text_nodes) < 2:
            return "top_down"

        # Check if text flows left→right or top→down
        first, second = text_nodes[0], text_nodes[1]
        dy = abs(second["y"] - first["y"])
        dx = abs(second["x"] - first["x"])

        if aspect > 2.0 and dx > dy:
            return "left_right"

        # Check for Z-pattern (top-left → top-right → bottom-left → bottom-right)
        if len(text_nodes) >= 3:
            positions = [(n["x"] + n["w"]/2, n["y"] + n["h"]/2) for n in text_nodes]
            if (positions[0][1] < 0.4 and positions[-1][1] > 0.6):
                return "z_pattern"

        return "top_down"


# Singleton
creative_graph = CreativeGraphBuilder()
