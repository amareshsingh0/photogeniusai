# Services module

# Core exports (optional so package loads when Modal/text_renderer unavailable)
__all__ = []
try:
    from .text_renderer import TextRenderer, text_renderer

    __all__ += ["TextRenderer", "text_renderer"]
except Exception:
    TextRenderer = None  # type: ignore[misc, assignment]
    text_renderer = None  # type: ignore[misc, assignment]

try:
    from .refinement_engine import RefinementEngine, refinement_engine

    __all__ += ["RefinementEngine", "refinement_engine"]
except Exception:
    RefinementEngine = None  # type: ignore[misc, assignment]
    refinement_engine = None  # type: ignore[misc, assignment]

try:
    from .universal_prompt_enhancer import (
        PromptDomain,
        DomainClassifier,
        ClassificationResult,
        classify,
        classify_prompt_domain,
        get_domain,
        get_domain_with_confidence,
        get_default_classifier,
        classify_with_metrics,
        WowBooster,
        get_default_wow_booster,
        enhance_prompt_with_wow,
        EnhancedPrompt,
        UniversalPromptEnhancer,
        get_default_enhancer,
        enhance,
    )

    __all__ += [
        "PromptDomain",
        "DomainClassifier",
        "ClassificationResult",
        "classify",
        "classify_prompt_domain",
        "get_domain",
        "get_domain_with_confidence",
        "get_default_classifier",
        "classify_with_metrics",
        "WowBooster",
        "get_default_wow_booster",
        "enhance_prompt_with_wow",
        "EnhancedPrompt",
        "UniversalPromptEnhancer",
        "get_default_enhancer",
        "enhance",
    ]
except Exception:
    pass

try:
    from .universal_prompt_classifier import (
        ClassificationResult as ImageClassificationResult,
        UniversalPromptClassifier,
        get_default_classifier as get_smart_prompt_classifier,
    )
    from .smart_prompt_engine import SmartPromptEngine

    __all__ += [
        "ImageClassificationResult",
        "UniversalPromptClassifier",
        "get_smart_prompt_classifier",
        "SmartPromptEngine",
    ]
except Exception:
    pass

try:
    from .cinematic_prompts import (
        CinematicPromptEngine,
        get_default_cinematic_engine,
        enhance_cinematic,
    )

    __all__ += [
        "CinematicPromptEngine",
        "get_default_cinematic_engine",
        "enhance_cinematic",
    ]
except Exception:
    pass

try:
    from .prompt_enhancement_v3 import (
        scene_graph_to_positive,
        physics_to_material_descriptors,
        validation_failures_to_negative,
        build_negative_prompt_base,
        enhance_v3,
        enhance_v3_from_compiled,
        PromptEnhancementV3Result,
    )

    __all__ += [
        "scene_graph_to_positive",
        "physics_to_material_descriptors",
        "validation_failures_to_negative",
        "build_negative_prompt_base",
        "enhance_v3",
        "enhance_v3_from_compiled",
        "PromptEnhancementV3Result",
    ]
except Exception:
    pass

try:
    from .prompt_enhancement_v2 import PromptEnhancementV2

    __all__ += ["PromptEnhancementV2"]
except Exception:
    pass

try:
    from .dimension_manager import (
        DimensionManager,
        DimensionPlan,
        DimensionSpec,
        resolve_dimensions,
        compute_aspect_ratio,
        MIN_DIMENSION,
        MAX_DIMENSION,
        MAX_MEGAPIXELS,
    )

    __all__ += [
        "DimensionManager",
        "DimensionPlan",
        "DimensionSpec",
        "resolve_dimensions",
        "compute_aspect_ratio",
        "MIN_DIMENSION",
        "MAX_DIMENSION",
        "MAX_MEGAPIXELS",
    ]
except Exception:
    pass

try:
    from .image_modification_engine import (
        ModificationType,
        ModificationPlan,
        IntentParser,
        ModificationPlanner,
        ImageModificationExecutor,
        ImageModificationEngine,
    )

    __all__ += [
        "ModificationType",
        "ModificationPlan",
        "IntentParser",
        "ModificationPlanner",
        "ImageModificationExecutor",
        "ImageModificationEngine",
    ]
except Exception:
    pass

try:
    from .generation_config import (
        GenerationQuality,
        Scheduler,
        GenerationConfig,
        SmartConfigBuilder,
        get_default_builder,
        auto_build_config,
    )

    __all__ += [
        "GenerationQuality",
        "Scheduler",
        "GenerationConfig",
        "SmartConfigBuilder",
        "get_default_builder",
        "auto_build_config",
    ]
except Exception:
    pass

try:
    from .quality_assessment import (
        QualityVerdict,
        QualityScore,
        QualityAssessment,
        get_default_assessor,
        assess_quality,
    )

    __all__ += [
        "QualityVerdict",
        "QualityScore",
        "QualityAssessment",
        "get_default_assessor",
        "assess_quality",
    ]
except Exception:
    pass

