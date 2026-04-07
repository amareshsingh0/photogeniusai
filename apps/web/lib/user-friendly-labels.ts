/**
 * User-Friendly Labels Mapper
 *
 * Hides backend technology names from frontend users.
 * Philosophy: Show FEATURES, not TECHNOLOGY.
 *
 * User sees: "Premium AI Engine"
 * We know: "flux_2_pro"
 */

// ══════════════════════════════════════════════════════════════════════════════
// AI Model Names → User-Friendly Labels
// ══════════════════════════════════════════════════════════════════════════════

export const MODEL_TO_USER_FRIENDLY: Record<string, string> = {
  // Flux Models
  "flux_2_pro": "Premium AI Engine",
  "flux_2_dev": "Advanced AI Engine",
  "flux_2_max": "Ultra AI Engine",
  "flux_schnell": "Fast AI Engine",
  "flux-pro": "Premium AI Engine",
  "flux-dev": "Advanced AI Engine",
  "flux.1-schnell": "Fast AI Engine",

  // Ideogram
  "ideogram_quality": "Typography Specialist",
  "ideogram_v3": "Typography Specialist",
  "ideogram": "Typography Specialist",

  // Recraft
  "recraft_v4": "Vector Specialist",
  "recraft": "Vector Graphics Engine",

  // Hunyuan
  "hunyuan_image": "Asian Aesthetic Specialist",
  "hunyuan": "Cultural AI Engine",

  // LLMs (Prompt Engineering)
  "gemini-2.5-flash": "Creative Intelligence",
  "gemini-2.0-flash-exp": "Creative Intelligence",
  "gemini": "Creative Intelligence",
  "claude-sonnet-4.5": "Creative Intelligence",
  "claude": "Creative Intelligence",

  // Legacy/Fallback
  "stable-diffusion": "AI Engine",
  "sdxl": "AI Engine",
}

// ══════════════════════════════════════════════════════════════════════════════
// Provider Names → User-Friendly Labels
// ══════════════════════════════════════════════════════════════════════════════

export const PROVIDER_TO_USER_FRIENDLY: Record<string, string> = {
  "fal.ai": "Cloud Processing",
  "fal": "Cloud Processing",
  "replicate": "Cloud Processing",
  "fireworks": "Cloud Processing",
  "sagemaker": "Dedicated GPU",
  "aws": "Cloud Infrastructure",
}

// ══════════════════════════════════════════════════════════════════════════════
// Stage/Event Names → User-Friendly Labels
// ══════════════════════════════════════════════════════════════════════════════

export const STAGE_TO_USER_FRIENDLY: Record<string, string> = {
  // SSE Event Types
  "intent_ready": "Analyzing your request",
  "brief_ready": "Preparing creative brief",
  "generating": "Creating your visual",
  "compositing": "Adding final touches",
  "quality_checking": "Quality assurance",
  "quality_scored": "Quality verified",
  "revision_triggered": "Refining details",
  "final_ready": "Complete",

  // Pipeline Stages
  "triage": "Understanding your needs",
  "brand_intel": "Analyzing brand identity",
  "creative_direction": "Crafting creative concept",
  "copy_writing": "Writing compelling copy",
  "layout_planning": "Designing layout",
  "image_generation": "Generating visuals",
  "post_processing": "Enhancing quality",
  "quality_gate": "Final quality check",
}

// ══════════════════════════════════════════════════════════════════════════════
// Quality Tier → User-Friendly Labels
// ══════════════════════════════════════════════════════════════════════════════

export const TIER_TO_USER_FRIENDLY: Record<string, string> = {
  "fast": "Quick Draft",
  "standard": "Standard Quality",
  "premium": "Premium Quality",
  "ultra": "Ultra Premium",
}

export const TIER_TO_ICON: Record<string, string> = {
  "fast": "⚡",
  "standard": "✨",
  "premium": "💎",
  "ultra": "👑",
}

export const TIER_TO_COLOR: Record<string, string> = {
  "fast": "text-blue-600",
  "standard": "text-purple-600",
  "premium": "text-amber-600",
  "ultra": "text-pink-600",
}

