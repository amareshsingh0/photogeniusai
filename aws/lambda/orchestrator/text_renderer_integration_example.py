"""
Integration Example: Using Text Renderer with PhotoGenius Services

This example shows how to integrate the text renderer with:
1. Identity Engine (for face-preserving generation)
2. Creative Engine (for style-based generation)
3. Orchestrator (for end-to-end generation)

Usage:
    modal run ai-pipeline/services/text_renderer_integration_example.py
"""

import modal  # type: ignore[reportMissingImports]
import base64
import io
from typing import Dict, List, Optional

# Define app first so @app.local_entrypoint() can use it
app = modal.App("photogenius-text-renderer-examples")


# ==================== Example 1: Identity Engine + Text ====================

def example_identity_with_text():
    """
    Generate a professional headshot with identity preservation,
    then add text overlay.
    """
    print("\n" + "="*60)
    print("Example 1: Identity Engine + Text Renderer")
    print("="*60)
    
    # Get services
    identity_engine = modal.Cls.from_name("photogenius-identity-engine", "IdentityEngine")
    text_renderer = modal.Cls.from_name("photogenius-text-renderer", "TextRenderer")
    
    # 1. Generate image with identity
    print("\n[1/3] Generating image with Identity Engine...")
    result = identity_engine.generate.remote(
        prompt="professional headshot, business attire, office background",
        identity_id="user_123",  # Your identity ID
        mode="REALISM",
        num_images=2
    )
    
    # 2. Add text to each image
    print("[2/3] Adding text overlay...")
    images_with_text = []
    for img_data in result["images"]:
        image_base64 = img_data["image_base64"]
        image_bytes = base64.b64decode(image_base64)
        
        # Add professional text
        image_with_text = text_renderer.add_text.remote(
            image=image_bytes,
            text="PROFESSIONAL\nHEADSHOT",
            style="bold",
            placement="top"
        )
        
        images_with_text.append({
            "image_base64": base64.b64encode(image_with_text).decode(),
            "original_score": img_data.get("score", 0)
        })
    
    print("[3/3] Complete!")
    print(f"Generated {len(images_with_text)} images with text")
    
    return images_with_text


# ==================== Example 2: Creative Engine + Text ====================

def example_creative_with_text():
    """
    Generate a creative image with style mixing,
    then add poster-style text.
    """
    print("\n" + "="*60)
    print("Example 2: Creative Engine + Text Renderer")
    print("="*60)
    
    creative_engine = modal.Cls.from_name("photogenius-creative-engine", "CreativeEngine")
    text_renderer = modal.Cls.from_name("photogenius-text-renderer", "TextRenderer")
    
    # 1. Generate with style preset
    print("\n[1/3] Generating creative image...")
    result = creative_engine.generate_with_preset.remote(
        prompt="fashion model, urban street, dramatic lighting",
        preset_name="Fashion Editorial",
        num_images=2
    )
    
    # 2. Add poster-style text
    print("[2/3] Adding poster text...")
    images_with_text = []
    for img_data in result["images"]:
        image_base64 = img_data["image_base64"]
        image_bytes = base64.b64decode(image_base64)
        
        # Add event poster text
        image_with_text = text_renderer.add_text.remote(
            image=image_bytes,
            text="SUMMER COLLECTION 2026\nNOW AVAILABLE",
            style="poster",
            placement="center"
        )
        
        images_with_text.append({
            "image_base64": base64.b64encode(image_with_text).decode()
        })
    
    print("[3/3] Complete!")
    return images_with_text


# ==================== Example 3: Orchestrator + Text ====================

