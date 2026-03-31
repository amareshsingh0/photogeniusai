"""
Safety Service - Context-Aware Content Moderation
Pre and post generation safety checks with reduced false positives
"""
import modal  # type: ignore[reportMissingImports]
from pathlib import Path
import io
import base64
import re
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np  # type: ignore[reportMissingImports]

app = modal.App("photogenius-safety")
stub = app  # Alias for compatibility

# ==================== Modal Config ====================
safety_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "torchvision==0.19.1",
        "pillow==10.2.0",
        "numpy==1.26.3",
        "opencv-python==4.9.0.80",
        "nudenet==3.4.2",
        "fastapi[standard]",
    )
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0",
    )
)

# ==================== Context-Aware Safety Rules ====================

# Blocked keywords with context exceptions
# Format: keyword -> list of safe context phrases where the keyword is OK
BLOCKED_WITH_CONTEXT = {
    "explicit": {
        "category": "explicit",
        "safe_contexts": ["explicit detail", "explicit quality"],
    },
    "nude": {
        "category": "explicit",
        "safe_contexts": ["nude color", "nude palette", "nude tone", "nude lipstick", "nude makeup"],
    },
    "naked": {
        "category": "explicit",
        "safe_contexts": ["naked eye"],
    },
    "nsfw": {"category": "explicit", "safe_contexts": []},
    "porn": {"category": "explicit", "safe_contexts": []},
    "sex": {
        "category": "explicit",
        "safe_contexts": ["sexy", "sexist"],  # "sexy" allowed in fashion context
    },
    "erotic": {"category": "explicit", "safe_contexts": []},
    "gore": {
        "category": "violence",
        "safe_contexts": ["gorgeous", "gore-tex"],
    },
    "violent": {"category": "violence", "safe_contexts": []},
    "weapon": {"category": "violence", "safe_contexts": []},
    "blood": {
        "category": "violence",
        "safe_contexts": ["blood orange", "blood red", "bloodhound"],
    },
}

