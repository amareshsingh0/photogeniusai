"""
Multi-ControlNet Pipeline with Online Reward Guidance.

The core innovation of PhotoGenius AI:
- Uses 3 ControlNets (depth, openpose, canny) for structure
- Guides generation in real-time using reward signals
- Adapts during denoising based on anatomy/physics/aesthetic feedback
P0: Multi-ControlNet with guided diffusion — Task 4.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np  # type: ignore[reportMissingImports]

try:
    import torch  # type: ignore[reportMissingImports]

    HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    HAS_TORCH = False

try:
    from diffusers.models.controlnet import ControlNetModel  # type: ignore[reportMissingImports]
    from diffusers.pipelines.controlnet.pipeline_controlnet_sd_xl import (  # type: ignore[reportMissingImports]
        StableDiffusionXLControlNetPipeline,
    )
    from diffusers.schedulers.scheduling_ddim import DDIMScheduler  # type: ignore[reportMissingImports]

    HAS_DIFFUSERS = True
except ImportError:
    ControlNetModel = None  # type: ignore[assignment]
    StableDiffusionXLControlNetPipeline = None  # type: ignore[assignment]
    DDIMScheduler = None  # type: ignore[assignment]
    HAS_DIFFUSERS = False

try:
    from PIL import Image  # type: ignore[reportMissingImports]

    HAS_PIL = True
except ImportError:
    Image = None  # type: ignore[assignment]
    HAS_PIL = False

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    tqdm = lambda x, **kw: x
    HAS_TQDM = False

try:
    from .reward_model import RewardModel
except ImportError:
    RewardModel = None

try:
    from .control_image_generator import ControlImageGenerator
except ImportError:
    ControlImageGenerator = None


class GuidedDiffusionPipeline:
    """
    Multi-ControlNet generation with real-time reward guidance.

    Process:
    1. Load ControlNets (depth, openpose, canny)
    2. Generate control images from scene graph
    3. Run guided diffusion:
       - At each step, compute rewards
       - Adjust noise prediction based on rewards
       - Continue until convergence
    4. Return high-quality image
    """

    def __init__(
        self,
        device: str = "cuda",
        use_reward_guidance: bool = True,
        load_models: bool = True,
    ) -> None:
        self.device = device or ("cuda" if HAS_TORCH and torch and torch.cuda.is_available() else "cpu")  # type: ignore[reportOptionalMemberAccess]
        self.use_reward_guidance = use_reward_guidance
        self.pipeline = None
        self.controlnet_depth = None
        self.controlnet_openpose = None
        self.controlnet_canny = None
        self.control_generator = None
        self.reward_model = None

        if ControlImageGenerator is not None:
            self.control_generator = ControlImageGenerator()

        if use_reward_guidance and RewardModel is not None:
            self.reward_model = RewardModel(device=self.device, load_clip=False)

        if not load_models or not HAS_TORCH or not HAS_DIFFUSERS:
            return

        self._load_pipeline()

    def _load_pipeline(self) -> None:
        """Load ControlNets and SDXL pipeline (requires GPU and model download)."""
        if not HAS_TORCH or not HAS_DIFFUSERS or torch is None:
            return
        try:
            dtype = torch.float16 if self.device == "cuda" else torch.float32  # type: ignore[reportOptionalMemberAccess]
            depth_cn = ControlNetModel.from_pretrained("diffusers/controlnet-depth-sdxl-1.0", torch_dtype=dtype)  # type: ignore[reportOptionalMemberAccess]
            self.controlnet_depth = depth_cn.to(self.device)  # type: ignore[reportAttributeAccessIssue]
            openpose_cn = ControlNetModel.from_pretrained("thibaud/controlnet-openpose-sdxl-1.0", torch_dtype=dtype)  # type: ignore[reportOptionalMemberAccess]
            self.controlnet_openpose = openpose_cn.to(self.device)  # type: ignore[reportAttributeAccessIssue]
            canny_cn = ControlNetModel.from_pretrained("diffusers/controlnet-canny-sdxl-1.0", torch_dtype=dtype)  # type: ignore[reportOptionalMemberAccess]
            self.controlnet_canny = canny_cn.to(self.device)  # type: ignore[reportAttributeAccessIssue]

            pipe = StableDiffusionXLControlNetPipeline.from_pretrained(  # type: ignore[reportOptionalMemberAccess]
                "stabilityai/stable-diffusion-xl-base-1.0",
                controlnet=[
                    self.controlnet_depth,
                    self.controlnet_openpose,
                    self.controlnet_canny,
                ],
                torch_dtype=dtype,
                variant="fp16" if self.device == "cuda" else None,
                use_safetensors=True,
            )
            self.pipeline = pipe.to(self.device)  # type: ignore[reportAttributeAccessIssue]

            self.pipeline.scheduler = DDIMScheduler.from_config(  # type: ignore[reportOptionalMemberAccess]
                self.pipeline.scheduler.config
            )

            if self.device == "cuda":
                self.pipeline.enable_model_cpu_offload()
                self.pipeline.enable_vae_slicing()
                try:
                    self.pipeline.enable_xformers_memory_efficient_attention()
                except Exception:
                    pass

            if (
                self.use_reward_guidance
                and RewardModel is not None
                and self.reward_model is not None
            ):
                self.reward_model = RewardModel(device=self.device, load_clip=True)
        except Exception:
            self.pipeline = None
            self.controlnet_depth = None
            self.controlnet_openpose = None
            self.controlnet_canny = None

    def generate(
        self,
        prompt: str,
        negative_prompt: str,
        scene_graph: Dict[str, Any],
        physics_state: Dict[str, Any],
        num_inference_steps: int = 40,
        guidance_scale: float = 7.5,
        controlnet_conditioning_scale: Optional[List[float]] = None,
        reward_guidance_weight: float = 0.3,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate image with multi-ControlNet and optional reward guidance.

        Args:
            prompt: Enhanced positive prompt
            negative_prompt: Negative prompt
            scene_graph: From SceneGraphCompiler
            physics_state: From PhysicsMicroSimulation
            num_inference_steps: Denoising steps (20-50)
            guidance_scale: CFG scale (7-12)
            controlnet_conditioning_scale: [depth, openpose, canny] weights
            reward_guidance_weight: How much to use rewards (0.0-1.0)
            width: Output width
            height: Output height
            seed: Random seed for reproducibility

        Returns:
            image: PIL Image
            control_images: dict of control images
            rewards_history: list of reward dicts (if reward-guided)
            metadata: dict
        """
        if not HAS_TORCH or not HAS_DIFFUSERS:
            raise RuntimeError(
                "GuidedDiffusionPipeline.generate requires torch and diffusers. "
                "Install: pip install torch diffusers"
            )
        if self.pipeline is None:
            self._load_pipeline()
        if self.pipeline is None:
            raise RuntimeError(
                "Pipeline could not be loaded (GPU and model download required)."
            )

        if controlnet_conditioning_scale is None:
            controlnet_conditioning_scale = [0.6, 0.9, 0.4]

        generator = None
        if seed is not None and torch is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)

        if self.control_generator is None:
            raise RuntimeError("ControlImageGenerator not available.")
        control_images = self.control_generator.generate_all_controls(
            scene_graph, width, height
        )
        control_image_list = [
            control_images["depth"],
            control_images["openpose"],
            control_images["canny"],
        ]
        if HAS_PIL and Image is not None:
            control_image_list = [
                (
                    img
                    if isinstance(img, Image.Image)
                    else Image.fromarray(np.asarray(img))
                )
                for img in control_image_list
            ]

        if (
            self.use_reward_guidance
            and reward_guidance_weight > 0
            and self.reward_model is not None
        ):
            result = self._generate_with_guidance(
                prompt=prompt,
                negative_prompt=negative_prompt,
                control_images=control_image_list,
                scene_graph=scene_graph,
                physics_state=physics_state,
                num_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                controlnet_scales=controlnet_conditioning_scale,
                reward_weight=reward_guidance_weight,
                generator=generator,
                width=width,
                height=height,
            )
        else:
            result = self._generate_standard(
                prompt=prompt,
                negative_prompt=negative_prompt,
                control_images=control_image_list,
                num_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                controlnet_scales=controlnet_conditioning_scale,
                generator=generator,
            )

        result["control_images"] = control_images
        return result

    def _generate_standard(
        self,
        prompt: str,
        negative_prompt: str,
        control_images: List[Any],
        num_steps: int,
        guidance_scale: float,
        controlnet_scales: List[float],
        generator: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Standard generation without reward guidance."""
        if self.pipeline is None:
            raise RuntimeError("Pipeline not loaded")
        out = self.pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            image=control_images,
            controlnet_conditioning_scale=controlnet_scales,
            num_inference_steps=num_steps,
            guidance_scale=guidance_scale,
            generator=generator,
        )
        image = out.images[0] if getattr(out, "images", None) else out[0]
        return {
            "image": image,
            "rewards_history": [],
            "metadata": {
                "method": "standard",
                "steps": num_steps,
                "guidance_scale": guidance_scale,
            },
        }

    def _generate_with_guidance(
        self,
        prompt: str,
        negative_prompt: str,
        control_images: List[Any],
        scene_graph: Dict[str, Any],
        physics_state: Dict[str, Any],
        num_steps: int,
        guidance_scale: float,
        controlnet_scales: List[float],
        reward_weight: float,
        generator: Optional[Any] = None,
        width: int = 1024,
        height: int = 1024,
    ) -> Dict[str, Any]:
        """Generate with real-time reward guidance."""
        rewards_history: List[Dict[str, Any]] = []

        encode_prompt = getattr(self.pipeline, "encode_prompt", None)
        if encode_prompt is None:
            return self._generate_standard(
                prompt,
                negative_prompt,
                control_images,
                num_steps,
                guidance_scale,
                controlnet_scales,
                generator,
            )

        try:
            out = encode_prompt(  # type: ignore[reportOptionalCall]
                prompt=prompt,
                prompt_2=prompt,
                device=self.device,
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
                negative_prompt=negative_prompt or "",
                negative_prompt_2=negative_prompt or "",
            )
        except TypeError:
            out = encode_prompt(
                prompt,
                device=self.device,
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
                negative_prompt=negative_prompt or "",
            )
        # SDXL encode_prompt may return (prompt_embeds, negative_embeds) or single concatenated tensor
        if isinstance(out, (list, tuple)) and len(out) == 2:
            prompt_embeds = torch.cat([out[1], out[0]], dim=0)  # type: ignore[reportOptionalMemberAccess]
        else:
            prompt_embeds = out

        prepare_img = getattr(self.pipeline, "prepare_image", None) or getattr(
            self.pipeline, "prepare_control_image", None
        )
        if prepare_img is None:
            return self._generate_standard(
                prompt,
                negative_prompt,
                control_images,
                num_steps,
                guidance_scale,
                controlnet_scales,
                generator,
            )

        try:
            control_images_tensor = prepare_img(
                image=control_images,
                width=width,
                height=height,
                batch_size=1,
                num_images_per_prompt=1,
                device=self.device,
                dtype=prompt_embeds.dtype,  # type: ignore[reportAttributeAccessIssue]
                do_classifier_free_guidance=True,
            )
        except TypeError:
            control_images_tensor = prepare_img(
                image=control_images,
                width=width,
                height=height,
                batch_size=1,
                num_images_per_prompt=1,
                device=self.device,
                dtype=prompt_embeds.dtype,  # type: ignore[reportAttributeAccessIssue]
            )
        # Multi-controlnet: prepare_image may return list of tensors (one per control)
        if isinstance(control_images_tensor, (list, tuple)):
            control_images_tensor = [
                t if t.shape[0] >= 2 else torch.cat([t] * 2, dim=0)  # type: ignore[reportOptionalMemberAccess]
                for t in control_images_tensor
            ]
        elif (
            hasattr(control_images_tensor, "shape")
            and control_images_tensor.shape[0] == 1
        ):
            control_images_tensor = torch.cat([control_images_tensor] * 2)  # type: ignore[reportOptionalMemberAccess]

        prepare_lat = getattr(self.pipeline, "prepare_latent_image", None) or getattr(
            self.pipeline, "prepare_latents", None
        )
        if prepare_lat is None:
            return self._generate_standard(
                prompt,
                negative_prompt,
                control_images,
                num_steps,
                guidance_scale,
                controlnet_scales,
                generator,
            )

        latents = prepare_lat(
            batch_size=1,
            num_channels_latents=getattr(
                self.pipeline.unet.config, "in_channels", 4  # type: ignore[reportOptionalMemberAccess,reportAttributeAccessIssue]
            ),
            height=height,
            width=width,
            dtype=prompt_embeds.dtype,  # type: ignore[reportAttributeAccessIssue]
            device=self.device,
            generator=generator,
        )

        self.pipeline.scheduler.set_timesteps(num_steps, device=self.device)  # type: ignore[reportOptionalMemberAccess]
        timesteps = self.pipeline.scheduler.timesteps  # type: ignore[reportOptionalMemberAccess]

        for i, t in enumerate(tqdm(timesteps, desc="Generating")):
            latent_model_input = torch.cat([latents] * 2)  # type: ignore[reportOptionalMemberAccess]
            latent_model_input = self.pipeline.scheduler.scale_model_input(  # type: ignore[reportOptionalMemberAccess]
                latent_model_input, t
            )

            try:
                down_block_res_samples, mid_block_res_sample = self.pipeline.controlnet(  # type: ignore[reportOptionalMemberAccess]
                    latent_model_input,
                    t,
                    encoder_hidden_states=prompt_embeds,
                    controlnet_cond=control_images_tensor,
                    conditioning_scale=controlnet_scales,
                    return_dict=False,
                )
            except TypeError:
                try:
                    down_block_res_samples, mid_block_res_sample = (
                        self.pipeline.controlnet(
                            latent_model_input,
                            t,
                            encoder_hidden_states=prompt_embeds,
                            image=control_images_tensor,
                            conditioning_scale=(
                                controlnet_scales[0] if controlnet_scales else 0.8
                            ),
                            return_dict=False,
                        )
                    )
                except TypeError:
                    down_block_res_samples, mid_block_res_sample = (
                        self.pipeline.controlnet(
                            latent_model_input,
                            t,
                            encoder_hidden_states=prompt_embeds,
                            image=control_images_tensor,
                            conditioning_scale=controlnet_scales,
                            return_dict=False,
                        )
                    )

            noise_pred = self.pipeline.unet(  # type: ignore[reportOptionalMemberAccess]
                latent_model_input,
                t,
                encoder_hidden_states=prompt_embeds,
                down_block_additional_residuals=down_block_res_samples,
                mid_block_additional_residual=mid_block_res_sample,
                return_dict=False,
            )[0]

            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + guidance_scale * (
                noise_pred_text - noise_pred_uncond
            )

            if self.reward_model is not None and i % 5 == 0 and i > num_steps * 0.2:
                with torch.no_grad():  # type: ignore[reportOptionalMemberAccess]
                    rewards = self.reward_model.compute_rewards(
                        latents=latents,
                        scene_graph=scene_graph,
                        physics_state=physics_state,
                        step=i,
                        total_steps=num_steps,
                        vae=self.pipeline.vae,
                        decode_every_n=5,
                    )
                    rewards_history.append({"step": i, "rewards": rewards})
                    overall_reward = rewards.get("overall", 0.5)
                    if overall_reward < 0.6:
                        noise_adjustment = (
                            torch.randn_like(noise_pred, device=noise_pred.device)  # type: ignore[reportOptionalMemberAccess]
                            * 0.15
                            * (1.0 - overall_reward)
                        )
                        noise_pred = noise_pred + noise_adjustment * reward_weight
                    if rewards.get("anatomy", 0.5) < 0.5:
                        anatomy_boost = (
                            torch.randn_like(noise_pred, device=noise_pred.device)  # type: ignore[reportOptionalMemberAccess]
                            * 0.1
                        )
                        noise_pred = noise_pred + anatomy_boost * reward_weight * 0.5

            latents = self.pipeline.scheduler.step(
                noise_pred, t, latents, return_dict=False
            )[0]

        latents = latents / self.pipeline.vae.config.scaling_factor
        image = self.pipeline.vae.decode(latents, return_dict=False)[0]
        image = self.pipeline.image_processor.postprocess(image, output_type="pil")[0]

        return {
            "image": image,
            "rewards_history": rewards_history,
            "metadata": {
                "method": "reward_guided",
                "steps": num_steps,
                "guidance_scale": guidance_scale,
                "reward_weight": reward_weight,
                "final_rewards": (
                    rewards_history[-1]["rewards"] if rewards_history else None
                ),
            },
        }
