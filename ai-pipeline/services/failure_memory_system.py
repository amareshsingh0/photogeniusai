"""
Failure Memory & Smart Recovery.
Store failure patterns and auto-apply fixes for similar prompts.
P1: 70%+ common failures auto-fixed on first attempt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .pattern_matcher import PatternMatcher, PatternMatch
except ImportError:
    from ai_pipeline.services.pattern_matcher import PatternMatcher, PatternMatch  # type: ignore[reportMissingImports]


@dataclass
class FailureEntry:
    """Single stored failure pattern with fix."""

    pattern: str  # regex, e.g. "mother.*children.*umbrella.*rain"
    failure: str  # e.g. "heads_occluded"
    fix: Dict[
        str, Any
    ]  # e.g. {"camera_tilt": -10, "umbrella_height": +80, "person_spacing": +50}
    hits: int = 0  # times this fix was applied successfully
    misses: int = 0  # times applied but still failed


# Built-in common patterns for 70%+ auto-fix on first attempt.
# Each fix uses: camera_tilt, umbrella_height, person_spacing (layout),
# negative_prompt_append, positive_prompt_append (prompts).
DEFAULT_PATTERNS: List[Dict[str, Any]] = [
    # ----- Original: multi-person + umbrella + rain -----
    {
        "pattern": r"mother.*children.*umbrella.*rain",
        "failure": "heads_occluded",
        "fix": {"camera_tilt": -10, "umbrella_height": 80, "person_spacing": 50},
    },
    {
        "pattern": r"family.*umbrella.*rain",
        "failure": "heads_occluded",
        "fix": {"camera_tilt": -8, "umbrella_height": 70, "person_spacing": 45},
    },
    {
        "pattern": r"couple.*umbrella",
        "failure": "heads_occluded",
        "fix": {"camera_tilt": -5, "umbrella_height": 60, "person_spacing": 30},
    },
    {
        "pattern": r"\d+\s*(people|persons|adults|children).*rain",
        "failure": "heads_occluded",
        "fix": {"camera_tilt": -10, "person_spacing": 55},
    },
    {
        "pattern": r".*extra\s*(arm|limb|finger)",
        "failure": "limb_violation",
        "fix": {"negative_prompt_append": "extra limbs, deformed arms, six fingers"},
    },
    {
        "pattern": r".*merged\s*(body|figure|person)",
        "failure": "merged_bodies",
        "fix": {
            "person_spacing": 80,
            "positive_prompt_append": "clear separation between figures",
        },
    },
    {
        "pattern": r".*missing\s*head|head.*occluded",
        "failure": "heads_occluded",
        "fix": {"camera_tilt": -12, "umbrella_height": 90},
    },
    # ----- 1. Multi-person: groups, crowds, families -----
    {
        "pattern": r"group.*?(holding|with|carrying)\s+umbrellas?",
        "failure": "umbrella_occlusion",
        "fix": {
            "positive_prompt_append": "clear view of all faces, umbrellas held to the side",
            "negative_prompt_append": "umbrella blocking face, umbrella covering head",
            "camera_tilt": -6,
            "person_spacing": 40,
        },
    },
    {
        "pattern": r"(crowd|group)\s+of\s+\d+.*(people|persons)",
        "failure": "merged_bodies",
        "fix": {
            "person_spacing": 60,
            "positive_prompt_append": "clear separation between figures, distinct people",
            "negative_prompt_append": "merged bodies, conjoined, overlapping figures",
        },
    },
    {
        "pattern": r"family\s+(photo|portrait|picture).*\d+\s*(people|members)",
        "failure": "heads_occluded",
        "fix": {
            "camera_tilt": -8,
            "person_spacing": 50,
            "positive_prompt_append": "all faces visible, evenly spaced",
        },
    },
    {
        "pattern": r"(wedding|reunion).*?(guests|group|everyone)",
        "failure": "merged_bodies",
        "fix": {
            "person_spacing": 55,
            "positive_prompt_append": "clear separation between guests, layered composition",
            "negative_prompt_append": "merged figures, conjoined",
        },
    },
    {
        "pattern": r"(\d+)\s*(friends|people).*(sitting|standing)\s+together",
        "failure": "merged_bodies",
        "fix": {
            "person_spacing": 45,
            "positive_prompt_append": "distinct figures, natural spacing",
        },
    },
    # ----- 2. Weather: rain, snow, fog -----
    {
        "pattern": r"(heavy|pouring|torrential)\s+rain",
        "failure": "heads_occluded",
        "fix": {
            "camera_tilt": -10,
            "positive_prompt_append": "clear view of faces despite rain, rain visible but not blocking",
            "negative_prompt_append": "rain covering face, obscured by rain",
        },
    },
    {
        "pattern": r".*snow.*(falling|storm|blizzard)",
        "failure": "faces_partially_visible",
        "fix": {
            "positive_prompt_append": "faces clearly visible, snow in background",
            "negative_prompt_append": "snow covering face, obscured by snow",
        },
    },
    {
        "pattern": r"(fog|foggy|mist).*portrait|portrait.*(fog|mist)",
        "failure": "low_visibility",
        "fix": {
            "positive_prompt_append": "sharp face, soft fog in background",
            "negative_prompt_append": "blurry face, fog obscuring features",
        },
    },
    {
        "pattern": r"rainy\s+(day|street|scene).*people",
        "failure": "umbrella_occlusion",
        "fix": {
            "camera_tilt": -7,
            "person_spacing": 45,
            "positive_prompt_append": "umbrellas away from heads, clear faces",
        },
    },
    # ----- 3. Props and objects: umbrellas, bags, signs -----
    {
        "pattern": r"(holding|carrying|with)\s+(handbag|purse|bag)",
        "failure": "hand_anatomy",
        "fix": {
            "positive_prompt_append": "natural hand holding bag, correct grip",
            "negative_prompt_append": "deformed hand, wrong number of fingers, floating bag",
        },
    },
    {
        "pattern": r".*sign.*(holding|carrying|poster)",
        "failure": "text_legibility",
        "fix": {
            "positive_prompt_append": "readable sign, clear text, sign held upright",
            "negative_prompt_append": "blurry text, distorted letters, illegible",
        },
    },
    {
        "pattern": r"(person|woman|man).*holding\s+(phone|smartphone)",
        "failure": "hand_anatomy",
        "fix": {
            "positive_prompt_append": "natural grip on phone, correct fingers",
            "negative_prompt_append": "deformed hands, extra fingers, missing thumb",
        },
    },
    {
        "pattern": r"umbrella.*(beach|outdoor|park)",
        "failure": "umbrella_occlusion",
        "fix": {
            "camera_tilt": -5,
            "umbrella_height": 65,
            "positive_prompt_append": "umbrella not blocking face",
        },
    },
    {
        "pattern": r"(cup|mug|glass).*in\s+hand|hand.*(holding|gripping).*(cup|mug)",
        "failure": "hand_anatomy",
        "fix": {
            "positive_prompt_append": "natural hand holding cup, proper grip",
            "negative_prompt_append": "deformed hand, fused fingers, floating cup",
        },
    },
    # ----- 4. Anatomy: hands holding, faces partially visible -----
    {
        "pattern": r"hands?\s+(holding|gripping|holding\s+out)",
        "failure": "hand_anatomy",
        "fix": {
            "positive_prompt_append": "anatomically correct hands, five fingers, natural pose",
            "negative_prompt_append": "extra fingers, missing fingers, deformed hands, bad anatomy",
        },
    },
    {
        "pattern": r"(profile|side\s+view).*face|face.*(half|partial)\s+visible",
        "failure": "faces_partially_visible",
        "fix": {
            "positive_prompt_append": "clear facial features, visible profile",
            "negative_prompt_append": "blurry face, missing features, distorted profile",
        },
    },
    {
        "pattern": r"(backlit|silhouette).*person|person.*(backlit|silhouette)",
        "failure": "face_visibility",
        "fix": {
            "positive_prompt_append": "face visible with fill light, rim light on face",
            "negative_prompt_append": "completely dark face, no facial detail",
        },
    },
    {
        "pattern": r"close[- ]?up.*hands?|hands?\s+close[- ]?up",
        "failure": "hand_anatomy",
        "fix": {
            "positive_prompt_append": "detailed correct hands, five fingers each",
            "negative_prompt_append": "six fingers, four fingers, mutated hands",
        },
    },
    {
        "pattern": r"(two|2)\s+people.*hand|holding\s+hands",
        "failure": "hand_anatomy",
        "fix": {
            "positive_prompt_append": "natural hand-holding, correct hand connection",
            "negative_prompt_append": "merged hands, extra hands, wrong anatomy",
        },
    },
    # ----- 5. Lighting: backlit, shadows, night -----
    {
        "pattern": r"(backlit|back\s+light|sun\s+behind)",
        "failure": "face_underexposed",
        "fix": {
            "positive_prompt_append": "face well lit, rim light, fill light on face",
            "negative_prompt_append": "dark face, black face, no detail on face",
        },
    },
    {
        "pattern": r"(night|nighttime|nocturnal).*portrait|portrait.*at\s+night",
        "failure": "low_light",
        "fix": {
            "positive_prompt_append": "face clearly lit, soft key light, visible features",
            "negative_prompt_append": "pitch black face, no facial detail",
        },
    },
    {
        "pattern": r"heavy\s+shadow|face.*(shadow|shadows)",
        "failure": "face_underexposed",
        "fix": {
            "positive_prompt_append": "soft shadows, face visible, balanced lighting",
            "negative_prompt_append": "face in shadow, obscured by shadow",
        },
    },
    {
        "pattern": r"(sunset|sunrise).*person|person.*(sunset|sunrise)",
        "failure": "backlit_face",
        "fix": {
            "positive_prompt_append": "face lit from front, golden hour fill",
            "negative_prompt_append": "silhouette face, dark face",
        },
    },
    # ----- 6. Text/signage: store signs, posters, labels -----
    {
        "pattern": r"(store|shop)\s+sign|sign.*(store|shop)",
        "failure": "text_accuracy",
        "fix": {
            "positive_prompt_append": "legible sign, clear text, readable letters",
            "negative_prompt_append": "blurry text, garbled letters, wrong spelling",
        },
    },
    {
        "pattern": r"poster.*(wall|hanging)|(wall|billboard).*poster",
        "failure": "text_legibility",
        "fix": {
            "positive_prompt_append": "readable poster text, sharp typography",
            "negative_prompt_append": "illegible, distorted text, messy letters",
        },
    },
    {
        "pattern": r"(label|logo|brand).*on\s+(product|bottle|packaging)",
        "failure": "text_accuracy",
        "fix": {
            "positive_prompt_append": "clear label, readable text, proper proportions",
            "negative_prompt_append": "blurry label, wrong text, distorted logo",
        },
    },
    {
        "pattern": r"street.*sign|(road|street).*signage",
        "failure": "text_legibility",
        "fix": {
            "positive_prompt_append": "readable street sign, clear text",
            "negative_prompt_append": "illegible sign, garbled text",
        },
    },
    {
        "pattern": r"(menu|blackboard).*with\s+text|chalkboard.*writing",
        "failure": "text_accuracy",
        "fix": {
            "positive_prompt_append": "legible menu text, clear chalk writing",
            "negative_prompt_append": "unreadable, wrong characters, blurry text",
        },
    },
]


class FailureMemorySystem:
    """
    Store failure patterns and auto-apply fixes for similar prompts.
    Uses PatternMatcher to find best pattern; applies fix to camera/layout/prompt.
    """

    def __init__(
        self,
        max_entries: int = 2000,
        persist_path: Optional[Path] = None,
        initial_patterns: Optional[List[Dict[str, Any]]] = None,
    ):
        self.max_entries = max_entries
        self.persist_path = Path(persist_path) if persist_path else None
        self.matcher = PatternMatcher(case_sensitive=False)
        self.entries = []
        if self.persist_path and self.persist_path.exists():
            self._load_from_disk()
        if not self.entries:
            self._load_initial(initial_patterns or DEFAULT_PATTERNS)

    def _load_initial(self, patterns: List[Dict[str, Any]]) -> None:
        for p in patterns:
            self.entries.append(
                FailureEntry(
                    pattern=p.get("pattern", ""),
                    failure=p.get("failure", ""),
                    fix=p.get("fix", {}),
                )
            )

    def _load_from_disk(self) -> None:
        if self.persist_path is None:
            return
        try:
            text = self.persist_path.read_text(encoding="utf-8")
            data = json.loads(text)
            self.entries = [
                FailureEntry(
                    pattern=item.get("pattern", ""),
                    failure=item.get("failure", ""),
                    fix=item.get("fix", {}),
                    hits=item.get("hits", 0),
                    misses=item.get("misses", 0),
                )
                for item in data.get("entries", [])
            ]
        except Exception:
            self.entries = []

    def save(self) -> None:
        if not self.persist_path:
            return
        try:
            data = {
                "entries": [
                    {
                        "pattern": e.pattern,
                        "failure": e.failure,
                        "fix": e.fix,
                        "hits": e.hits,
                        "misses": e.misses,
                    }
                    for e in self.entries
                ]
            }
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self.persist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def record_failure(
        self,
        prompt: str,
        failure_type: str,
        failed_rules: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a failure; optionally derive a new pattern and fix from context.
        """
        # If we have a matching pattern, update its misses when fix was applied but failed
        pattern_list = [
            {"pattern": e.pattern, "failure": e.failure, "fix": e.fix}
            for e in self.entries
        ]
        match = self.matcher.best_match(prompt, pattern_list)
        if match:
            for e in self.entries:
                if e.pattern == match.pattern and e.failure == match.failure:
                    e.misses += 1
                    break

        # Optionally add new pattern from context (e.g. suggested fix from validator)
        fix_from_context = (context or {}).get("suggested_fix")
        if fix_from_context and isinstance(fix_from_context, dict):
            # Build simple regex from prompt keywords
            words = re.findall(r"\w+", prompt.lower())
            if len(words) >= 3:
                pattern = ".*".join(words[:5])  # first 5 words as pattern
                self.entries.append(
                    FailureEntry(
                        pattern=pattern,
                        failure=failure_type,
                        fix=fix_from_context,
                    )
                )
                if len(self.entries) > self.max_entries:
                    self.entries = self.entries[-self.max_entries :]
        self.save()

    def record_success(self, prompt: str, applied_fix: Dict[str, Any]) -> None:
        """Record that a fix was applied and validation passed (hits += 1)."""
        pattern_list = [
            {"pattern": e.pattern, "failure": e.failure, "fix": e.fix}
            for e in self.entries
        ]
        match = self.matcher.best_match(prompt, pattern_list)
        if match and match.fix == applied_fix:
            for e in self.entries:
                if (
                    e.pattern == match.pattern
                    and e.failure == match.failure
                    and e.fix == applied_fix
                ):
                    e.hits += 1
                    break
        self.save()

    def get_fix_for_prompt(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Return applicable fix for prompt (best matching pattern), or None.
        Enables 70%+ common failures auto-fixed on first attempt when patterns cover them.
        """
        pattern_list = [
            {"pattern": e.pattern, "failure": e.failure, "fix": e.fix}
            for e in self.entries
        ]
        match = self.matcher.best_match(prompt, pattern_list)
        if match and match.score >= 0.3:
            return dict(match.fix)
        return None

    def get_fix_and_match(self, prompt: str) -> Optional[tuple]:
        """Return (fix_dict, PatternMatch) for caller to inspect score/failure type."""
        pattern_list = [
            {"pattern": e.pattern, "failure": e.failure, "fix": e.fix}
            for e in self.entries
        ]
        match = self.matcher.best_match(prompt, pattern_list)
        if match and match.score >= 0.3:
            return (dict(match.fix), match)
        return None

    def apply_fix_to_layout(
        self,
        layout: Dict[str, Any],
        fix: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply fix (camera_tilt, umbrella_height, person_spacing) to layout/camera."""
        layout = dict(layout)
        entities = list(layout.get("entities", []))
        camera = dict(layout.get("camera") or {})

        tilt = fix.get("camera_tilt")
        if tilt is not None:
            camera["tilt"] = camera.get("tilt", 0) + tilt

        spacing = fix.get("person_spacing")
        if spacing is not None and entities:
            # Heuristic: shift person centers by spacing (spread out)
            for i, e in enumerate(entities):
                e = dict(e)
                if e.get("type") == "person" and (
                    "center" in e or "head_position" in e
                ):
                    head = e.get("head_position") or e.get("center") or (0, 0)
                    dx = (i - (len(entities) - 1) / 2) * (spacing or 0)
                    e["head_position"] = (head[0] + int(dx), head[1])
                    if "center" in e:
                        e["center"] = (head[0] + int(dx), head[1])
                    if "bbox" in e:
                        bbox = list(e["bbox"])
                        bbox[0] += int(dx)
                        bbox[2] += int(dx)
                        e["bbox"] = tuple(bbox)
                entities[i] = e
            layout["entities"] = entities

        umbrella_height = fix.get("umbrella_height")
        if umbrella_height is not None and entities:
            for i, e in enumerate(entities):
                e = dict(e)
                if e.get("type") == "umbrella" and "center" in e:
                    cx, cy = e["center"][0], e["center"][1]
                    e["center"] = (cx, cy - int(umbrella_height))
                    entities[i] = e
            layout["entities"] = entities

        layout["camera"] = camera
        return layout

    def apply_fix_to_prompt(
        self,
        prompt: str,
        negative_prompt: str,
        fix: Dict[str, Any],
    ) -> tuple:
        """Apply fix (positive/negative append) to prompts. Returns (new_prompt, new_negative)."""
        pos_append = fix.get("positive_prompt_append")
        neg_append = fix.get("negative_prompt_append")
        new_prompt = prompt + (", " + pos_append if pos_append else "")
        new_neg = negative_prompt + (", " + neg_append if neg_append else "")
        return new_prompt, new_neg
