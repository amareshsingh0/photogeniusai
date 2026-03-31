"""
Scene Graph Compiler for PhotoGenius AI.
Converts prompts into constraint graphs that MUST be satisfied.
P0: Deterministic, self-evolving image generation — Task 1.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# Optional: use networkx for graph; fallback to dict-based graph
try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False
    nx = None

# Optional: use spacy for NLP; fallback to regex-only extraction
try:
    import spacy

    _nlp = None

    def _get_nlp():
        global _nlp
        if _nlp is None:
            try:
                _nlp = spacy.load("en_core_web_sm")
            except OSError:
                _nlp = spacy.load("en_core_web_trf")
        return _nlp

    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    _get_nlp = None


# Object types that can occlude heads/faces; layout logic keeps them away from heads
OCCLUDER_TYPES = frozenset({
    "umbrella", "hat", "balloon", "sign", "bag", "handbag", "purse",
    "poster", "book", "phone", "lamp_shade",
})


@dataclass
class EntityNode:
    """Single entity in the scene (person, object, weather, lighting, creature, etc.)."""

    id: str
    type: str  # 'person', 'object', 'weather', 'lighting', 'creature', 'furniture', etc.
    properties: Dict[str, Any]
    count: int = 1
    bounding_box: Optional[Tuple[float, float, float, float]] = None
    z_order: int = 0  # Layering for occlusion
    required_attributes: List[str] = field(default_factory=list)  # e.g. ["visible_face", "hands_visible"]


@dataclass
class RelationEdge:
    """Relationship between two entities."""

    source: str
    target: str
    relation: str  # 'covers', 'holds', 'under', 'beside'
    constraints: List[str]


@dataclass
class HardConstraint:
    """Non-negotiable constraint that validator MUST pass."""

    type: str  # 'visibility', 'anatomy', 'physics', 'count', 'spatial'
    rule: str
    severity: str  # 'critical', 'high', 'medium'
    validator: Optional[Callable[..., bool]] = (
        None  # Optional; implemented in Tri-Model Validation (Task 4)
    )


class SceneGraphCompiler:
    """
    Transforms natural language into an executable constraint graph
    that FORCES correctness (exact counts, visibility, anatomy, physics).
    """

    def __init__(self, use_spacy: bool = True):
        self.use_spacy = use_spacy and HAS_SPACY
        self.nlp = _get_nlp() if self.use_spacy else None
        self.graph = nx.DiGraph() if HAS_NX else None
        self.constraints: List[HardConstraint] = []

    def compile(self, prompt: str) -> Dict[str, Any]:
        """
        Compile prompt into executable scene graph with hard constraints.

        Returns:
            {
                'graph': NetworkX graph (or dict) with entities and relations,
                'constraints': List of HardConstraints that MUST pass,
                'layout': Spatial layout plan (occlusion-safe),
                'camera': Camera configuration,
                'quality_requirements': Non-negotiable quality rules,
                'entities': List[EntityNode],
                'relations': List[RelationEdge],
            }
        """
        doc = self._parse(prompt)

        # Step 1: Extract entities with exact counts
        entities = self._extract_entities_precise(doc, prompt)

        # Step 2: Build relationship graph
        relations = self._extract_relations(doc, entities, prompt)

        # Step 3: Generate hard constraints (including inference from prompt)
        constraints = self._generate_hard_constraints(entities, relations, prompt)

        # Step 4: Compute spatial layout with occlusion solver
        layout = self._compute_layout_with_occlusion(entities, relations)

        # Step 5: Plan camera to ensure all constraints met
        camera = self._plan_camera(layout, constraints)

        # Step 6: Build graph
        graph = self._build_graph(entities, relations)

        # Serializable view of constraints for API (hard_constraints)
        hard_constraints = [
            {"type": c.type, "rule": c.rule, "severity": c.severity}
            for c in constraints
        ]
        return {
            "graph": graph,
            "entities": entities,
            "relations": relations,
            "constraints": constraints,
            "hard_constraints": hard_constraints,
            "layout": layout,
            "camera": camera,
            "quality_requirements": self._generate_quality_reqs(entities, constraints),
            "prompt": prompt,
        }

    def _parse(self, prompt: str):
        """Return doc-like object (spacy Doc or simple wrapper)."""
        if self.use_spacy and self.nlp is not None:
            return self.nlp(prompt)

        # Simple wrapper with .text for regex-only path
        class SimpleDoc:
            def __init__(self, text: str):
                self.text = text

        return SimpleDoc(prompt)

    def _extract_entities_precise(self, doc, prompt: str) -> List[EntityNode]:
        """
        Extract entities with EXACT counts using multiple strategies.

        Handles:
        - "3 children" → 3 child entities
        - "mother with 3 kids" → 1 adult + 3 children = 4 total
        - "couple" → 2 adults
        - "family of 5" → 5 people
        - "dragon" → 1 mythical creature
        - "flying city" → 1 imaginative structure
        """
        entities: List[EntityNode] = []
        text = prompt.lower()
        entity_id = [0]  # use list to allow mutation in nested loops
        consumed_spans: List[Tuple[int, int]] = (
            []
        )  # (start, end) already used by relational

        def next_id():
            entity_id[0] += 1
            return entity_id[0] - 1

        def is_consumed(match: re.Match) -> bool:
            s, e = match.start(), match.end()
            return any(cs <= s and e <= ce for cs, ce in consumed_spans)

        # Strategy 2: Relational patterns first (so consumed_spans block number pattern double-count)
        relational_patterns = [
            (
                r"(mother and father|father and mother)\s+with\s+(\d+)\s+(kids|children)",
                "two_parents_with_kids",
            ),
            (
                r"(man and woman|woman and man)\s+with\s+baby",
                "couple_with_baby",
            ),
            (
                r"(mother|father|woman|man)\s+with\s+baby\s+and\s+toddler",
                "adult_baby_toddler",
            ),
            (
                r"(mother|father|parent|adult)\s+with\s+(\d+)\s+(children|kids)",
                "parent_child",
            ),
            (
                r"(man|woman|mother|father)\s+and\s+(\d+)\s+(children|kids|daughters|sons|boys|girls|daughter|son)",
                "parent_child",
            ),
            (
                r"(father|mother)\s+and\s+(daughter|son)\b",
                "parent_one_child",
            ),
            (
                r"(adult|person)\s+and\s+(toddler|child|baby)\b",
                "adult_and_one",
            ),
            (
                r"(woman|man|mother|father)\s+with\s+(\d+)\s+babies",
                "adult_with_babies",
            ),
        ]
        for pattern, rel_type in relational_patterns:
            for match in re.finditer(pattern, text):
                if is_consumed(match):
                    continue
                consumed_spans.append((match.start(), match.end()))
                if rel_type == "adult_and_one":
                    # "adult and toddler" → 2
                    consumed_spans.append((match.start(), match.end()))
                    for _ in range(2):
                        eid = next_id()
                        entities.append(
                            EntityNode(
                                id=f"person_{eid}",
                                type="person",
                                properties={"role": "person", "age": "adult"},
                                count=1,
                            )
                        )
                    entities[-1].properties["age"] = "child"
                    entities[-1].properties["role"] = match.group(2)
                    continue
                if rel_type == "parent_one_child":
                    # "father and daughter" → 2
                    pid = next_id()
                    entities.append(
                        EntityNode(
                            id=f"person_{pid}",
                            type="person",
                            properties={"role": match.group(1), "age": "adult"},
                            count=1,
                        )
                    )
                    cid = next_id()
                    entities.append(
                        EntityNode(
                            id=f"person_{cid}",
                            type="person",
                            properties={
                                "role": "child",
                                "age": "child",
                                "parent_id": f"person_{pid}",
                            },
                            count=1,
                        )
                    )
                    continue
                if rel_type == "two_parents_with_kids":
                    consumed_spans.append((match.start(), match.end()))
                    kid_count = int(match.group(2))
                    for _ in range(2 + kid_count):
                        eid = next_id()
                        entities.append(
                            EntityNode(
                                id=f"person_{eid}",
                                type="person",
                                properties={"role": "person", "age": "adult"},
                                count=1,
                            )
                        )
                    for i in range(kid_count):
                        entities[-1 - i].properties["age"] = "child"
                        entities[-1 - i].properties["role"] = "child"
                    continue
                if rel_type == "couple_with_baby":
                    # "man and woman with baby" → 3
                    consumed_spans.append((match.start(), match.end()))
                    for _ in range(3):
                        eid = next_id()
                        entities.append(
                            EntityNode(
                                id=f"person_{eid}",
                                type="person",
                                properties={
                                    "role": "person" if _ < 2 else "baby",
                                    "age": "adult" if _ < 2 else "child",
                                },
                                count=1,
                            )
                        )
                    continue
                if rel_type == "adult_baby_toddler":
                    # "mother with baby and toddler" → 3
                    consumed_spans.append((match.start(), match.end()))
                    for idx in range(3):
                        eid = next_id()
                        entities.append(
                            EntityNode(
                                id=f"person_{eid}",
                                type="person",
                                properties={
                                    "role": ["person", "baby", "toddler"][idx],
                                    "age": "adult" if idx == 0 else "child",
                                },
                                count=1,
                            )
                        )
                    continue
                if rel_type == "adult_with_babies":
                    # "woman with 2 babies" → 1 + N
                    baby_count = int(match.group(2))
                    for _ in range(1 + baby_count):
                        eid = next_id()
                        entities.append(
                            EntityNode(
                                id=f"person_{eid}",
                                type="person",
                                properties={"role": "person", "age": "adult"},
                                count=1,
                            )
                        )
                    for i in range(baby_count):
                        entities[-1 - i].properties["age"] = "child"
                        entities[-1 - i].properties["role"] = "baby"
                    continue
                parent_role = match.group(1)
                child_count = int(match.group(2))
                pid = next_id()
                entities.append(
                    EntityNode(
                        id=f"person_{pid}",
                        type="person",
                        properties={"role": parent_role, "age": "adult"},
                        count=1,
                    )
                )
                for i in range(child_count):
                    cid = next_id()
                    entities.append(
                        EntityNode(
                            id=f"person_{cid}",
                            type="person",
                            properties={
                                "role": "child",
                                "age": "child",
                                "parent_id": f"person_{pid}",
                            },
                            count=1,
                        )
                    )

        # Strategy 2b: Adult with (a) baby → 2 people
        baby_patterns = [
            r"(woman|man|mother|father)\s+with\s+(a\s+)?baby",
            r"(mother|father)\s+and\s+baby",
        ]
        for pattern in baby_patterns:
            match = re.search(pattern, text)
            if match and not any(e.properties.get("role") == "baby" for e in entities):
                person_count_before = sum(1 for e in entities if e.type == "person")
                consumed_spans.append((match.start(), match.end()))
                # If already 2+ persons (e.g. "man and woman with baby"), add 1 baby only
                if person_count_before >= 2:
                    eid = next_id()
                    entities.append(
                        EntityNode(
                            id=f"person_{eid}",
                            type="person",
                            properties={"role": "baby", "age": "child"},
                            count=1,
                        )
                    )
                else:
                    # Add adult + baby (2 people)
                    for _ in range(2):
                        eid = next_id()
                        role = "adult" if _ == 0 else "baby"
                        age = "adult" if _ == 0 else "child"
                        entities.append(
                            EntityNode(
                                id=f"person_{eid}",
                                type="person",
                                properties={"role": role, "age": age},
                                count=1,
                            )
                        )
                break

        # Strategy 1: Explicit number patterns (skip if inside a relational span)
        number_patterns = [
            (
                r"(\d+)\s+(children|kids|people|adults|men|women|boys|girls|toddlers|babies|child|baby)",
                "person",
            ),
            (
                r"(\d+)\s+(dogs|cats|birds|dragons|unicorns|animals)",
                "creature",
            ),
            (
                r"(\d+)\s+(cars|buildings|umbrellas|trees|flowers)",
                "object",
            ),
        ]
        for pattern, entity_type in number_patterns:
            for match in re.finditer(pattern, text):
                if is_consumed(match):
                    continue
                count = int(match.group(1))
                role = match.group(2)
                for i in range(count):
                    eid = next_id()
                    entities.append(
                        EntityNode(
                            id=f"{entity_type}_{eid}",
                            type=entity_type,
                            properties={
                                "role": role,
                                "age": self._infer_age(role),
                                "instance": i + 1,
                                "total_of_type": count,
                            },
                            count=1,
                        )
                    )

        # Strategy 2c: Word numbers (one, two, three, four, five, ...)
        word_numbers = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }
        word_number_pattern = re.compile(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+"
            r"(people|persons|men|women|adults|children|kids|boys|girls|couples)\b",
            re.I,
        )
        for match in word_number_pattern.finditer(text):
            if is_consumed(match):
                continue
            num_word = match.group(1).lower()
            role_word = match.group(2).lower()
            count = word_numbers.get(num_word, 1)
            if role_word == "couples":
                count = count * 2  # "two couples" = 4 people
            for i in range(count):
                eid = next_id()
                entities.append(
                    EntityNode(
                        id=f"person_{eid}",
                        type="person",
                        properties={
                            "role": (
                                role_word.rstrip("s")
                                if role_word.endswith("s")
                                else role_word
                            ),
                            "age": (
                                "child"
                                if role_word in ("children", "kids", "boys", "girls")
                                else "adult"
                            ),
                        },
                        count=1,
                    )
                )
            consumed_spans.append((match.start(), match.end()))

        # Strategy 3: Implicit counts (couple, pair, trio) - only when no persons yet
        implicit_counts = {
            "couple": 2,
            "pair": 2,
            "duo": 2,
            "trio": 3,
            "group": 4,
            "crowd": 8,
            "family of 3": 3,
            "family of 4": 4,
            "family of 5": 5,
            "family of 6": 6,
            "family of 7": 7,
            "mother and father": 2,
            "father and mother": 2,
            "man and woman": 2,
            "woman and man": 2,
        }
        person_count_so_far = sum(1 for e in entities if e.type == "person")
        for phrase, count in implicit_counts.items():
            if phrase in text:
                if any(
                    e.properties.get("role") == f"{phrase}_member" for e in entities
                ):
                    continue
                # Don't add crowd/group if we already have explicit count (e.g. "10 people in crowd")
                if phrase in ("crowd", "group") and person_count_so_far > 0:
                    continue
                # Don't add "couple" if "two couples" / "one couple" etc. already matched (word_number)
                if phrase == "couple" and re.search(
                    r"\b(one|two|three|four|five)\s+couples?\b", text, re.I
                ):
                    continue
                # Don't add "mother and father" when "with N kids" (handled by two_parents_with_kids)
                if phrase in ("mother and father", "father and mother") and re.search(
                    r"with\s+\d+\s+(kids|children)", text
                ):
                    continue
                # Don't add "man and woman" when "with baby" (handled by couple_with_baby)
                if phrase in ("man and woman", "woman and man") and "with baby" in text:
                    continue
                for i in range(count):
                    eid = next_id()
                    entities.append(
                        EntityNode(
                            id=f"person_{eid}",
                            type="person",
                            properties={
                                "role": f"{phrase}_member",
                                "age": "adult",
                            },
                            count=1,
                        )
                    )

        # Strategy 4: Single-person / generic person (no number)
        if not any(e.type == "person" for e in entities):
            person_markers = [
                "person",
                "man",
                "woman",
                "child",
                "boy",
                "girl",
                "mother",
                "father",
                "adult",
                "kid",
                "baby",
                "people",
                "figure",
                "someone",
            ]
            if any(m in text for m in person_markers):
                eid = next_id()
                entities.append(
                    EntityNode(
                        id=f"person_{eid}",
                        type="person",
                        properties={"role": "person", "age": "adult"},
                        count=1,
                    )
                )

        # Strategy 5: Objects and environmental elements
        objects = self._detect_objects(doc, text, next_id)
        entities.extend(objects)

        # Strategy 6: Weather and atmospheric elements (rain, snow, clouds, fog)
        weather_entities = self._detect_weather(doc, text, next_id)
        entities.extend(weather_entities)

        # Strategy 6b: Lighting sources (sun, lamps, windows)
        lighting_entities = self._detect_lighting_sources(doc, text, next_id)
        entities.extend(lighting_entities)

        # Strategy 7: Imaginative/fantasy elements
        fantasy = self._detect_fantasy_elements(doc, text, next_id)
        entities.extend(fantasy)

        return entities

    def _detect_fantasy_elements(
        self, doc, text: str, next_id: Callable[[], int]
    ) -> List[EntityNode]:
        """Detect imaginative elements for 'madness' category."""
        fantasy_keywords = {
            "dragon": {
                "type": "mythical_creature",
                "properties": {"wings": True, "breathes_fire": True},
            },
            "unicorn": {
                "type": "mythical_creature",
                "properties": {"horn": True, "magical": True},
            },
            "flying city": {
                "type": "imaginative_structure",
                "properties": {"defies_gravity": True},
            },
            "portal": {
                "type": "magical_object",
                "properties": {"interdimensional": True},
            },
            "crystal": {
                "type": "magical_material",
                "properties": {"glowing": True, "translucent": True},
            },
        }
        entities = []
        for keyword, spec in fantasy_keywords.items():
            if keyword in text:
                entities.append(
                    EntityNode(
                        id=f"fantasy_{keyword.replace(' ', '_')}_{next_id()}",
                        type=spec["type"],
                        properties=spec["properties"],
                        count=1,
                    )
                )
        return entities

    def _generate_hard_constraints(
        self,
        entities: List[EntityNode],
        relations: List[RelationEdge],
        prompt: str = "",
    ) -> List[HardConstraint]:
        """
        Generate NON-NEGOTIABLE constraints that validator MUST pass.
        Infers from prompt: exactly_N_people (family of N), hands_holding_book_correctly (reading book),
        centered_subject + clean_background (product photo).
        Categories: visibility, anatomy, physics, count, spatial.
        """
        constraints: List[HardConstraint] = []
        text = (prompt or "").lower()
        person_count = sum(1 for e in entities if e.type == "person")

        # Inferred from prompt: "family of N" → exactly_N_people
        family_of_match = re.search(r"family\s+of\s+(\d+)", text)
        if family_of_match:
            n = int(family_of_match.group(1))
            constraints.append(
                HardConstraint(
                    type="count",
                    rule=f"exactly_{n}_people",
                    severity="critical",
                    validator=None,
                )
            )

        # Inferred: "reading book" → hands_holding_book_correctly
        if "reading" in text and "book" in text:
            constraints.append(
                HardConstraint(
                    type="anatomy",
                    rule="hands_holding_book_correctly",
                    severity="high",
                    validator=None,
                )
            )

        # Inferred: "product photo" → centered_subject, clean_background
        if "product photo" in text or "product shot" in text or "product photography" in text:
            constraints.append(
                HardConstraint(
                    type="spatial",
                    rule="centered_subject",
                    severity="critical",
                    validator=None,
                )
            )
            constraints.append(
                HardConstraint(
                    type="visibility",
                    rule="clean_background",
                    severity="high",
                    validator=None,
                )
            )

        if person_count > 0:
            constraints.append(
                HardConstraint(
                    type="visibility",
                    rule=f"exactly_{person_count}_heads_fully_visible",
                    severity="critical",
                    validator=None,
                )
            )
            constraints.append(
                HardConstraint(
                    type="visibility",
                    rule="no_heads_occluded_by_objects",
                    severity="critical",
                    validator=None,
                )
            )
            constraints.append(
                HardConstraint(
                    type="anatomy",
                    rule="each_person_has_2_arms_2_legs",
                    severity="critical",
                    validator=None,
                )
            )
            constraints.append(
                HardConstraint(
                    type="anatomy",
                    rule="hands_have_5_fingers_each",
                    severity="high",
                    validator=None,
                )
            )
            if person_count > 1:
                constraints.append(
                    HardConstraint(
                        type="spatial",
                        rule="no_merged_bodies",
                        severity="critical",
                        validator=None,
                    )
                )

        has_rain = any(
            e.type == "weather" and e.properties.get("condition") == "rain"
            for e in entities
        )
        if has_rain:
            constraints.append(
                HardConstraint(
                    type="physics",
                    rule="realistic_wetness_effects",
                    severity="high",
                    validator=None,
                )
            )

        return constraints

    def _compute_layout_with_occlusion(
        self,
        entities: List[EntityNode],
        relations: List[RelationEdge],
    ) -> Dict[str, Any]:
        """
        Compute spatial layout ensuring NO occlusion of critical parts.
        Uses constraint satisfaction: heads visible, umbrella above head.
        """
        layout: Dict[str, Any] = {"entities": [], "camera": None}
        width, height = 1024, 1024

        people = [e for e in entities if e.type == "person"]
        objects = [e for e in entities if e.type == "object"]

        if people:
            person_count = len(people)
            avg_person_width = width // (person_count + 1)
            safety_margin = 50

            for i, person in enumerate(people):
                x_center = avg_person_width * (i + 1)
                is_child = person.properties.get("age") == "child"
                person_height = int(height * (0.4 if is_child else 0.65))
                person_width = int(person_height * 0.35)
                y_bottom = int(height * 0.90)
                y_top = y_bottom - person_height
                head_y = y_top

                layout["entities"].append(
                    {
                        "id": person.id,
                        "type": "person",
                        "age": person.properties.get("age", "adult"),
                        "bbox": (
                            x_center - person_width // 2,
                            y_top,
                            x_center + person_width // 2,
                            y_bottom,
                        ),
                        "head_position": (x_center, head_y),
                        "head_radius": int(person_height * 0.12),
                        "z_order": i,
                    }
                )

        people_in_layout = [p for p in layout["entities"] if p.get("type") == "person"]
        for obj_entity in objects:
            name = obj_entity.properties.get("name")
            # Umbrella: place above ALL heads (zero occlusion)
            if name == "umbrella" and people_in_layout:
                min_head_y = min(p["head_position"][1] for p in people_in_layout)
                max_head_r = max(p["head_radius"] for p in people_in_layout)
                umbrella_y = min_head_y - max_head_r - 80
                holder = next(
                    (
                        p
                        for p in layout["entities"]
                        if p.get("type") == "person" and p.get("age") == "adult"
                    ),
                    layout["entities"][0] if layout["entities"] else None,
                )
                if holder:
                    umbrella_x = holder["head_position"][0]
                    layout["entities"].append(
                        {
                            "id": obj_entity.id,
                            "type": "umbrella",
                            "center": (umbrella_x, umbrella_y),
                            "radius": 150,
                            "z_order": -1,
                        }
                    )
            # Hat: place above head of first person (or above all heads if shared)
            elif name == "hat" and people_in_layout:
                min_head_y = min(p["head_position"][1] for p in people_in_layout)
                hat_y = min_head_y - 60
                hat_x = people_in_layout[0]["head_position"][0]
                layout["entities"].append(
                    {
                        "id": obj_entity.id,
                        "type": "hat",
                        "center": (hat_x, hat_y),
                        "radius": 45,
                        "z_order": -1,
                    }
                )
            # Prop (balloon, sign): above and slightly aside so no head occlusion
            elif obj_entity.properties.get("category") == "prop" and people_in_layout:
                min_head_y = min(p["head_position"][1] for p in people_in_layout)
                prop_y = min_head_y - 100
                cx = sum(p["head_position"][0] for p in people_in_layout) / len(
                    people_in_layout
                )
                layout["entities"].append(
                    {
                        "id": obj_entity.id,
                        "type": "prop",
                        "center": (cx, prop_y),
                        "radius": 50,
                        "z_order": -1,
                    }
                )
            # Furniture: place below head band so heads are in front
            elif obj_entity.properties.get("category") == "furniture":
                width, height = 1024, 1024
                # Default: chair/table at bottom third
                fy0 = int(height * 0.55)
                fy1 = int(height * 0.92)
                fx0 = int(width * 0.3)
                fx1 = int(width * 0.7)
                layout["entities"].append(
                    {
                        "id": obj_entity.id,
                        "type": "furniture",
                        "bbox": (fx0, fy0, fx1, fy1),
                        "z_order": 1,
                    }
                )
            # Other objects (car, tree, etc.): bbox in safe zone
            elif name in ("car", "building", "tree", "flower"):
                width, height = 1024, 1024
                layout["entities"].append(
                    {
                        "id": obj_entity.id,
                        "type": "object",
                        "bbox": (
                            int(width * 0.1),
                            int(height * 0.5),
                            int(width * 0.4),
                            int(height * 0.9),
                        ),
                        "z_order": 0,
                    }
                )

        return layout

    def _compute_fov_for_entities(
        self,
        n_people: int,
        n_objects: int,
        base_fov: float = 50.0,
        per_entity_fov: float = 6.0,
        fov_min: float = 45.0,
        fov_max: float = 90.0,
        fov_scale_mode: str = "linear",
    ) -> float:
        """
        FOV calculation based on entity count so all entities fit in frame.
        fov_scale_mode: "linear" (default), "sqrt", or "log" — sqrt/log avoid maxing FOV in crowds.
        """
        n = n_people + n_objects
        if n <= 0:
            return base_fov
        if fov_scale_mode == "sqrt":
            mult = math.sqrt(max(0, n - 1))
        elif fov_scale_mode == "log":
            mult = math.log1p(max(0, n - 1))
        else:
            mult = float(n - 1)
        fov = base_fov + per_entity_fov * mult
        return max(fov_min, min(fov_max, fov))

    def _plan_camera(
        self,
        layout: Dict[str, Any],
        constraints: List[HardConstraint],
    ) -> Dict[str, Any]:
        """
        Plan camera position/angle to satisfy visibility constraints.
        - FOV from entity count (wider for more people/objects).
        - Height/tilt for full visibility: height from head centers, tilt down for groups.
        """
        all_entities = layout.get("entities", [])
        if not all_entities:
            return {
                "fov": 50.0,
                "height": 1.6,
                "tilt": 0.0,
                "distance": 2.5,
                "frame": {"min_x": 0, "max_x": 1024, "min_y": 0, "max_y": 1024},
            }

        def get_min_x(e):
            if "bbox" in e:
                return e["bbox"][0]
            return e.get("center", (0, 0))[0] - e.get("radius", 0)

        def get_max_x(e):
            if "bbox" in e:
                return e["bbox"][2]
            return e.get("center", (0, 0))[0] + e.get("radius", 0)

        def get_min_y(e):
            if "bbox" in e:
                return e["bbox"][1]
            return e.get("center", (0, 0))[1] - e.get("radius", 0)

        def get_max_y(e):
            if "bbox" in e:
                return e["bbox"][3]
            return e.get("center", (0, 0))[1] + e.get("radius", 0)

        people = [e for e in all_entities if e.get("type") == "person"]
        objects = [e for e in all_entities if e.get("type") != "person"]
        n_people = len(people)
        n_objects = len(objects)

        # FOV based on entity count (sqrt mode for crowds to avoid maxing FOV)
        fov_scale_mode = "sqrt" if (n_people + n_objects) > 6 else "linear"
        fov = self._compute_fov_for_entities(
            n_people, n_objects, fov_scale_mode=fov_scale_mode
        )

        min_x = min(get_min_x(e) for e in all_entities)
        max_x = max(get_max_x(e) for e in all_entities)
        min_y = min(get_min_y(e) for e in all_entities)
        max_y = max(get_max_y(e) for e in all_entities)

        # Height: eye-level from head centers (tunable factor 0.35)
        height_eye_factor = 0.35
        if people:
            head_ys = [
                e.get("head_position", (0, 0))[1]
                for e in people
                if "head_position" in e
            ]
            if head_ys:
                camera_height_y = (
                    min(head_ys) + (max(head_ys) - min(head_ys)) * height_eye_factor
                )
            else:
                camera_height_y = min_y + (max_y - min_y) * 0.4
        else:
            camera_height_y = min_y + (max_y - min_y) * 0.4
        # Normalize to 0–2 scale for "height" (used as hint)
        height = 1.2 + (camera_height_y / 1024.0) * 0.8

        # Tilt: look down for multiple people (tunable: 2° per extra person, cap 10°)
        tilt_per_extra_person = 2.0
        tilt_cap_degrees = 10.0
        tilt = 0.0
        if n_people > 1:
            tilt = -5.0 - min(tilt_cap_degrees, (n_people - 1) * tilt_per_extra_person)
        elif n_people == 1 and objects:
            tilt = -3.0

        return {
            "fov": fov,
            "height": height,
            "tilt": tilt,
            "distance": 2.5,
            "frame": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
        }

    def _infer_age(self, role: str) -> str:
        child_keywords = [
            "child",
            "children",
            "kid",
            "kids",
            "baby",
            "toddler",
            "boy",
            "girl",
            "boys",
            "girls",
        ]
        return "child" if any(k in role.lower() for k in child_keywords) else "adult"

    def _detect_objects(
        self, doc, text: str, next_id: Callable[[], int]
    ) -> List[EntityNode]:
        # Furniture, props, vehicles, nature; props/furniture used for relations and occlusion
        object_keywords = {
            # Furniture
            "chair": {"category": "furniture", "name": "chair"},
            "chairs": {"category": "furniture", "name": "chair"},
            "table": {"category": "furniture", "name": "table"},
            "tables": {"category": "furniture", "name": "table"},
            "sofa": {"category": "furniture", "name": "sofa"},
            "sofas": {"category": "furniture", "name": "sofa"},
            "couch": {"category": "furniture", "name": "couch"},
            "desk": {"category": "furniture", "name": "desk"},
            "bed": {"category": "furniture", "name": "bed"},
            # Props (OCCLUDER_TYPES)
            "umbrella": {"category": "accessory", "name": "umbrella"},
            "umbrellas": {"category": "accessory", "name": "umbrella"},
            "hat": {"category": "accessory", "name": "hat"},
            "balloon": {"category": "prop", "name": "balloon"},
            "balloons": {"category": "prop", "name": "balloon"},
            "sign": {"category": "prop", "name": "sign"},
            "signs": {"category": "prop", "name": "sign"},
            "bag": {"category": "prop", "name": "bag"},
            "bags": {"category": "prop", "name": "bag"},
            "handbag": {"category": "prop", "name": "handbag"},
            "purse": {"category": "prop", "name": "purse"},
            "book": {"category": "prop", "name": "book"},
            "books": {"category": "prop", "name": "book"},
            "phone": {"category": "prop", "name": "phone"},
            "smartphone": {"category": "prop", "name": "phone"},
            "poster": {"category": "prop", "name": "poster"},
            # Other
            "car": {"category": "vehicle", "name": "car"},
            "building": {"category": "structure", "name": "building"},
            "tree": {"category": "nature", "name": "tree"},
            "flower": {"category": "nature", "name": "flower"},
            "lamp": {"category": "furniture", "name": "lamp"},
        }
        entities = []
        seen_names = set()
        for keyword, props in object_keywords.items():
            if keyword in text and props.get("name") not in seen_names:
                seen_names.add(props.get("name"))
                color_match = re.search(rf"(\w+)\s+{re.escape(keyword)}", text)
                p = dict(props)
                if color_match:
                    p["color"] = color_match.group(1)
                entities.append(
                    EntityNode(
                        id=f"object_{p['name']}_{next_id()}",
                        type="object",
                        properties=p,
                        count=1,
                    )
                )
        return entities

    def _detect_weather(
        self, doc, text: str, next_id: Callable[[], int]
    ) -> List[EntityNode]:
        """Detect weather/atmosphere: rain, snow, clouds, fog, sunny, night."""
        weather_map = [
            ("rain", {"condition": "rain", "wetness": True, "visibility": 0.7}),
            ("rainy", {"condition": "rain", "wetness": True, "visibility": 0.7}),
            ("raining", {"condition": "rain", "wetness": True, "visibility": 0.7}),
            ("snow", {"condition": "snow", "cold": True, "visibility": 0.6}),
            ("snowfall", {"condition": "snow", "cold": True, "visibility": 0.6}),
            ("snowing", {"condition": "snow", "cold": True, "visibility": 0.6}),
            ("clouds", {"condition": "cloudy", "overcast": True, "visibility": 0.8}),
            ("cloudy", {"condition": "cloudy", "overcast": True, "visibility": 0.8}),
            ("fog", {"condition": "fog", "visibility": 0.4}),
            ("foggy", {"condition": "fog", "visibility": 0.4}),
            ("mist", {"condition": "fog", "visibility": 0.5}),
            ("sunny", {"condition": "sunny", "bright": True, "shadows": True}),
            ("night", {"condition": "night", "dark": True, "artificial_lighting": True}),
        ]
        entities: List[EntityNode] = []
        seen_conditions: set = set()
        for keyword, props in weather_map:
            if keyword in text and props["condition"] not in seen_conditions:
                seen_conditions.add(props["condition"])
                eid = next_id()
                entities.append(
                    EntityNode(
                        id=f"weather_{props['condition']}_{eid}",
                        type="weather",
                        properties=dict(props),
                        count=1,
                    )
                )
        return entities

    def _detect_lighting_sources(
        self, doc, text: str, next_id: Callable[[], int]
    ) -> List[EntityNode]:
        """Detect lighting sources: sun, lamp(s), window(s), light."""
        lighting_keywords = [
            ("sun", {"source": "sun", "natural": True, "direction": "above"}),
            ("sunlight", {"source": "sun", "natural": True}),
            ("lamp", {"source": "lamp", "natural": False, "indoor": True}),
            ("lamps", {"source": "lamp", "natural": False, "indoor": True}),
            ("window", {"source": "window", "natural": True, "indoor": True}),
            ("windows", {"source": "window", "natural": True, "indoor": True}),
            ("ceiling light", {"source": "ceiling_light", "natural": False}),
            ("desk lamp", {"source": "desk_lamp", "natural": False}),
        ]
        entities: List[EntityNode] = []
        seen_sources: set = set()
        for keyword, props in lighting_keywords:
            if keyword in text and props["source"] not in seen_sources:
                seen_sources.add(props["source"])
                eid = next_id()
                entities.append(
                    EntityNode(
                        id=f"lighting_{props['source']}_{eid}",
                        type="lighting",
                        properties=dict(props),
                        count=1,
                    )
                )
        return entities

    def _extract_relations(
        self,
        doc,
        entities: List[EntityNode],
        prompt: str = "",
    ) -> List[RelationEdge]:
        """Extract spatial and interaction relationships: holding, sitting_on, under/sheltered_by, illuminated_by."""
        relations: List[RelationEdge] = []
        text = (prompt or getattr(doc, "text", "") or "").lower()
        people = [e for e in entities if e.type == "person"]
        objects = [e for e in entities if e.type == "object"]
        furniture = [e for e in objects if e.properties.get("category") == "furniture"]
        lighting = [e for e in entities if e.type == "lighting"]
        weather = [e for e in entities if e.type == "weather"]

        # Holding: person-object (umbrella, sign, bag, book, phone)
        holdable = {"umbrella", "hat", "sign", "balloon", "bag", "handbag", "purse", "book", "phone"}
        for person in people:
            for obj in objects:
                name = obj.properties.get("name")
                if name not in holdable:
                    continue
                # Prompt suggests holding: "holding X", "with X", "carrying X", "reading book", "on phone"
                if any(
                    phrase in text
                    for phrase in (
                        "holding " + name,
                        "with " + name,
                        "carrying " + name,
                        " " + name + " in hand",
                        name + " in hand",
                    )
                ) or (name == "book" and "reading" in text) or (name == "phone" and ("phone" in text or "smartphone" in text)):
                    relations.append(
                        RelationEdge(
                            source=person.id,
                            target=obj.id,
                            relation="holding",
                            constraints=["hand_touches_object", "object_not_occluding_face"],
                        )
                    )
                    if name == "umbrella":
                        relations[-1].constraints = ["hand_touches_handle", "umbrella_above_head"]
                    elif name == "book":
                        relations[-1].constraints = ["hands_holding_book_correctly", "book_visible"]
                    break  # one holding relation per person for this object type

        # Umbrella-specific: under / sheltered_by when rain present
        umbrella_entity = next(
            (e for e in objects if e.properties.get("name") == "umbrella"),
            None,
        )
        has_rain = any(
            w.properties.get("condition") == "rain" for w in weather
        )
        if umbrella_entity and people:
            if not any(r.source == people[0].id and r.target == umbrella_entity.id and r.relation == "holding" for r in relations):
                relations.append(
                    RelationEdge(
                        source=people[0].id,
                        target=umbrella_entity.id,
                        relation="holding",
                        constraints=["hand_touches_handle", "umbrella_above_head"],
                    )
                )
            for person in people:
                rel_type = "sheltered_by" if has_rain else "under"
                constraints = ["head_not_occluded", "protected_from_rain"] if has_rain else ["head_not_occluded"]
                relations.append(
                    RelationEdge(
                        source=person.id,
                        target=umbrella_entity.id,
                        relation=rel_type,
                        constraints=constraints,
                    )
                )

        # Sitting/standing on: person-furniture (chair, sofa, desk)
        sit_stand_phrases = ("sitting on", "sits on", "seated on", "on the chair", "on a chair",
                             "on the sofa", "on a sofa", "on the couch", "on a couch",
                             "on the desk", "at the desk", "by the desk")
        for person in people:
            for furn in furniture:
                fname = furn.properties.get("name", "")
                if fname in ("chair", "sofa", "couch", "desk") and (
                    f"on the {fname}" in text or f"on a {fname}" in text
                    or f"sitting on {fname}" in text or f"seated on {fname}" in text
                    or (fname == "desk" and "at the desk" in text)
                ):
                    relations.append(
                        RelationEdge(
                            source=person.id,
                            target=furn.id,
                            relation="sitting_on" if fname in ("chair", "sofa", "couch") else "at",
                            constraints=["person_supported_by_furniture", "furniture_visible"],
                        )
                    )
                    break

        # Illuminated by: person or object — lighting source
        if lighting and (people or objects):
            for light in lighting:
                for entity in people + objects:
                    relations.append(
                        RelationEdge(
                            source=entity.id,
                            target=light.id,
                            relation="illuminated_by",
                            constraints=["lit_appropriately", "no_harsh_shadows_on_face"],
                        )
                    )

        return relations

    def _build_graph(
        self,
        entities: List[EntityNode],
        relations: List[RelationEdge],
    ) -> Any:
        """Build graph for visualization and reasoning (NetworkX or dict)."""
        if HAS_NX and nx is not None:
            G = nx.DiGraph()
            for entity in entities:
                G.add_node(
                    entity.id,
                    **entity.properties,
                    type=entity.type,
                )
            for relation in relations:
                G.add_edge(
                    relation.source,
                    relation.target,
                    relation=relation.relation,
                    constraints=relation.constraints,
                )
            return G
        # Fallback: dict-based graph
        nodes = {e.id: {"type": e.type, **e.properties} for e in entities}
        edges = [
            {
                "source": r.source,
                "target": r.target,
                "relation": r.relation,
                "constraints": r.constraints,
            }
            for r in relations
        ]
        return {"nodes": nodes, "edges": edges}

    def _generate_quality_reqs(
        self,
        entities: List[EntityNode],
        constraints: List[HardConstraint],
    ) -> Dict[str, Any]:
        """Generate quality requirements from constraints."""
        person_count = sum(1 for e in entities if e.type == "person")
        return {
            "person_count_exact": person_count,
            "all_heads_visible": True,
            "all_faces_clear": True,
            "correct_limb_count": True,
            "no_merged_bodies": person_count > 1,
            "no_extra_limbs": True,
            "proper_hand_anatomy": True,
            "proper_foot_anatomy": True,
            "realistic_proportions": True,
            "constraint_count": len(constraints),
            "critical_constraints": len(
                [c for c in constraints if c.severity == "critical"]
            ),
        }
