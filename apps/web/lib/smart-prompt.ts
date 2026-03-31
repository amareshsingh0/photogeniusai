/**
 * Smart Prompt Enhancement
 * 
 * Automatically detects user intent and enhances prompts with optimal settings.
 * AI decides everything - style, mood, lighting, quality based on input.
 */

export type DetectedStyle = 
  | "PROFESSIONAL"
  | "CASUAL" 
  | "ARTISTIC"
  | "CINEMATIC"
  | "FASHION"
  | "ROMANTIC"
  | "COOL_EDGY";

export interface SmartPromptResult {
  enhancedPrompt: string;
  detectedStyle: DetectedStyle;
  mode: "REALISM" | "CREATIVE" | "ROMANTIC" | "CINEMATIC" | "FASHION" | "COOL_EDGY" | "ARTISTIC";
  qualityTier: "FAST" | "STANDARD" | "BALANCED" | "PREMIUM" | "ULTRA";
  mood: string;
  lighting: string;
  confidence: number;
}

const STYLE_KEYWORDS = {
  PROFESSIONAL: [
    'professional', 'business', 'headshot', 'linkedin', 'corporate',
    'office', 'formal', 'executive', 'interview', 'resume'
  ],
  CASUAL: [
    'casual', 'relaxed', 'everyday', 'comfortable', 'natural',
    'friendly', 'approachable', 'laid-back', 'informal'
  ],
  ARTISTIC: [
    'artistic', 'creative', 'abstract', 'expressive', 'unique',
    'avant-garde', 'experimental', 'imaginative', 'original'
  ],
  CINEMATIC: [
    'cinematic', 'movie', 'film', 'dramatic', 'epic', 'hero',
    'action', 'thriller', 'noir', 'hollywood', 'trailer'
  ],
  FASHION: [
    'fashion', 'model', 'runway', 'editorial', 'vogue', 'style',
    'trendy', 'chic', 'haute couture', 'magazine', 'glamour'
  ],
  ROMANTIC: [
    'romantic', 'wedding', 'couple', 'love', 'intimate', 'soft',
    'dreamy', 'elegant', 'bride', 'groom', 'engagement'
  ],
  COOL_EDGY: [
    'cool', 'edgy', 'urban', 'street', 'hip', 'modern', 'bold',
    'rebel', 'punk', 'grunge', 'alternative', 'contemporary'
  ],
};

const LIGHTING_PATTERNS = {
  'golden hour': ['sunset', 'sunrise', 'warm', 'golden', 'dusk', 'dawn'],
  'studio': ['professional', 'headshot', 'corporate', 'clean', 'formal'],
  'natural': ['outdoor', 'daylight', 'natural', 'window', 'ambient'],
  'dramatic': ['moody', 'dramatic', 'dark', 'shadow', 'contrast', 'noir'],
  'soft': ['soft', 'gentle', 'diffused', 'romantic', 'dreamy', 'tender'],
  'neon': ['neon', 'cyberpunk', 'urban', 'night', 'city', 'colorful'],
};

const MOOD_PATTERNS = {
  'confident': ['confident', 'powerful', 'strong', 'bold', 'assertive'],
  'friendly': ['friendly', 'warm', 'approachable', 'welcoming', 'kind'],
  'mysterious': ['mysterious', 'enigmatic', 'intriguing', 'dark', 'noir'],
  'joyful': ['happy', 'joyful', 'cheerful', 'bright', 'positive', 'smiling'],
  'serene': ['peaceful', 'calm', 'serene', 'tranquil', 'zen', 'relaxed'],
  'intense': ['intense', 'fierce', 'powerful', 'dramatic', 'passionate'],
};

/**
 * Analyze user prompt and automatically determine optimal generation settings
 */