try:
    from .unified_orchestrator import (
        OrchestrationResult,
        UnifiedOrchestrator,
        get_default_orchestrator,
        process,
    )

    __all__ += [
        "OrchestrationResult",
        "UnifiedOrchestrator",
        "get_default_orchestrator",
        "process",
    ]
except Exception:
    pass

try:
    from .orchestrator_aws import (
        generate_professional,
        generate_professional_with_fallback,
    )

    __all__ += ["generate_professional", "generate_professional_with_fallback"]
except Exception:
    pass

try:
    from .advanced_classifier import (
        VisualStyle,
        SurpriseLevel,
        LightingStyle,
        EmotionalTone,
        StyleAnalysis,
        AdvancedStyleClassifier,
        get_default_style_classifier,
        quick_style_analysis,
    )

    __all__ += [
        "VisualStyle",
        "SurpriseLevel",
        "LightingStyle",
        "EmotionalTone",
        "StyleAnalysis",
        "AdvancedStyleClassifier",
        "get_default_style_classifier",
        "quick_style_analysis",
    ]
except Exception:
    pass

try:
    from .user_preference_analyzer import (
        UserInteraction,
        UserPreferenceProfile,
        UserPreferenceAnalyzer,
        get_default_preference_analyzer,
    )

    __all__ += [
        "UserInteraction",
        "UserPreferenceProfile",
        "UserPreferenceAnalyzer",
        "get_default_preference_analyzer",
    ]
except Exception:
    pass

try:
    from .multi_variant_generator import (
        VariantType,
        VariantScore,
        PromptVariant,
        MultiVariantResult,
        MultiVariantGenerator,
        format_variant_display,
    )

    __all__ += [
        "VariantType",
        "VariantScore",
        "PromptVariant",
        "MultiVariantResult",
        "MultiVariantGenerator",
        "format_variant_display",
    ]
except Exception:
    pass

try:
    from .model_optimizer import (
        AIModel,
        ModelOptimizedPrompt,
        ModelOptimizer,
        optimize_variant_for_all_models,
    )

    __all__ += [
        "AIModel",
        "ModelOptimizedPrompt",
        "ModelOptimizer",
        "optimize_variant_for_all_models",
    ]
except Exception:
    pass

try:
    from .self_improvement_engine import SelfImprovementEngine

    __all__ += ["SelfImprovementEngine"]
except Exception:
    pass

try:
    from .enhanced_self_improvement_engine import (
        GenerationRecord,
        CategoryStats,
        LocalStorageAdapter,
        DynamoDBStorageAdapter,
        EnhancedSelfImprovementEngine,
    )

    __all__ += [
        "GenerationRecord",
        "CategoryStats",
        "LocalStorageAdapter",
        "DynamoDBStorageAdapter",
        "EnhancedSelfImprovementEngine",
    ]
except Exception:
    pass

try:
    from .finish import FluxFinish, ReplicateFinish, FinishResult

    __all__ += ["FluxFinish", "ReplicateFinish", "FinishResult"]
except Exception:
    pass

# Deterministic pipeline (Scene Graph, Camera/Occlusion, Physics, Tri-Model, Refinement)
try:
    from .scene_graph_compiler import (
        EntityNode,
        RelationEdge,
        HardConstraint,
        SceneGraphCompiler,
    )

    __all__ += ["EntityNode", "RelationEdge", "HardConstraint", "SceneGraphCompiler"]
except Exception:
    pass

try:
    from .camera_occlusion_solver import (
        CameraConfig,
        OcclusionSafeLayout,
        CameraOcclusionSolver,
    )

    __all__ += ["CameraConfig", "OcclusionSafeLayout", "CameraOcclusionSolver"]
except Exception:
    pass

try:
    from .constraint_solver import ConstraintSolver, SolverResult

    __all__ += ["ConstraintSolver", "SolverResult"]
except Exception:
    pass

try:
    from .physics_micro_sim import (
        MaterialState,
        LightingState,
        PhysicsSimResult,
        PhysicsMicroSim,
    )

    __all__ += ["MaterialState", "LightingState", "PhysicsSimResult", "PhysicsMicroSim"]
except Exception:
    pass

try:
    from .physics_micro_simulation import (
        MaterialState as MaterialStateSim,
        EnvironmentalCondition,
        PhysicsMicroSimulation,
    )

    __all__ += ["MaterialStateSim", "EnvironmentalCondition", "PhysicsMicroSimulation"]
except Exception:
    pass

try:
    from .tri_model_validator import (
        ValidationResult,
        TriModelConsensus,
        TriModelValidator,
        AnatomyValidationResult,
        AnatomyIssueLocalizer,
    )

    __all__ += [
        "ValidationResult",
        "TriModelConsensus",
        "TriModelValidator",
        "AnatomyValidationResult",
        "AnatomyIssueLocalizer",
    ]
except Exception:
    pass

try:
    from .validation_integration import ValidationIntegration

    __all__ += ["ValidationIntegration"]
except Exception:
    pass