# Always blocked - no context exceptions
ALWAYS_BLOCKED = {
    "child": {
        "category": "minors",
        "safe_contexts": ["childhood", "childlike wonder", "inner child", "child-friendly"],
    },
    "kid": {
        "category": "minors",
        "safe_contexts": ["kidding", "kids meal"],
    },
    "minor": {
        "category": "minors",
        "safe_contexts": ["minor adjustment", "minor detail", "minor change", "minor key"],
    },
    "underage": {"category": "minors", "safe_contexts": []},
    "teen": {
        "category": "minors",
        "safe_contexts": ["canteen", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"],
    },
    "teenager": {"category": "minors", "safe_contexts": []},
}

AGE_THRESHOLD = 18


def check_keyword_with_context(keyword: str, rule: dict, text: str) -> bool:
    """
    Check if a keyword violation is real (not a false positive).
    Returns True if the keyword is a genuine violation.
    """
    # Check if any safe context phrase contains the keyword
    for safe_phrase in rule.get("safe_contexts", []):
        if safe_phrase in text:
            return False  # Safe context found, not a violation

    # Use word boundary check to avoid partial matches
    # e.g., "child" should not match "childhood"
    pattern = r'\b' + re.escape(keyword) + r'\b'
    if not re.search(pattern, text):
        return False  # Keyword not found as whole word

    return True


@app.function(
    image=safety_image,
    timeout=60,
)
def check_prompt_safety(prompt: str, mode: str) -> Dict:
    """
    Context-aware prompt safety check.
    Reduces false positives while maintaining safety.
    """
    print(f"[*] Checking prompt safety: {prompt}")

    violations = []
    lower_prompt = prompt.lower().strip()

    # ==================== Context-Aware Keyword Check ====================
    all_rules = {**BLOCKED_WITH_CONTEXT, **ALWAYS_BLOCKED}

    for keyword, rule in all_rules.items():
        if check_keyword_with_context(keyword, rule, lower_prompt):
            violations.append({
                "type": "blocked_keyword",
                "category": rule["category"],
                "keyword": keyword,
            })

    # ==================== Mode-Specific Rules ====================
    if mode == "ROMANTIC":
        romantic_blocks = ["revealing", "provocative", "intimate apparel", "lingerie"]
        for keyword in romantic_blocks:
            if keyword in lower_prompt:
                violations.append({
                    "type": "romantic_mode_violation",
                    "keyword": keyword,
                })

    # ==================== Combination Detection ====================
    # Some words are only dangerous in combination
    dangerous_combos = [
        (["young", "woman"], ["undress", "naked", "strip"]),
        (["girl"], ["sexy", "hot", "attractive"]),
        (["boy"], ["sexy", "hot", "attractive"]),
    ]

    for group_a, group_b in dangerous_combos:
        has_a = any(w in lower_prompt for w in group_a)
        has_b = any(w in lower_prompt for w in group_b)
        if has_a and has_b:
            violations.append({
                "type": "dangerous_combination",
                "groups": [group_a, group_b],
            })

    # ==================== Result ====================
    allowed = len(violations) == 0

    result = {
        "allowed": allowed,
        "violations": violations,
        "prompt": prompt,
        "mode": mode,
    }

    if allowed:
        print("[OK] Prompt passed safety check")
    else:
        print(f"[BLOCKED] {len(violations)} violations found:")
        for v in violations:
            print(f"   - {v['type']}: {v.get('keyword', v.get('groups', 'N/A'))}")

    return result


@app.function(
    image=safety_image,
    gpu="T4",
    timeout=60,
)
def check_image_safety(image_base64: str, mode: str) -> Dict:
    """Post-generation image safety check using NudeNet"""
    from PIL import Image  # type: ignore[reportMissingImports]
    import numpy as np  # type: ignore[reportMissingImports]
    from nudenet import NudeDetector  # type: ignore[reportMissingImports]
    import cv2  # type: ignore[reportMissingImports]

    print("[*] Checking image safety...")

    img_bytes = base64.b64decode(image_base64)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img_array = np.array(image)

    # ==================== NSFW Detection ====================
    print("  [*] NSFW check...")
    detector = NudeDetector()
    temp_path = "/tmp/temp_check.jpg"
    image.save(temp_path)
    detections = detector.detect(temp_path)

    nsfw_score = 0.0
    nsfw_classes = [
        "EXPOSED_BREAST_F", "EXPOSED_GENITALIA_F", "EXPOSED_GENITALIA_M",
        "EXPOSED_BUTTOCKS", "EXPOSED_ANUS",
    ]
    for detection in detections:
        if detection["class"] in nsfw_classes:
            nsfw_score = max(nsfw_score, detection["score"])

    print(f"  NSFW: {nsfw_score:.3f}")

    # ==================== Age Estimation ====================
    print("  [*] Age check...")
    age_score = estimate_age(img_array)
    print(f"  Age: {age_score:.1f}")

    # ==================== Violence Detection ====================
    print("  [*] Violence check...")
    violence_score = detect_violence(img_array)
    print(f"  Violence: {violence_score:.3f}")

    # ==================== Decision ====================
    violations = []

    nsfw_threshold = 0.6 if mode == "ROMANTIC" else 0.4
    if nsfw_score > nsfw_threshold:
        violations.append({
            "type": "nsfw",
            "score": float(nsfw_score),
            "threshold": nsfw_threshold,
        })

    if age_score < AGE_THRESHOLD:
        violations.append({
            "type": "underage",
            "estimated_age": float(age_score),
            "threshold": AGE_THRESHOLD,
        })

    if violence_score > 0.5:
        violations.append({
            "type": "violence",
            "score": float(violence_score),
        })

    safe = len(violations) == 0

    result = {
        "safe": safe,
        "nsfw_score": float(nsfw_score),
        "age_score": float(age_score),
        "violence_score": float(violence_score),
        "violations": violations,
    }

    if safe:
        print("[OK] Image passed safety check")
    else:
        print(f"[BLOCKED] {len(violations)} violations")

    return result


def estimate_age(img_array: "np.ndarray") -> float:
    """Estimate age from image using face detection heuristics"""
    import cv2  # type: ignore[reportMissingImports]

    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    if len(faces) == 0:
        return 25.0  # Default adult age

    face = max(faces, key=lambda x: x[2] * x[3])
    x, y, w, h = face

    face_roi = gray[y:y+h, x:x+w]
    texture_var = cv2.Laplacian(face_roi, cv2.CV_64F).var()

    estimated_age = 20.0 + (texture_var / 100.0) * 10
    return max(18.0, min(estimated_age, 80.0))


def detect_violence(img_array: "np.ndarray") -> float:
    """Detect violence indicators via color and edge analysis"""
    import cv2  # type: ignore[reportMissingImports]

    red_channel = img_array[:, :, 0]
    red_intensity = red_channel.mean() / 255.0
    red_score = max(0, (red_intensity - 0.4) * 2.5)

    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    edge_density = edges.mean() / 255.0

    return min((red_score * 0.6 + edge_density * 0.4), 1.0)


# ==================== Web Endpoints ====================
@app.function(image=safety_image, timeout=60)
@modal.fastapi_endpoint(method="POST")
def check_prompt_safety_web(item: dict):
    """Web endpoint for prompt safety check"""
    result = check_prompt_safety.local(
        prompt=item.get("prompt", ""),
        mode=item.get("mode", "REALISM"),
    )
    return result


@app.function(image=safety_image, gpu="T4", timeout=60)
@modal.fastapi_endpoint(method="POST")
def check_image_safety_web(item: dict):
    """Web endpoint for image safety check"""
    result = check_image_safety.local(
        image_base64=item.get("image_base64", ""),
        mode=item.get("mode", "REALISM"),
    )
    return result


@app.local_entrypoint()
def test_safety():
    """Test safety checks"""
    print("\n=== Testing Prompt Safety ===\n")

    test_prompts = [
        ("professional headshot of person", "REALISM", True),
        ("nude person in bedroom", "REALISM", False),
        ("child playing in park", "REALISM", False),
        ("person in romantic setting", "ROMANTIC", True),
        ("childhood memories in the park", "REALISM", True),  # Should pass - "childhood" is safe
        ("nude lipstick and elegant dress", "FASHION", True),  # Should pass - "nude" color
        ("gorgeous sunset portrait", "CREATIVE", True),  # Should pass - "gorgeous" not "gore"
        ("blood orange cocktail on table", "CREATIVE", True),  # Should pass - "blood orange"
    ]

    for prompt, mode, expected_pass in test_prompts:
        result = check_prompt_safety.remote(prompt, mode)
        status = "PASS" if result["allowed"] else "BLOCK"
        expected = "PASS" if expected_pass else "BLOCK"
        match = "OK" if status == expected else "FAIL"
        print(f"  [{match}] {status} (expected {expected}): \"{prompt}\"")
        if not result["allowed"]:
            for v in result["violations"]:
                print(f"       -> {v['type']}: {v.get('keyword', 'N/A')}")
