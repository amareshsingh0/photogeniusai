"""
Tests for Scene Graph Compiler.
Task 1 deliverables: 100% accuracy on person counting, zero head occlusions.

Run from ai-pipeline root:
  python -m pytest tests/test_scene_graph_compiler.py -v -p no:asyncio
"""

import pytest

try:
    from services.scene_graph_compiler import (
        SceneGraphCompiler,
        OCCLUDER_TYPES,
        EntityNode,
        RelationEdge,
    )
except ImportError:
    from ai_pipeline.services.scene_graph_compiler import (
        SceneGraphCompiler,
        OCCLUDER_TYPES,
        EntityNode,
        RelationEdge,
    )


def test_exact_person_counting():
    """Test precise person counting across all patterns."""
    compiler = SceneGraphCompiler(use_spacy=False)

    test_cases = [
        ("Mother with 3 children", 4),
        ("Couple walking in park", 2),
        ("Family of 5 at beach", 5),
        ("3 kids playing soccer", 3),
        ("Father and 2 daughters", 3),
        ("Group of friends", 4),  # 'group' implies 4
        ("Woman with baby", 2),
    ]

    for prompt, expected_count in test_cases:
        result = compiler.compile(prompt)
        entities = result["entities"]
        actual_count = sum(1 for e in entities if e.type == "person")
        assert (
            actual_count == expected_count
        ), f"Prompt: '{prompt}' - Expected: {expected_count}, Got: {actual_count}"


def test_occlusion_prevention():
    """Test that layout prevents head occlusion."""
    compiler = SceneGraphCompiler(use_spacy=False)

    result = compiler.compile("Mother with 3 children under umbrella in rain")
    layout = result["layout"]

    umbrella = next((e for e in layout["entities"] if e["type"] == "umbrella"), None)
    people = [e for e in layout["entities"] if e["type"] == "person"]

    assert umbrella is not None, "Umbrella should be in layout"
    assert len(people) == 4, "Should have 4 people"

    umbrella_y = umbrella["center"][1]
    for person in people:
        head_y = person["head_position"][1]
        assert (
            umbrella_y < head_y - 50
        ), f"Umbrella ({umbrella_y}) should be well above head ({head_y})"


def test_constraint_generation():
    """Test that correct constraints are generated."""
    compiler = SceneGraphCompiler(use_spacy=False)

    result = compiler.compile("3 people walking in rain")
    constraints = result["constraints"]

    visibility_constraints = [c for c in constraints if c.type == "visibility"]
    assert len(visibility_constraints) >= 2, "Should have visibility constraints"

    anatomy_constraints = [c for c in constraints if c.type == "anatomy"]
    assert len(anatomy_constraints) >= 2, "Should have anatomy constraints"

    physics_constraints = [c for c in constraints if c.type == "physics"]
    assert len(physics_constraints) >= 1, "Should have rain physics constraint"


def test_fantasy_element_detection():
    """Test imaginative/fantasy element parsing."""
    compiler = SceneGraphCompiler(use_spacy=False)

    result = compiler.compile("Dragon flying over a magical crystal city")
    entities = result["entities"]

    dragon = next((e for e in entities if "dragon" in e.id), None)
    assert dragon is not None, "Should detect dragon"
    assert dragon.type == "mythical_creature", "Dragon should be mythical_creature"

    crystal = next((e for e in entities if "crystal" in e.id), None)
    assert crystal is not None, "Should detect crystal"


def test_camera_planning():
    """Test camera automatically adjusts for group size."""
    compiler = SceneGraphCompiler(use_spacy=False)

    result_small = compiler.compile("Couple at sunset")
    camera_small = result_small["camera"]

    result_large = compiler.compile("Family of 5 at picnic")
    camera_large = result_large["camera"]

    assert (
        camera_large["fov"] > camera_small["fov"]
    ), "Larger group should have wider field of view"