try:
    from .issue_analyzer import IssueAnalyzer, IssueFix

    __all__ += ["IssueAnalyzer", "IssueFix"]
except Exception:
    pass

try:
    from .iterative_refinement_engine import (
        IterativeRefinementEngine,
        RefinementIteration,
    )

    __all__ += ["IterativeRefinementEngine", "RefinementIteration"]
except Exception:
    pass

try:
    from .experience_memory import (
        ExperienceMemory,
        GenerationExperience,
        create_experience_id,
    )

    __all__ += ["ExperienceMemory", "GenerationExperience", "create_experience_id"]
except Exception:
    pass

try:
    from .preference_learning import PreferenceLearning, PreferencePair

    __all__ += ["PreferenceLearning", "PreferencePair"]
except Exception:
    pass

try:
    from .self_improvement_engine import SelfImprovementEngine

    __all__ += ["SelfImprovementEngine"]
except Exception:
    pass

try:
    from .iterative_refinement import (
        RefinementStep,
        RefinementResult,
        build_refinement_deltas,
        apply_refinement_to_prompt,
    )

    __all__ += [
        "RefinementStep",
        "RefinementResult",
        "build_refinement_deltas",
        "apply_refinement_to_prompt",
    ]
except Exception:
    pass

try:
    from .guided_diffusion_controlnet import (
        RewardModel,
        GuidedDiffusionControlNet,
    )

    __all__ += ["RewardModel", "GuidedDiffusionControlNet"]
except Exception:
    pass

try:
    from .control_image_generator import ControlImageGenerator

    __all__ += ["ControlImageGenerator"]
except Exception:
    pass

try:
    from .guided_diffusion_pipeline import GuidedDiffusionPipeline

    __all__ += ["GuidedDiffusionPipeline"]
except Exception:
    pass

try:
    from .reward_aggregator import (
        RewardAggregator,
        AggregatedReward,
        FailureMemory,
        ppo_fine_tuning_step,
    )

    __all__ += [
        "RewardAggregator",
        "AggregatedReward",
        "FailureMemory",
        "ppo_fine_tuning_step",
    ]
except Exception:
    pass

try:
    from .pattern_matcher import PatternMatcher, PatternMatch
    from .failure_memory_system import (
        FailureMemorySystem,
        FailureEntry,
        DEFAULT_PATTERNS,
    )

    __all__ += [
        "PatternMatcher",
        "PatternMatch",
        "FailureMemorySystem",
        "FailureEntry",
        "DEFAULT_PATTERNS",
    ]
except Exception:
    pass

try:
    from .iterative_refinement_v2 import (
        RefinementStepV2,
        RefinementResultV2,
        IssueRegion,
        InpaintRequest,
        localize_issues_from_consensus,
        build_refinement_deltas_v2,
        refine_with_inpainting,
        IterativeRefinementV2,
    )

    __all__ += [
        "RefinementStepV2",
        "RefinementResultV2",
        "IssueRegion",
        "InpaintRequest",
        "localize_issues_from_consensus",
        "build_refinement_deltas_v2",
        "refine_with_inpainting",
        "IterativeRefinementV2",
    ]
except Exception:
    pass

try:
    from .auto_validation_pipeline import AutoValidationPipeline

    __all__ += ["AutoValidationPipeline"]
except Exception:
    pass

try:
    from .typography_engine import (
        TypographyEngine,
        TextPlacement,
        render_text_placement,
        FONT_STYLE_FILES,
        FONT_SEARCH_PATHS,
    )

    __all__ += [
        "TypographyEngine",
        "TextPlacement",
        "render_text_placement",
        "FONT_STYLE_FILES",
        "FONT_SEARCH_PATHS",
    ]
except Exception:
    pass

try:
    from .math_renderer import MathRenderer

    __all__ += ["MathRenderer"]
except Exception:
    pass

try:
    from .math_diagram_renderer import (
        MathDiagramRenderer,
        FormulaPlacement,
        ChartSpec,
        DiagramKind,
        LightingOptions,
        ValidationResult,
        validate_formula_latex,
        validate_formula_sympy_expr,
        check_formula_equivalence,
        render_latex_to_png,
        overlay_math_on_image,
        get_default_math_diagram_renderer,
    )

    __all__ += [
        "MathDiagramRenderer",
        "FormulaPlacement",
        "ChartSpec",
        "DiagramKind",
        "LightingOptions",
        "ValidationResult",
        "validate_formula_latex",
        "validate_formula_sympy_expr",
        "check_formula_equivalence",
        "render_latex_to_png",
        "overlay_math_on_image",
        "get_default_math_diagram_renderer",
    ]
except Exception:
    pass

try:
    from .deterministic_pipeline import (
        DeterministicPipelineResult,
        DeterministicPipeline,
        create_pipeline,
        typography_post_process,
        math_diagram_post_process,
    )

    __all__ += [
        "DeterministicPipelineResult",
        "DeterministicPipeline",
        "create_pipeline",
        "typography_post_process",
        "math_diagram_post_process",
    ]
except Exception:
    pass
