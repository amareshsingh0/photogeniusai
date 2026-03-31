#!/usr/bin/env python3
"""
Test script to verify prompt enhancement pipeline
"""

import sys
from pathlib import Path

# Add API to path
api_path = Path(__file__).parent / "apps" / "api"
sys.path.insert(0, str(api_path))

from app.services.smart.prompt_enhancer import prompt_enhancer

# Test prompts
test_prompts = [
    "A pink Indian village house with old time nature feel",
    "Generate such an image in which a big house which is from the old times is with nature, the color of that house is pink and of natural leaf, that house should give such a feel. In Indian villagian house",
    "A family walking on a rainy road",
]

print("=" * 80)
print("PROMPT ENHANCEMENT TEST")
print("=" * 80)

for i, user_prompt in enumerate(test_prompts, 1):
    print(f"\nTest {i}:")
    print(f"Original: {user_prompt}")
    print("-" * 80)

    try:
        result = prompt_enhancer.enhance(
            user_prompt=user_prompt,
            quality='STANDARD'
        )

        print(f"Enhanced: {result['enhanced']}")
        print(f"Mode: {result['mode']}")
        print(f"Sub-mode: {result['sub_mode']}")
        print(f"Category: {result['category']}")
        print(f"Template: {result['template_key']}")
        print(f"Negative: {result['negative'][:80]}...")

        # Check if actually enhanced
        if result['original'] == result['enhanced']:
            print("WARNING: Prompt NOT enhanced (same as original)!")
        else:
            enhancement_len = len(result['enhanced']) - len(result['original'])
            print(f"SUCCESS: Added {enhancement_len} characters of enhancement")

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
