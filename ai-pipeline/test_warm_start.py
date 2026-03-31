"""
Test script to verify model pre-loading works correctly.

This script tests that:
1. First request: Slow (container startup + model loading)
2. Second request: Instant (model already loaded in warm container)

Run: aws run test_warm_start.py
"""

import aws
import time

# Import the generation service app and class
from services.generation_service import app as generation_app, GenerationService

# Use the same app context
app = generation_app

@app.local_entrypoint()
def test_warm_start():
    """Test that warm containers provide instant second requests"""
    print("\n" + "="*60)
    print("🔥 WARM START TEST - Model Pre-loading Verification")
    print("="*60 + "\n")
    
    # Create service instance - this will use the deployed app
    service = GenerationService()
    
    test_prompt = "professional headshot of person in business suit"
    
    # First request - should be slow (container startup + model loading)
    print("[TEST 1/2] First request (cold start)...")
    print("Expected: Slow (~30-60s) - container startup + model loading")
    print("-" * 60)
    
    start_time_1 = time.time()
    try:
        result_1 = service.generate_images.remote(
            user_id="test_user",
            identity_id="test_identity_1",
            prompt=test_prompt,
            mode="REALISM",
            num_candidates=1,  # Just 1 for speed
            seed=42,
        )
        elapsed_1 = time.time() - start_time_1
        print(f"✅ First request completed in {elapsed_1:.2f}s")
        print(f"   Generated {len(result_1)} images")
    except Exception as e:
        print(f"❌ First request failed: {e}")
        return
    
    # Wait a moment to ensure container stays warm
    print("\n[WAIT] Waiting 2 seconds to ensure container stays warm...")
    time.sleep(2)
    
    # Second request - should be instant (model already loaded)
    print("\n[TEST 2/2] Second request (warm start)...")
    print("Expected: Fast (<5s) - model already loaded in warm container")
    print("-" * 60)
    
    start_time_2 = time.time()
    try:
        result_2 = service.generate_images.remote(
            user_id="test_user",
            identity_id="test_identity_1",
            prompt="office portrait, professional lighting",
            mode="REALISM",
            num_candidates=1,  # Just 1 for speed
            seed=43,
        )
        elapsed_2 = time.time() - start_time_2
        print(f"✅ Second request completed in {elapsed_2:.2f}s")
        print(f"   Generated {len(result_2)} images")
    except Exception as e:
        print(f"❌ Second request failed: {e}")
        return
    
    # Analysis
    print("\n" + "="*60)
    print("📊 RESULTS ANALYSIS")
    print("="*60)
    print(f"First request (cold):  {elapsed_1:.2f}s")
    print(f"Second request (warm): {elapsed_2:.2f}s")
    print(f"Speedup:               {elapsed_1/elapsed_2:.1f}x faster")
    print()
    
    if elapsed_2 < 10:
        print("✅ SUCCESS: Second request was fast (<10s)")
        print("   Model pre-loading is working correctly!")
        print("   Container stayed warm and reused loaded model.")
    elif elapsed_2 < elapsed_1 * 0.5:
        print("✅ GOOD: Second request was significantly faster")
        print("   Model pre-loading appears to be working.")
    else:
        print("⚠️  WARNING: Second request was not much faster")
        print("   This might indicate:")
        print("   - Container did not stay warm")
        print("   - Model was reloaded")
        print("   - Network latency")
    
    print("\n" + "="*60)
    print("💡 TIP: For production, ensure:")
    print("   - min_containers=1 is set (always 1 container ready)")
    print("   - scaledown_window=300 (5 min warm)")
    print("   - Models are pre-loaded in @aws.enter()")
    print("="*60 + "\n")