def example_orchestrator_with_text():
    """
    Use the orchestrator for end-to-end generation,
    then add text as post-processing step.
    """
    print("\n" + "="*60)
    print("Example 3: Orchestrator + Text Renderer")
    print("="*60)
    
    orchestrator = modal.Cls.from_name("photogenius-orchestrator", "Orchestrator")
    text_renderer = modal.Cls.from_name("photogenius-text-renderer", "TextRenderer")
    
    # 1. Generate with orchestrator
    print("\n[1/3] Orchestrating generation...")
    result = orchestrator.generate.remote(
        prompt="beach sunset portrait",
        mode="ROMANTIC",
        identity_id="user_123",  # Optional
        num_images=2
    )
    
    # 2. Add elegant text overlay
    print("[2/3] Adding elegant text...")
    final_images = []
    for img_data in result["images"]:
        image_base64 = img_data["image_base64"]
        image_bytes = base64.b64decode(image_base64)
        
        # Add romantic text
        image_with_text = text_renderer.add_text.remote(
            image=image_bytes,
            text="Golden Hour\nMemories",
            style="elegant",
            placement="bottom"
        )
        
        final_images.append({
            "image_base64": base64.b64encode(image_with_text).decode(),
            "prompt_used": result.get("prompt_used", ""),
            "mode": result.get("mode", "")
        })
    
    print("[3/3] Complete!")
    return final_images


# ==================== Example 4: Custom Text Configuration ====================

def example_custom_text_config():
    """
    Use custom text configuration for precise control.
    """
    print("\n" + "="*60)
    print("Example 4: Custom Text Configuration")
    print("="*60)
    
    text_renderer = modal.Cls.from_name("photogenius-text-renderer", "TextRenderer")
    
    # Load a sample image (in production, this would come from generation)
    # For demo, we'll analyze an image first
    print("\n[1/2] Analyzing image for optimal text placement...")
    
    # Assuming you have image_bytes from somewhere
    # image_bytes = load_image_bytes()
    
    # Get recommended config
    # config = text_renderer.analyze_for_text.remote(
    #     image=image_bytes,
    #     text="CUSTOM TEXT"
    # )
    # print(f"Recommended config: {config}")
    
    # 2. Apply custom configuration
    print("[2/2] Applying custom text configuration...")
    
    custom_config = {
        "placement": {"x": 0.5, "y": 0.15},  # Top center
        "font_style": "display",
        "font_size_ratio": 0.12,  # Large text
        "text_color": [255, 215, 0],  # Gold color
        "stroke_color": [0, 0, 0],  # Black outline
        "stroke_width": 4,
        "shadow": True,
        "alignment": "center",
        "opacity": 1.0
    }
    
    # result = text_renderer.add_text_with_config.remote(
    #     image=image_bytes,
    #     text="CUSTOM\nSTYLED TEXT",
    #     config=custom_config
    # )
    
    print("Custom config example prepared!")
    return custom_config


# ==================== Example 5: Watermark ====================

def example_watermark():
    """
    Add watermark to generated images.
    """
    print("\n" + "="*60)
    print("Example 5: Adding Watermark")
    print("="*60)
    
    text_renderer = modal.Cls.from_name("photogenius-text-renderer", "TextRenderer")
    
    # Assuming you have image_bytes
    # image_bytes = load_image_bytes()
    
    # Add watermark
    # watermarked = text_renderer.add_watermark.remote(
    #     image=image_bytes,
    #     text="© PhotoGenius AI",
    #     position="bottom_right",
    #     opacity=0.3
    # )
    
    print("Watermark example prepared!")
    print("Use add_watermark() for copyright notices and branding")


# ==================== Main Entry Point ====================

@app.local_entrypoint()
def run_examples():
    """Run all integration examples"""
    print("\n" + "="*60)
    print("PhotoGenius Text Renderer - Integration Examples")
    print("="*60)
    
    print("\nAvailable examples:")
    print("1. Identity Engine + Text")
    print("2. Creative Engine + Text")
    print("3. Orchestrator + Text")
    print("4. Custom Text Configuration")
    print("5. Watermark")
    
    print("\nTo run examples:")
    print("1. Deploy all services:")
    print("   modal deploy ai-pipeline/services/identity_engine.py")
    print("   modal deploy ai-pipeline/services/creative_engine.py")
    print("   modal deploy ai-pipeline/services/orchestrator.py")
    print("   modal deploy ai-pipeline/services/text_renderer.py")
    print("\n2. Uncomment the example functions above")
    print("3. Run: modal run ai-pipeline/services/text_renderer_integration_example.py")
    
    # Uncomment to run examples:
    # example_identity_with_text()
    # example_creative_with_text()
    # example_orchestrator_with_text()
    # example_custom_text_config()
    # example_watermark()
