"""
Refinement Engine - Iterative Image Improvement
Enables chat-based refinement: "make it brighter", "change background", etc.

Architecture:
1. User provides natural language refinement request
2. Claude analyzes what needs to change
3. img2img pipeline refines the image
4. History maintained for context-aware refinements

Features:
- Natural language refinement requests
- Context-aware (uses generation history)
- Multiple refinement types (lighting, color, composition, expression, background)
- Adjustable strength (subtle to significant changes)
- Iterative refinement chain support
"""

import modal  # type: ignore[reportMissingImports]
import os
import json
import io
import base64
from typing import Dict, List, Optional, Any
from pathlib import Path

app = modal.App("photogenius-refinement-engine")

# ==================== Modal Config ====================

MODEL_DIR = "/models"
models_volume = modal.Volume.from_name("photogenius-models", create_if_missing=True)

refinement_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install([
        "torch==2.4.1",
        "torchvision==0.19.1",
        "diffusers==0.30.3",
        "transformers==4.44.2",
        "accelerate==0.34.2",
        "safetensors==0.4.5",
        "xformers==0.0.28.post1",
        "pillow==10.2.0",
        "numpy==1.26.3",
        "anthropic>=0.34.0",
        "fastapi[standard]",
    ])
    .run_commands(
        "apt-get update",
        "apt-get install -y libgl1-mesa-glx libglib2.0-0",
    )
)

# ==================== Refinement Types ====================

REFINEMENT_ASPECTS = {
    "lighting": {
        "keywords": ["bright", "dark", "light", "shadow", "illumination", "glow", "sunset", "sunrise"],
        "default_strength": 0.4,
    },
    "color": {
        "keywords": ["color", "warm", "cool", "saturated", "vibrant", "muted", "tone", "hue"],
        "default_strength": 0.35,
    },
    "composition": {
        "keywords": ["crop", "zoom", "angle", "framing", "position", "center", "off-center"],
        "default_strength": 0.5,
    },
    "expression": {
        "keywords": ["smile", "serious", "expression", "emotion", "mood", "happy", "neutral"],
        "default_strength": 0.45,
    },
    "background": {
        "keywords": ["background", "backdrop", "scene", "setting", "environment"],
        "default_strength": 0.6,
    },
    "style": {
        "keywords": ["style", "aesthetic", "look", "feel", "vibe", "mood"],
        "default_strength": 0.5,
    },
    "details": {
        "keywords": ["sharp", "blur", "detail", "texture", "quality", "resolution"],
        "default_strength": 0.3,
    },
}