// ══════════════════════════════════════════════════════════════════════════════
// Platform → User-Friendly Labels
// ══════════════════════════════════════════════════════════════════════════════

export const PLATFORM_TO_USER_FRIENDLY: Record<string, string> = {
  // Instagram
  "instagram_feed": "Instagram Feed",
  "instagram_story": "Instagram Story",
  "instagram_reel": "Instagram Reel",
  "instagram": "Instagram",

  // Facebook
  "facebook_feed": "Facebook Feed",
  "facebook_story": "Facebook Story",
  "facebook": "Facebook",

  // YouTube
  "youtube_thumbnail": "YouTube Thumbnail",
  "youtube_cover": "YouTube Cover",
  "youtube": "YouTube",

  // TikTok
  "tiktok": "TikTok",

  // LinkedIn
  "linkedin_post": "LinkedIn Post",
  "linkedin_cover": "LinkedIn Cover",
  "linkedin": "LinkedIn",

  // Twitter/X
  "twitter_post": "Twitter/X Post",
  "twitter": "Twitter/X",

  // Physical/Print
  "billboard_landscape": "Billboard",
  "billboard_portrait": "Billboard (Vertical)",
  "print_poster_a4": "Print Poster",
  "print_flyer": "Print Flyer",

  // Digital
  "web_banner": "Web Banner",
  "email_header": "Email Header",
  "email": "Email",

  // General
  "general": "General",
}

export const PLATFORM_TO_ICON: Record<string, string> = {
  "instagram_feed": "📱",
  "instagram_story": "📱",
  "instagram_reel": "🎥",
  "facebook_feed": "👥",
  "youtube_thumbnail": "▶️",
  "tiktok": "🎵",
  "linkedin_post": "💼",
  "twitter_post": "🐦",
  "billboard_landscape": "🏙️",
  "print_poster_a4": "🖨️",
  "web_banner": "🌐",
  "email_header": "✉️",
  "general": "🎨",
}

// ══════════════════════════════════════════════════════════════════════════════
// Generation Profile → User-Friendly Labels
// ══════════════════════════════════════════════════════════════════════════════

export const GENERATION_TO_USER_FRIENDLY: Record<string, string> = {
  "gen_z_india": "Gen Z Style",
  "millennial_parent": "Family-Friendly",
  "premium_buyer": "Premium Audience",
  "achiever_urban": "Achiever Style",
  "mass_market_india": "Mass Appeal",
}

export const GENERATION_TO_ICON: Record<string, string> = {
  "gen_z_india": "🔥",
  "millennial_parent": "👨‍👩‍👧",
  "premium_buyer": "💎",
  "achiever_urban": "🚀",
  "mass_market_india": "🇮🇳",
}

export const GENERATION_TO_COLOR: Record<string, string> = {
  "gen_z_india": "bg-orange-50 text-orange-700",
  "millennial_parent": "bg-blue-50 text-blue-700",
  "premium_buyer": "bg-purple-50 text-purple-700",
  "achiever_urban": "bg-green-50 text-green-700",
  "mass_market_india": "bg-indigo-50 text-indigo-700",
}

// ══════════════════════════════════════════════════════════════════════════════
// Aesthetic Code → User-Friendly Labels
// ══════════════════════════════════════════════════════════════════════════════

export const AESTHETIC_TO_USER_FRIENDLY: Record<string, string> = {
  "brutalist_luxury": "Brutalist Luxury",
  "ai_native": "AI Native",
  "dopamine_maximalism": "Dopamine Maximalism",
  "vintage_y2k": "Y2K Vintage",
  "cottagecore_soft": "Cottagecore Soft",
  "dark_academia": "Dark Academia",
  "clean_minimal": "Clean Minimal",
  "neon_cyberpunk": "Neon Cyberpunk",
  "organic_earth": "Organic Earth",
}

// ══════════════════════════════════════════════════════════════════════════════
// Main Helper Functions
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Convert any backend technology term to user-friendly label
 */