# Success Metric: 100% accuracy on 50+ test prompts with person counting
PERSON_COUNT_PROMPTS = [
    ("Mother with 3 children", 4),
    ("Couple walking in park", 2),
    ("Family of 5 at beach", 5),
    ("3 kids playing soccer", 3),
    ("Father and 2 daughters", 3),
    ("Group of friends", 4),
    ("Woman with baby", 2),
    ("2 people at cafe", 2),
    ("Four adults at meeting", 4),
    ("1 woman portrait", 1),
    ("Family of 4 at picnic", 4),
    ("Mother and father with 2 kids", 4),
    ("Trio of musicians", 3),
    ("Crowd at concert", 8),
    ("Pair of dancers", 2),
    ("5 men in suits", 5),
    ("Two women in garden", 2),
    ("6 children at school", 6),
    ("Man with baby", 2),
    ("Duo performing", 2),
    ("Family of 6 on vacation", 6),
    ("3 adults and 2 children", 5),
    ("Single person walking", 1),
    ("7 people in line", 7),
    ("Father and 3 sons", 4),
    ("Mother and 1 daughter", 2),
    ("8 people at party", 8),
    ("Couple with 1 child", 3),
    ("9 men playing football", 9),
    ("Woman and 2 boys", 3),
    ("10 people in crowd", 10),
    ("2 boys and 2 girls", 4),
    ("Parent with 4 children", 5),
    ("Adult and toddler", 2),
    ("4 women at brunch", 4),
    ("Man and woman with baby", 3),
    ("5 children in playground", 5),
    ("Two couples", 4),
    ("6 people hiking", 6),
    ("Mother with baby and toddler", 3),
    ("7 adults in office", 7),
    ("Family of 3", 3),
    ("8 kids at camp", 8),
    ("Father and daughter", 2),
    ("9 people at wedding", 9),
    ("Three men", 3),
    ("10 children in class", 10),
    ("Woman with 2 babies", 3),
    ("2 men and 2 women", 4),
    ("Group at table", 4),
    ("One person standing", 1),
    ("4 boys playing", 4),
    ("Couple at sunset", 2),
    ("5 girls in dress", 5),
    ("Family of 7", 7),
]


@pytest.mark.parametrize("prompt,expected_count", PERSON_COUNT_PROMPTS)
def test_person_counting_50_plus_prompts(prompt, expected_count):
    """Success metric: 100% accuracy on 50+ test prompts with person counting."""
    compiler = SceneGraphCompiler(use_spacy=False)
    result = compiler.compile(prompt)
    entities = result["entities"]
    actual_count = sum(1 for e in entities if e.type == "person")
    assert (
        actual_count == expected_count
    ), f"Prompt: '{prompt}' - Expected: {expected_count}, Got: {actual_count}"


def test_zero_head_occlusion_umbrella_above_all():
    """Success metric: Zero head occlusions in generated layouts (umbrella above all heads)."""
    compiler = SceneGraphCompiler(use_spacy=False)
    prompts_with_umbrella = [
        "Mother with 3 children under umbrella in rain",
        "2 people with umbrella walking",
        "Family of 5 with one umbrella in rain",
    ]
    for prompt in prompts_with_umbrella:
        result = compiler.compile(prompt)
        layout = result["layout"]
        umbrella = next(
            (e for e in layout["entities"] if e["type"] == "umbrella"), None
        )
        people = [e for e in layout["entities"] if e["type"] == "person"]
        if not people:
            continue
        assert umbrella is not None, f"Layout should have umbrella for: {prompt}"
        umbrella_y = umbrella["center"][1]
        for person in people:
            head_y = person["head_position"][1]
            assert (
                umbrella_y < head_y - 50
            ), f"Prompt: {prompt} - Umbrella ({umbrella_y}) must be above head ({head_y})"


# ----- Task 3.1: Complex prompts and enriched output -----


def test_complex_family_umbrellas_rain():
    """Complex prompt: family of 5 with umbrellas in rain — entities, relations, hard_constraints."""
    compiler = SceneGraphCompiler(use_spacy=False)
    prompt = "family of 5 with umbrellas in rain"
    result = compiler.compile(prompt)

    entities = result["entities"]
    person_count = sum(1 for e in entities if e.type == "person")
    assert person_count == 5, f"Expected 5 people, got {person_count}"

    umbrella = next(
        (e for e in entities if e.type == "object" and e.properties.get("name") == "umbrella"),
        None,
    )
    assert umbrella is not None, "Should detect umbrella"

    weather = [e for e in entities if e.type == "weather"]
    assert any(e.properties.get("condition") == "rain" for e in weather), "Should detect rain"

    relations = result["relations"]
    under_or_sheltered = [r for r in relations if r.relation in ("under", "sheltered_by")]
    assert len(under_or_sheltered) >= 1, "Should have under/sheltered_by when rain + umbrella"

    hard = result.get("hard_constraints") or []
    rules = [h["rule"] for h in hard]
    assert "exactly_5_people" in rules, "Family of 5 should add exactly_5_people constraint"