export function analyzePrompt(userPrompt: string): SmartPromptResult {
  const prompt = userPrompt.toLowerCase().trim();
  
  // Detect style
  let bestStyle: DetectedStyle = "PROFESSIONAL";
  let maxScore = 0;
  
  for (const [style, keywords] of Object.entries(STYLE_KEYWORDS)) {
    const score = keywords.filter(kw => prompt.includes(kw)).length;
    if (score > maxScore) {
      maxScore = score;
      bestStyle = style as DetectedStyle;
    }
  }
  
  // Detect lighting
  let lighting = "studio lighting";
  for (const [light, keywords] of Object.entries(LIGHTING_PATTERNS)) {
    if (keywords.some(kw => prompt.includes(kw))) {
      lighting = light;
      break;
    }
  }
  
  // Detect mood
  let mood = "confident";
  for (const [moodType, keywords] of Object.entries(MOOD_PATTERNS)) {
    if (keywords.some(kw => prompt.includes(kw))) {
      mood = moodType;
      break;
    }
  }
  
  // Map style to generation mode
  const modeMap: Record<DetectedStyle, SmartPromptResult["mode"]> = {
    PROFESSIONAL: "REALISM",
    CASUAL: "REALISM",
    ARTISTIC: "ARTISTIC",
    CINEMATIC: "CINEMATIC",
    FASHION: "FASHION",
    ROMANTIC: "ROMANTIC",
    COOL_EDGY: "COOL_EDGY",
  };
  
  const mode = modeMap[bestStyle];
  
  // Determine quality tier based on style
  const qualityMap: Record<DetectedStyle, SmartPromptResult["qualityTier"]> = {
    PROFESSIONAL: "PREMIUM",
    FASHION: "ULTRA",
    ROMANTIC: "PREMIUM",
    CINEMATIC: "PREMIUM",
    ARTISTIC: "BALANCED",
    CASUAL: "STANDARD",
    COOL_EDGY: "BALANCED",
  };
  
  const qualityTier = qualityMap[bestStyle];
  
  // Enhance the prompt
  const enhancedPrompt = enhancePromptText(userPrompt, bestStyle, lighting, mood);
  
  return {
    enhancedPrompt,
    detectedStyle: bestStyle,
    mode,
    qualityTier,
    mood,
    lighting,
    confidence: maxScore > 0 ? Math.min(maxScore / 3, 1) : 0.5,
  };
}

/**
 * Enhance prompt with optimal keywords and instructions
 */
function enhancePromptText(
  original: string,
  style: DetectedStyle,
  lighting: string,
  mood: string
): string {
  // Don't over-enhance if prompt is already detailed
  if (original.split(' ').length > 15) {
    return original;
  }
  
  const qualityKeywords = [
    "RAW photo",
    "professional photography",
    "8k uhd",
    "highly detailed",
    "sharp focus",
    "photorealistic",
    "dslr",
    "masterpiece",
    "best quality"
  ];

  const styleEnhancements: Record<DetectedStyle, string[]> = {
    PROFESSIONAL: ["professional photography", "studio lighting", "clean sharp focus", "business attire", "confident pose", "professional setting"],
    CASUAL: ["natural lighting", "relaxed authentic pose", "genuine expression", "candid moment", "soft daylight"],
    ARTISTIC: ["creative composition", "unique artistic perspective", "professional color grading", "artistic expression", "gallery quality"],
    CINEMATIC: ["cinematic lighting", "dramatic composition", "film grain", "professional color grading", "depth of field", "anamorphic lens"],
    FASHION: ["editorial style photography", "high fashion", "runway quality", "vogue magazine style", "professional lighting", "trendy pose"],
    ROMANTIC: ["golden hour lighting", "dreamy soft atmosphere", "elegant pose", "intimate moment", "beautiful bokeh", "sunset warm tones", "professional romantic photography"],
    COOL_EDGY: ["urban setting", "bold contemporary style", "street photography", "modern aesthetic", "dramatic lighting"],
  };
  
  const parts = [];

  // Start with quality prefix for photorealism
  if (style === "PROFESSIONAL" || style === "ROMANTIC" || style === "FASHION") {
    parts.push("RAW photo");
  }

  // Add the original prompt
  parts.push(original);

  // Add style-specific enhancements (take more items for better quality)
  const enhancements = styleEnhancements[style];
  const missing = enhancements.filter(e => !original.toLowerCase().includes(e.split(' ')[0]));
  if (missing.length > 0) {
    parts.push(...missing.slice(0, 4)); // Take up to 4 enhancements
  }

  // Always add lighting for mood
  if (!original.toLowerCase().includes('light')) {
    parts.push(lighting);
  }

  // Add comprehensive quality keywords
  parts.push("highly detailed");
  parts.push("8k uhd");
  parts.push("professional photography");
  parts.push("sharp focus");
  parts.push("dslr quality");
  parts.push("photorealistic");
  parts.push("masterpiece");
  parts.push("best quality");

  return parts.join(', ');
}

/**
 * Get recommended settings for a generation mode
 */
export function getRecommendedSettings(mode: SmartPromptResult["mode"]) {
  const settings = {
    REALISM: {
      numCandidates: 4,
      seed: Math.floor(Math.random() * 1000000),
    },
    CREATIVE: {
      numCandidates: 6,
      seed: Math.floor(Math.random() * 1000000),
    },
    ROMANTIC: {
      numCandidates: 4,
      seed: Math.floor(Math.random() * 1000000),
    },
    CINEMATIC: {
      numCandidates: 4,
      seed: Math.floor(Math.random() * 1000000),
    },
    FASHION: {
      numCandidates: 6,
      seed: Math.floor(Math.random() * 1000000),
    },
    COOL_EDGY: {
      numCandidates: 6,
      seed: Math.floor(Math.random() * 1000000),
    },
    ARTISTIC: {
      numCandidates: 8,
      seed: Math.floor(Math.random() * 1000000),
    },
  };
  
  return settings[mode];
}