export function friendlyLabel(techTerm: string | undefined | null): string {
  if (!techTerm) return "AI Engine"

  const term = techTerm.toLowerCase().trim()

  // Try all mappers in order
  return (
    MODEL_TO_USER_FRIENDLY[term] ||
    PROVIDER_TO_USER_FRIENDLY[term] ||
    STAGE_TO_USER_FRIENDLY[term] ||
    TIER_TO_USER_FRIENDLY[term] ||
    PLATFORM_TO_USER_FRIENDLY[term] ||
    GENERATION_TO_USER_FRIENDLY[term] ||
    AESTHETIC_TO_USER_FRIENDLY[term] ||
    techTerm // Fallback to original if no mapping found
  )
}

/**
 * Get user-friendly model name
 */
export function friendlyModel(modelId: string | undefined | null): string {
  if (!modelId) return "AI Engine"
  return MODEL_TO_USER_FRIENDLY[modelId.toLowerCase()] || "AI Engine"
}

/**
 * Get user-friendly stage name
 */
export function friendlyStage(stage: string | undefined | null): string {
  if (!stage) return "Processing"
  return STAGE_TO_USER_FRIENDLY[stage.toLowerCase()] || stage
}

/**
 * Get user-friendly tier name with icon
 */
export function friendlyTier(tier: string | undefined | null): {
  label: string
  icon: string
  color: string
} {
  const t = tier?.toLowerCase() || "standard"
  return {
    label: TIER_TO_USER_FRIENDLY[t] || "Standard Quality",
    icon: TIER_TO_ICON[t] || "✨",
    color: TIER_TO_COLOR[t] || "text-purple-600",
  }
}

/**
 * Get user-friendly platform name with icon
 */
export function friendlyPlatform(platform: string | undefined | null): {
  label: string
  icon: string
} {
  const p = platform?.toLowerCase() || "general"
  return {
    label: PLATFORM_TO_USER_FRIENDLY[p] || "General",
    icon: PLATFORM_TO_ICON[p] || "🎨",
  }
}

/**
 * Get user-friendly generation profile with icon and color
 */
export function friendlyGeneration(generation: string | undefined | null): {
  label: string
  icon: string
  color: string
} {
  const g = generation?.toLowerCase() || "mass_market_india"
  return {
    label: GENERATION_TO_USER_FRIENDLY[g] || "Mass Appeal",
    icon: GENERATION_TO_ICON[g] || "🇮🇳",
    color: GENERATION_TO_COLOR[g] || "bg-indigo-50 text-indigo-700",
  }
}

/**
 * Get user-friendly aesthetic name
 */
export function friendlyAesthetic(aesthetic: string | undefined | null): string {
  if (!aesthetic) return "Modern"
  return AESTHETIC_TO_USER_FRIENDLY[aesthetic.toLowerCase()] || aesthetic
}

/**
 * Format status message by replacing all backend terms
 */
export function friendlyStatusMessage(message: string): string {
  let friendly = message

  // Replace model names
  Object.entries(MODEL_TO_USER_FRIENDLY).forEach(([tech, user]) => {
    const regex = new RegExp(tech, "gi")
    friendly = friendly.replace(regex, user)
  })

  // Replace provider names
  Object.entries(PROVIDER_TO_USER_FRIENDLY).forEach(([tech, user]) => {
    const regex = new RegExp(tech, "gi")
    friendly = friendly.replace(regex, user)
  })

  // Common replacements
  friendly = friendly
    .replace(/processing with/gi, "Creating with")
    .replace(/using/gi, "with")
    .replace(/flux pro/gi, "Premium AI Engine")
    .replace(/gemini/gi, "Creative Intelligence")

  return friendly
}

// ══════════════════════════════════════════════════════════════════════════════
// Type Exports
// ══════════════════════════════════════════════════════════════════════════════

export type ModelId = keyof typeof MODEL_TO_USER_FRIENDLY
export type ProviderId = keyof typeof PROVIDER_TO_USER_FRIENDLY
export type StageId = keyof typeof STAGE_TO_USER_FRIENDLY
export type TierId = keyof typeof TIER_TO_USER_FRIENDLY
export type PlatformId = keyof typeof PLATFORM_TO_USER_FRIENDLY
export type GenerationId = keyof typeof GENERATION_TO_USER_FRIENDLY
export type AestheticId = keyof typeof AESTHETIC_TO_USER_FRIENDLY