def test_complex_woman_chair_book_lamp():
    """Complex prompt: woman sitting on chair reading book by lamp — furniture, holding, illuminated_by."""
    compiler = SceneGraphCompiler(use_spacy=False)
    prompt = "woman sitting on chair reading book by lamp"
    result = compiler.compile(prompt)

    entities = result["entities"]
    people = [e for e in entities if e.type == "person"]
    assert len(people) >= 1, "Should have at least one person"

    furniture = [e for e in entities if e.type == "object" and e.properties.get("category") == "furniture"]
    chair = next((e for e in furniture if e.properties.get("name") == "chair"), None)
    assert chair is not None, "Should detect chair"

    book = next(
        (e for e in entities if e.type == "object" and e.properties.get("name") == "book"),
        None,
    )
    assert book is not None, "Should detect book"

    lighting = [e for e in entities if e.type == "lighting"]
    assert len(lighting) >= 1, "Should detect lamp as lighting"

    relations = result["relations"]
    sitting_on = [r for r in relations if r.relation == "sitting_on"]
    assert len(sitting_on) >= 1, "Should have sitting_on (person-chair)"

    holding = [r for r in relations if r.relation == "holding"]
    book_holding = [r for r in holding if r.target == book.id]
    assert len(book_holding) >= 1, "Should have holding (person-book) for reading book"

    illuminated = [r for r in relations if r.relation == "illuminated_by"]
    assert len(illuminated) >= 1, "Should have illuminated_by when lamp present"

    constraints = result["constraints"]
    rules = [c.rule for c in constraints]
    assert "hands_holding_book_correctly" in rules, "Reading book should add hands_holding_book_correctly"


def test_complex_product_photo_smartphone_desk():
    """Complex prompt: product photo of smartphone on desk — centered_subject, clean_background."""
    compiler = SceneGraphCompiler(use_spacy=False)
    prompt = "product photo of smartphone on desk"
    result = compiler.compile(prompt)

    entities = result["entities"]
    objects = [e for e in entities if e.type == "object"]
    phone = next((e for e in objects if e.properties.get("name") == "phone"), None)
    desk = next((e for e in objects if e.properties.get("category") == "furniture" and e.properties.get("name") == "desk"), None)
    assert phone is not None, "Should detect smartphone/phone"
    assert desk is not None, "Should detect desk"

    hard = result.get("hard_constraints") or []
    rules = [h["rule"] for h in hard]
    assert "centered_subject" in rules, "Product photo should add centered_subject"
    assert "clean_background" in rules, "Product photo should add clean_background"


def test_output_has_hard_constraints_and_relations():
    """Output includes entities, relations, hard_constraints (validation rules)."""
    compiler = SceneGraphCompiler(use_spacy=False)
    result = compiler.compile("family of 4 at the beach")

    assert "entities" in result
    assert "relations" in result
    assert "hard_constraints" in result
    assert isinstance(result["entities"], list)
    assert isinstance(result["relations"], list)
    assert isinstance(result["hard_constraints"], list)
    for h in result["hard_constraints"]:
        assert "type" in h and "rule" in h and "severity" in h


def test_occluder_types_include_props():
    """OCCLUDER_TYPES includes umbrella, balloon, sign, bag for layout/occlusion."""
    assert "umbrella" in OCCLUDER_TYPES
    assert "balloon" in OCCLUDER_TYPES
    assert "sign" in OCCLUDER_TYPES
    assert "bag" in OCCLUDER_TYPES


def test_weather_and_lighting_detection():
    """Weather (rain, snow, clouds) and lighting (sun, lamp, window) detected."""
    compiler = SceneGraphCompiler(use_spacy=False)

    r1 = compiler.compile("portrait in rain with snow and clouds")
    weather_types = {e.properties.get("condition") for e in r1["entities"] if e.type == "weather"}
    assert "rain" in weather_types or "snow" in weather_types or "cloudy" in weather_types

    r2 = compiler.compile("woman reading by lamp near window")
    lighting = [e for e in r2["entities"] if e.type == "lighting"]
    assert len(lighting) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