@app.cls(
    gpu="A10G",  # A10G for img2img refinement
    image=refinement_image,
    volumes={
        MODEL_DIR: models_volume,
    },
    keep_warm=2,  # Keep 2 containers warm for faster refinement
    timeout=300,
    secrets=[
        modal.Secret.from_name("anthropic", required=False),
        modal.Secret.from_name("huggingface", required=False),
    ],
)
class RefinementEngine:
    """
    Iterative refinement of generated images.
    
    Users can chat: "make it brighter", "change background", "more smile"
    System understands context from generation history and applies appropriate changes.
    """
    
    @modal.enter()
    def load_models(self):
        """Load img2img pipeline once, reuse forever"""
        import torch  # type: ignore[reportMissingImports]
        from diffusers import StableDiffusionXLImg2ImgPipeline  # type: ignore[reportMissingImports]
        
        print("\n[*] Loading Refinement Engine...")
        
        hf_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        
        # Check for local model first
        model_path = Path(f"{MODEL_DIR}/sdxl-base")
        if model_path.exists() and any(model_path.iterdir()):
            model_repo = str(model_path)
            print(f"  Using local model: {model_repo}")
        else:
            model_repo = "stabilityai/stable-diffusion-xl-base-1.0"
            print(f"  Using HuggingFace model: {model_repo}")
        
        kwargs = {
            "torch_dtype": torch.float16,
            "variant": "fp16",
            "use_safetensors": True,
            "cache_dir": MODEL_DIR,
        }
        if hf_token:
            kwargs["token"] = hf_token
        
        try:
            self.pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained(
                model_repo, **kwargs
            ).to("cuda")
            
            # Enable memory optimizations
            try:
                self.pipe.enable_xformers_memory_efficient_attention()
            except:
                pass
            
            try:
                self.pipe.enable_model_cpu_offload()
            except:
                pass
            
            print("✅ Refinement Engine loaded (img2img pipeline ready)")
            
        except Exception as e:
            print(f"⚠️ Failed to load pipeline: {e}")
            self.pipe = None
        
        # Initialize Claude client (optional)
        try:
            from anthropic import Anthropic  # type: ignore[reportMissingImports]
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self.claude = Anthropic(api_key=api_key)
                self.claude_available = True
                print("✅ Claude initialized for refinement analysis")
            else:
                self.claude_available = False
                print("⚠️ Claude not available, using heuristic analysis")
        except Exception as e:
            print(f"⚠️ Claude initialization failed: {e}")
            self.claude_available = False
    
    def _analyze_refinement_request(
        self,
        refinement_request: str,
        generation_history: List[Dict],
        mode: str
    ) -> Dict[str, Any]:
        """
        Analyze refinement request to determine what needs to change.
        
        Uses Claude if available, falls back to heuristic keyword matching.
        """
        if self.claude_available:
            return self._claude_analyze_refinement(refinement_request, generation_history, mode)
        else:
            return self._heuristic_analyze_refinement(refinement_request, generation_history, mode)
    
    def _claude_analyze_refinement(
        self,
        refinement_request: str,
        generation_history: List[Dict],
        mode: str
    ) -> Dict[str, Any]:
        """Use Claude to analyze refinement request"""
        # Build history context
        history_context = []
        if generation_history:
            original_prompt = generation_history[0].get("prompt", "")
            history_context.append(f"Original prompt: {original_prompt}")
            
            for i, item in enumerate(generation_history[1:], 1):
                prev_request = item.get("request", "")
                prev_result = item.get("result", {})
                prev_change = prev_result.get("change_description", "")
                history_context.append(
                    f"Refinement {i}: '{prev_request}' → {prev_change}"
                )
        
        analysis_prompt = f"""You are an expert image refinement assistant. Analyze the user's refinement request and determine what needs to change.

Original generation context:
{chr(10).join(history_context) if history_context else "No previous refinements"}

Current refinement request: "{refinement_request}"
Generation mode: {mode}

Determine:
1. What aspect needs changing (lighting, color, composition, expression, background, style, details)
2. How much change is needed (subtle=0.2-0.3, moderate=0.4-0.5, significant=0.6-0.7)
3. Specific prompt modifications (what to add/remove)
4. Appropriate guidance scale (7.0-9.0)

Return ONLY valid JSON (no markdown, no explanation):
{{
  "aspect": "lighting",
  "change_description": "increase brightness and add warm golden hour lighting",
  "img2img_strength": 0.4,
  "prompt_modifications": {{
    "add": ["brighter lighting", "warm golden hour glow", "soft fill light"],
    "remove": ["dark", "moody", "low light"]
  }},
  "guidance_scale": 7.5,
  "num_inference_steps": 30
}}

Aspect options: lighting, color, composition, expression, background, style, details
Strength range: 0.2 (subtle) to 0.7 (significant changes)
"""
        
        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            
            content = response.content[0].text.strip()
            
            # Handle potential markdown code blocks
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])
            
            config = json.loads(content)
            
            # Validate and clamp values
            config["img2img_strength"] = max(0.2, min(0.7, config.get("img2img_strength", 0.4)))
            config["guidance_scale"] = max(7.0, min(9.0, config.get("guidance_scale", 7.5)))
            config["num_inference_steps"] = max(20, min(50, config.get("num_inference_steps", 30)))
            
            return config
            
        except Exception as e:
            print(f"⚠️ Claude analysis failed: {e}, using heuristic")
            return self._heuristic_analyze_refinement(refinement_request, generation_history, mode)
    
    def _heuristic_analyze_refinement(
        self,
        refinement_request: str,
        generation_history: List[Dict],
        mode: str
    ) -> Dict[str, Any]:
        """Heuristic keyword-based refinement analysis"""
        request_lower = refinement_request.lower()
        
        # Determine aspect from keywords
        aspect = "lighting"  # default
        max_matches = 0
        
        for aspect_name, aspect_data in REFINEMENT_ASPECTS.items():
            matches = sum(1 for keyword in aspect_data["keywords"] if keyword in request_lower)
            if matches > max_matches:
                max_matches = matches
                aspect = aspect_name
        
        # Determine strength from request intensity words
        strength = REFINEMENT_ASPECTS[aspect]["default_strength"]
        
        intensity_words = {
            "slight": 0.2, "subtle": 0.25, "little": 0.3,
            "more": 0.4, "bit": 0.35, "somewhat": 0.4,
            "much": 0.5, "significantly": 0.6, "completely": 0.7,
            "totally": 0.7, "very": 0.5, "really": 0.5,
        }
        
        for word, word_strength in intensity_words.items():
            if word in request_lower:
                strength = word_strength
                break
        
        # Build prompt modifications
        add_parts = []
        remove_parts = []
        
        # Lighting modifications
        if "bright" in request_lower or "brighter" in request_lower:
            add_parts.extend(["brighter lighting", "well-lit"])
            remove_parts.extend(["dark", "dim", "low light"])
        if "dark" in request_lower or "darker" in request_lower:
            add_parts.extend(["darker", "moody lighting"])
            remove_parts.extend(["bright", "overexposed"])
        
        # Color modifications
        if "warm" in request_lower:
            add_parts.extend(["warm tones", "golden"])
            remove_parts.extend(["cool", "blue"])
        if "cool" in request_lower:
            add_parts.extend(["cool tones", "blue"])
            remove_parts.extend(["warm", "orange"])
        if "vibrant" in request_lower or "saturated" in request_lower:
            add_parts.extend(["vibrant colors", "high saturation"])
            remove_parts.extend(["muted", "desaturated"])
        
        # Background modifications
        if "background" in request_lower:
            # Extract background description if provided
            if "beach" in request_lower:
                add_parts.append("beach background")
            if "office" in request_lower:
                add_parts.append("office background")
            if "nature" in request_lower or "outdoor" in request_lower:
                add_parts.append("natural outdoor background")
        
        # Expression modifications
        if "smile" in request_lower:
            add_parts.extend(["smiling", "happy expression"])
            remove_parts.extend(["serious", "neutral expression"])
        if "serious" in request_lower:
            add_parts.extend(["serious expression", "professional"])
            remove_parts.extend(["smiling", "casual"])
        
        # Build change description
        change_description = f"adjust {aspect}"
        if add_parts:
            change_description += f": add {', '.join(add_parts[:3])}"
        if remove_parts:
            change_description += f", remove {', '.join(remove_parts[:2])}"
        
        return {
            "aspect": aspect,
            "change_description": change_description,
            "img2img_strength": strength,
            "prompt_modifications": {
                "add": add_parts[:5],  # Limit to 5 additions
                "remove": remove_parts[:3],  # Limit to 3 removals
            },
            "guidance_scale": 7.5,
            "num_inference_steps": 30,
        }
    
    def _build_refined_prompt(
        self,
        original_prompt: str,
        prompt_modifications: Dict[str, List[str]],
        mode: str
    ) -> tuple[str, str]:
        """
        Build refined prompt and negative prompt.
        
        Returns:
            (refined_prompt, negative_prompt)
        """
        # Start with original prompt
        refined_parts = [original_prompt]
        
        # Add modifications
        for add_part in prompt_modifications.get("add", []):
            refined_parts.append(add_part)
        
        refined_prompt = ", ".join(refined_parts)
        
        # Build negative prompt
        negative_parts = prompt_modifications.get("remove", [])
        negative_parts.extend([
            "low quality", "blurry", "bad anatomy", "distorted",
            "deformed", "ugly", "bad proportions"
        ])
        
        # Mode-specific negatives
        if mode == "REALISM":
            negative_parts.extend(["cartoon", "anime", "illustration", "painting"])
        elif mode == "CREATIVE":
            negative_parts.extend(["boring", "plain", "generic"])
        
        negative_prompt = ", ".join(negative_parts)
        
        return refined_prompt, negative_prompt
    
    @modal.method()
    def refine(
        self,
        original_image: bytes,
        refinement_request: str,
        generation_history: List[Dict],
        mode: str = "REALISM",
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Refine image based on natural language request.
        
        Args:
            original_image: Original image as bytes (JPEG/PNG)
            refinement_request: Natural language request (e.g., "make it brighter", "change background to beach")
            generation_history: List of previous generation/refinement steps:
                [
                    {"prompt": "original prompt"},
                    {"request": "make it brighter", "result": {...}},
                    ...
                ]
            mode: Generation mode (REALISM, CREATIVE, ROMANTIC, FASHION, CINEMATIC)
            seed: Optional random seed for reproducibility
        
        Returns:
            {
                "image_base64": "...",
                "change_description": "increase brightness and warmth",
                "strength_used": 0.4,
                "prompt_used": "refined prompt",
                "negative_prompt_used": "negative prompt",
                "aspect": "lighting"
            }
        """
        if self.pipe is None:
            raise RuntimeError("Refinement pipeline not loaded")
        
        print(f"\n🔧 Refining: '{refinement_request}'")
        print(f"   Mode: {mode}")
        print(f"   History length: {len(generation_history)}")
        
        # Get original prompt from history
        if not generation_history:
            raise ValueError("generation_history must contain at least the original prompt")
        
        original_prompt = generation_history[0].get("prompt", "")
        if not original_prompt:
            raise ValueError("generation_history[0] must contain 'prompt'")
        
        # Analyze refinement request
        config = self._analyze_refinement_request(refinement_request, generation_history, mode)
        
        print(f"   Aspect: {config['aspect']}")
        print(f"   Strength: {config['img2img_strength']}")
        print(f"   Change: {config['change_description']}")
        
        # Build refined prompt
        refined_prompt, negative_prompt = self._build_refined_prompt(
            original_prompt,
            config["prompt_modifications"],
            mode
        )
        
        # Load and prepare image
        from PIL import Image  # type: ignore[reportMissingImports]
        import torch  # type: ignore[reportMissingImports]
        
        original_img = Image.open(io.BytesIO(original_image)).convert("RGB")
        
        # Resize if needed (SDXL expects 1024x1024 or multiples)
        if original_img.size[0] != 1024 or original_img.size[1] != 1024:
            # Maintain aspect ratio, pad to square
            w, h = original_img.size
            size = max(w, h)
            new_img = Image.new("RGB", (size, size), (0, 0, 0))
            new_img.paste(original_img, ((size - w) // 2, (size - h) // 2))
            original_img = new_img.resize((1024, 1024), Image.Resampling.LANCZOS)
        
        # Generate refined image
        generator = None
        if seed is not None:
            generator = torch.Generator(device="cuda").manual_seed(int(seed))
        
        print(f"   Generating refined image...")
        
        refined_result = self.pipe(
            prompt=refined_prompt,
            negative_prompt=negative_prompt,
            image=original_img,
            strength=config["img2img_strength"],
            guidance_scale=config["guidance_scale"],
            num_inference_steps=config["num_inference_steps"],
            generator=generator,
        )
        
        refined_img = refined_result.images[0]  # type: ignore[union-attr]
        
        # Convert to base64
        output_buffer = io.BytesIO()
        refined_img.save(output_buffer, format="JPEG", quality=95)
        refined_image_bytes = output_buffer.getvalue()
        refined_image_base64 = base64.b64encode(refined_image_bytes).decode()
        
        print(f"✅ Refinement complete")
        
        return {
            "image": refined_image_bytes,  # Bytes (matches spec)
            "image_bytes": refined_image_bytes,  # Alias for convenience
            "image_base64": refined_image_base64,  # Base64 for web APIs
            "change_description": config["change_description"],
            "strength_used": config["img2img_strength"],
            "prompt_used": refined_prompt,
            "negative_prompt_used": negative_prompt,
            "aspect": config["aspect"],
            "guidance_scale": config["guidance_scale"],
            "num_inference_steps": config["num_inference_steps"],
        }
    
    @modal.method()
    def refine_batch(
        self,
        original_image: bytes,
        refinement_requests: List[str],
        generation_history: List[Dict],
        mode: str = "REALISM",
    ) -> List[Dict[str, Any]]:
        """
        Apply multiple refinements in sequence.
        
        Args:
            original_image: Original image as bytes
            refinement_requests: List of refinement requests to apply sequentially
            generation_history: Generation history
            mode: Generation mode
        
        Returns:
            List of refinement results (one per request)
        """
        results = []
        current_image = original_image
        current_history = generation_history.copy()
        
        for i, request in enumerate(refinement_requests):
            print(f"\n[{i+1}/{len(refinement_requests)}] Processing: '{request}'")
            
            result = self.refine(
                original_image=current_image,
                refinement_request=request,
                generation_history=current_history,
                mode=mode,
            )
            
            results.append(result)
            
            # Update for next iteration
            current_image = result["image_bytes"]
            current_history.append({
                "request": request,
                "result": result,
            })
        
        return results


# Module-level export for services.__init__.py (use modal.Cls.lookup for remote)
refinement_engine = RefinementEngine

# ==================== Web Endpoints ====================

@app.function(
    image=refinement_image,
    gpu="A10G",
    timeout=300,
    secrets=[
        modal.Secret.from_name("anthropic", required=False),
        modal.Secret.from_name("huggingface", required=False),
    ],
)
@modal.fastapi_endpoint(method="POST")
def refine_web(item: dict):
    """
    Web endpoint for image refinement.

    Request body:
    {
        "image_base64": "...",  // Base64 encoded image
        "refinement_request": "make it brighter",
        "generation_history": [
            {"prompt": "original prompt"},
            // ... previous refinements
        ],
        "mode": "REALISM",  // Optional
        "seed": 42  // Optional
    }

    Response:
    {
        "image_base64": "...",
        "change_description": "...",
        "strength_used": 0.4,
        "prompt_used": "...",
        ...
    }
    """
    import base64

    image_base64 = item.get("image_base64", "")
    if not image_base64:
        return {"error": "image_base64 is required"}

    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        return {"error": f"Invalid base64 image: {e}"}

    refinement_request = item.get("refinement_request", "")
    if not refinement_request:
        return {"error": "refinement_request is required"}

    generation_history = item.get("generation_history", [])
    if not generation_history:
        return {"error": "generation_history is required (must contain at least original prompt)"}

    mode = item.get("mode", "REALISM")
    seed = item.get("seed")

    # Use Modal's cls lookup for remote invocation
    engine = modal.Cls.lookup("photogenius-refinement-engine", "RefinementEngine")
    result = engine().refine.remote(
        original_image=image_bytes,
        refinement_request=refinement_request,
        generation_history=generation_history,
        mode=mode,
        seed=seed,
    )

    return result


@app.function(
    image=refinement_image,
    gpu="A10G",
    timeout=600,  # Longer timeout for batch
    secrets=[
        modal.Secret.from_name("anthropic", required=False),
        modal.Secret.from_name("huggingface", required=False),
    ],
)
@modal.fastapi_endpoint(method="POST")
def refine_batch_web(item: dict):
    """
    Web endpoint for batch refinement (multiple requests in sequence).
    
    Request body:
    {
        "image_base64": "...",
        "refinement_requests": ["make it brighter", "change background"],
        "generation_history": [...],
        "mode": "REALISM"
    }
    """
    import base64
    
    image_base64 = item.get("image_base64", "")
    if not image_base64:
        return {"error": "image_base64 is required"}
    
    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as e:
        return {"error": f"Invalid base64 image: {e}"}
    
    refinement_requests = item.get("refinement_requests", [])
    if not refinement_requests:
        return {"error": "refinement_requests is required"}
    
    generation_history = item.get("generation_history", [])
    if not generation_history:
        return {"error": "generation_history is required"}
    
    mode = item.get("mode", "REALISM")

    # Use Modal's cls lookup for remote invocation
    engine = modal.Cls.lookup("photogenius-refinement-engine", "RefinementEngine")
    results = engine().refine_batch.remote(
        original_image=image_bytes,
        refinement_requests=refinement_requests,
        generation_history=generation_history,
        mode=mode,
    )

    return {
        "results": results,
        "count": len(results),
    }


# ==================== Testing ====================

@app.local_entrypoint()
def test_refinement():
    """Test refinement engine"""
    print("\n" + "="*60)
    print("🔧 Testing Refinement Engine")
    print("="*60 + "\n")
    
    print("This test requires:")
    print("1. A generated image (from orchestrator or identity engine)")
    print("2. Generation history with original prompt")
    print("\nExample usage:")
    print("  # 1. Generate initial image")
    print("  result = orchestrator.orchestrate.remote(...)")
    print("  image_bytes = base64.b64decode(result['images'][0]['image_base64'])")
    print("  history = [{'prompt': result['parsed_prompt']['full_prompt']}]")
    print("\n  # 2. Refine")
    print("  refinement = modal.Cls.from_name('photogenius-refinement-engine', 'RefinementEngine')")
    print("  refined = refinement.refine.remote(")
    print("      original_image=image_bytes,")
    print('      refinement_request="make it brighter",')
    print("      generation_history=history,")
    print('      mode="REALISM"')
    print("  )")
    print("\n  # 3. Refine again")
    print("  history.append({'request': 'make it brighter', 'result': refined})")
    print("  refined2 = refinement.refine.remote(")
    print("      original_image=refined['image_bytes'],")
    print('      refinement_request="change background to beach",')
    print("      generation_history=history,")
    print('      mode="REALISM"')
    print("  )")
    print("\n" + "="*60)
    print("✅ Test instructions displayed")
    print("="*60)
