"use client"

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react"
import dynamic from "next/dynamic"
import { useRouter } from "next/navigation"

const EditImageModal      = dynamic(
  () => import("@/components/edit-image-modal").catch(err => {
    console.error("[EditImageModal] chunk load failed:", err)
    return { default: () => (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
        <div className="bg-red-950 border border-red-500 rounded-xl p-6 max-w-md text-white">
          <p className="font-semibold mb-2">Editor failed to load</p>
          <p className="text-sm text-red-200">Chunk load error — please hard refresh (Ctrl+Shift+R).</p>
        </div>
      </div>
    ) }
  }),
  {
    ssr: false,
    loading: () => (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
        <div className="text-white text-sm animate-pulse">Loading editor…</div>
      </div>
    ),
  }
)
const LogoOverlayModal    = dynamic(() => import("@/components/logo-overlay-modal"),    { ssr: false })
const PosterPackModal     = dynamic(() => import("@/components/poster-pack-modal").then(m => ({ default: m.PosterPackModal })),     { ssr: false })
const GenerationControlsV2 = dynamic(() => import("@/components/generation-controls-v2").then(m => ({ default: m.GenerationControlsV2 })), { ssr: false })
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import ImageRating from "@/components/feedback/image-rating"
import {
  Sparkles,
  Loader2,
  Download,
  Globe,
  X as XIcon,
  RotateCcw,
  AlertCircle,
  Plus,
  Mic,
  MicOff,
  Zap,
  ImageIcon,
  Palette,
  ChevronDown,
  ChevronUp,
  Film,
  Camera,
  PenTool,
  Wand2,
  Mountain,
  Palette as ArtIcon,
  X,
  Clock,
  Star,
  Eye,
  EyeOff,
  Copy,
  Check,
  RefreshCw,
  SlidersHorizontal,
  Megaphone,
  Scissors,
  Upload,
  Building2,
  Utensils,
  Leaf,
  Cpu,
  Pen,
  FlaskConical,
  Triangle,
  Lightbulb,
  ThumbsUp,
  ThumbsDown,
  Package,
  PenSquare,
} from "lucide-react"
import Image from "next/image"
import { cn } from "@/lib/utils"
import { useToast } from "@/components/ui/use-toast"
import { ToastAction } from "@/components/ui/toast"

interface DetectedSettings {
  style: string
  mood: string
  lighting: string
  quality: string
  category: string
}

interface CreativeOSData {
  intent?: { creative_type: string; platform: string; goal: string; is_ad: boolean }
  jury?: {
    overall_score: number; grade: string; readability: number; balance: number
    color_harmony: number; ocr_quality: number; composition: number
    wcag_contrast: number; brand_score: number; passed: boolean; issues: string[]
  }
  brand?: { compliant: boolean; score: number; issues: string[] }
  variants?: {
    count: number; primary: string; strategy: string
    options: { id: string; label: string; type: string; template: string; style: string; colors: string[]; text_position: string }[]
  }
  ctr?: { engagement_score: number; confidence: number; suggestions: string[] }
}

interface GenerationResult {
  success: boolean
  image_url?: string
  preview_url?: string
  detected_settings?: DetectedSettings
  enhanced_prompt?: string
  error?: string
  demo_mode?: boolean
  message?: string
  generationId?: string
  quality_score?: number
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  quality_gate?: any         // CREA quality gate result { total, grade, critique, auto_rerun }
  total_time?: number
  model_used?: string
  creative_os?: CreativeOSData
  // Poster / ad fields (Sprint 4)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ad_copy?: any
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  poster_design?: any
  hero_url?: string          // raw hero before compositor — for recompose/pack
  capability_bucket?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  design_brief?: any         // full DesignBrief from agent chain — for canvas editor
  image_url_experimental?: string  // Phase 6: dual variant experimental image
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  motion_hints?: any         // Motion Designer hints for stories/reels
  learning_logged?: boolean  // Learning Engine logged this generation
}

// SSE-driven stage labels — updated by real backend events
const SSE_STAGES: Record<string, { label: string; sub: string; pct: number }> = {
  intent:          { label: "Reading your vision",     sub: "Detecting intent & creative type",    pct: 10 },
  brief:           { label: "Creative brief ready",    sub: "Photographer mindset applied",        pct: 35 },
  generating:      { label: "Rendering with AI",       sub: "AI processing your image",            pct: 55 },
  compositing:     { label: "Compositing design",      sub: "Applying text layout & brand style",  pct: 80 },
  quality_checking:{ label: "AI quality review",       sub: "Scoring against Creative Bible",      pct: 88 },
  done:            { label: "Finishing touches",       sub: "Optimizing quality",                  pct: 95 },
}
// Fallback array for dot indicator (4 stages)
const GENERATION_STAGES = [
  { label: "Reading your vision",   sub: "Detecting intent & creative type", pct: 10 },
  { label: "Creative brief ready",  sub: "Photographer mindset applied",     pct: 35 },
  { label: "Rendering with AI",     sub: "AI processing your image",         pct: 55 },
  { label: "Finishing touches",     sub: "Optimizing quality",               pct: 95 },
]

interface DimensionPreset {
  label: string
  width: number
  height: number
  aspect: string
}

const DIMENSION_PRESETS: DimensionPreset[] = [
  { label: "Auto",       width: 1024, height: 1024, aspect: "auto" },
  { label: "Square",     width: 1024, height: 1024, aspect: "1:1"  },
  { label: "Portrait",   width: 768,  height: 1024, aspect: "3:4"  },
  { label: "Landscape",  width: 1024, height: 768,  aspect: "4:3"  },
  { label: "Widescreen", width: 1344, height: 768,  aspect: "16:9" },
  { label: "Story",      width: 768,  height: 1344, aspect: "9:16" },
  { label: "Ultrawide",  width: 1536, height: 640,  aspect: "21:9" },
]

// Valid pixel sizes per preset (long-side reference; auto/square = both sides)
const PRESET_SIZES: Record<string, number[]> = {
  "Auto":       [512, 768, 1024, 1280],
  "Square":     [512, 768, 1024, 1280, 1536],
  "Portrait":   [768, 1024, 1280],
  "Landscape":  [768, 1024, 1280],
  "Widescreen": [1024, 1344],
  "Story":      [768, 1344],
  "Ultrawide":  [1536],
}
const PRESET_DEFAULT_SIZE: Record<string, number> = {
  "Auto": 1024, "Square": 1024, "Portrait": 1024,
  "Landscape": 1024, "Widescreen": 1344, "Story": 1344, "Ultrawide": 1536,
}
// Given a preset + chosen long-side size, return 64-aligned W×H
function calcDims(preset: DimensionPreset, size: number): { width: number; height: number } {
  if (preset.aspect === "auto" || preset.aspect === "1:1") {
    const s = Math.round(size / 64) * 64
    return { width: s, height: s }
  }
  const [pw, ph] = preset.aspect.split(":").map(Number)
  const ratio = pw / ph
  if (ratio >= 1) {
    const w = Math.round(size / 64) * 64
    const h = Math.round(size / ratio / 64) * 64
    return { width: w, height: h }
  } else {
    const h = Math.round(size / 64) * 64
    const w = Math.round(size * ratio / 64) * 64
    return { width: w, height: h }
  }
}

const QUALITY_OPTIONS = [
  { value: "1k", label: "1K", hint: "~10s", note: "1024px render" },
  { value: "2k", label: "2K", hint: "~30s", note: "2048px render" },
  { value: "4k", label: "4K", hint: "~60s", note: "4096px render" },
] as const

// Style filmstrip — portrait-ratio cards with rich gradient fills
// Single unified style filmstrip — all styles, one row, all with icons
const STYLE_ALL: { id: string; icon: React.ElementType; label: string; from: string; to: string }[] = [
  { id: "Auto",         icon: Wand2,        label: "Auto",      from: "#4c1d95", to: "#1e40af" },
  { id: "Realistic",    icon: Camera,       label: "Realistic", from: "#78350f", to: "#7f1d1d" },
  { id: "Cinematic",    icon: Film,         label: "Cinematic", from: "#0c4a6e", to: "#1e1b4b" },
  { id: "Anime",        icon: PenTool,      label: "Anime",     from: "#831843", to: "#4c1d95" },
  { id: "Fantasy",      icon: Mountain,     label: "Fantasy",   from: "#064e3b", to: "#0e7490" },
  { id: "Art",          icon: ArtIcon,      label: "Art",       from: "#7c2d12", to: "#9d174d" },
  { id: "Digital Art",  icon: Sparkles,     label: "Digital",   from: "#1e3a5f", to: "#312e81" },
  { id: "Product",      icon: ImageIcon,    label: "Product",   from: "#1c1917", to: "#27272a" },
  { id: "Architecture", icon: Building2,    label: "Architect.",from: "#0f172a", to: "#1e293b" },
  { id: "Food",         icon: Utensils,     label: "Food",      from: "#431407", to: "#7c2d12" },
  { id: "Nature",       icon: Leaf,         label: "Nature",    from: "#052e16", to: "#064e3b" },
  { id: "Cyberpunk",    icon: Cpu,          label: "Cyberpunk", from: "#030712", to: "#083344" },
  { id: "Vintage",      icon: Clock,        label: "Vintage",   from: "#292524", to: "#44403c" },
  { id: "Design",       icon: Pen,          label: "Design",    from: "#1e1b4b", to: "#312e81" },
  { id: "Scientific",   icon: FlaskConical, label: "Science",   from: "#0c0a09", to: "#134e4a" },
  { id: "Geometric",    icon: Triangle,     label: "Geometric", from: "#0f172a", to: "#1e3a5f" },
  { id: "Creative",     icon: Lightbulb,    label: "Creative",  from: "#450a0a", to: "#7f1d1d" },
]
// Quality color coding
const QUALITY_COLORS: Record<string, string> = {
  "1k": "#3b82f6", "2k": "#8b5cf6", "4k": "#d97706"
}

const LEGACY_QUALITY_MAP: Record<string, string> = {
  fast: "1k",
  standard: "2k",
  balanced: "2k",
  premium: "2k",
  quality: "2k",
  ultra: "4k",
}

function normalizeQualityTier(value?: string): string {
  const normalized = value?.trim().toLowerCase() ?? ""
  if (normalized in QUALITY_COLORS) return normalized
  return LEGACY_QUALITY_MAP[normalized] ?? "1k"
}

function getQualityMeta(value?: string) {
  const normalized = normalizeQualityTier(value)
  return QUALITY_OPTIONS.find((option) => option.value === normalized) ?? QUALITY_OPTIONS[0]
}

// P6: Try These — horizontal scroll cards with gradient + label
const SUGGESTION_CARDS = [
  { id: "cyberpunk", emoji: "🌆", label: "Cyberpunk City", prompt: "Cyberpunk city at night, neon lights, rain reflections, cinematic" },
  { id: "headshot", emoji: "📸", label: "Studio Headshot", prompt: "Professional headshot with soft studio lighting" },
  { id: "golden", emoji: "🌅", label: "Golden Hour", prompt: "Cinematic portrait at golden hour, warm light" },
  { id: "editorial", emoji: "👗", label: "Fashion Editorial", prompt: "Fashion editorial in urban setting, dramatic shadows" },
  { id: "nature", emoji: "🌿", label: "Nature Scene", prompt: "Serene nature landscape, soft morning light, peaceful" },
  { id: "artistic", emoji: "🎨", label: "Artistic Photo", prompt: "Artistic photo with dramatic shadows and moody lighting" },
]

const POSTER_SUGGESTION_CARDS = [
  { id: "sale", emoji: "🏷️", label: "Sale Poster", prompt: "summer sale poster with text 'SUMMER SALE' and '50% OFF'" },
  { id: "event", emoji: "🎉", label: "Event Flyer", prompt: "music festival poster with text 'BEAT FEST 2026' and 'March 15'" },
  { id: "food", emoji: "🍕", label: "Food Ad", prompt: "restaurant promotion poster with text 'GRAND OPENING' and 'Free Dessert'" },
  { id: "fitness", emoji: "💪", label: "Fitness Ad", prompt: "gym poster with text 'TRANSFORM' and 'Join Now'" },
  { id: "fashion", emoji: "👠", label: "Fashion Ad", prompt: "luxury fashion poster with text 'NEW COLLECTION' and 'Spring 2026'" },
  { id: "tech", emoji: "🚀", label: "Tech Launch", prompt: "futuristic tech product launch poster with text 'THE FUTURE IS HERE'" },
]

// Creation modes
type CreationMode = "image" | "poster"

// P2: Reactive tint — keyword -> subtle bg tint (patterns hoisted to module level)
const _TINT_PATTERNS: [RegExp, string][] = [
  [/\b(cyberpunk|neon|night|sci-fi)\b/,          "rgba(0,255,255,0.04)"],
  [/\b(nature|forest|green|grass|tree)\b/,        "rgba(34,197,94,0.05)"],
  [/\b(sunset|golden|warm|fire)\b/,               "rgba(251,146,60,0.05)"],
  [/\b(portrait|headshot|face|person)\b/,         "rgba(168,85,247,0.04)"],
]
function getPromptTint(prompt: string): string {
  const p = prompt.toLowerCase()
  for (const [re, color] of _TINT_PATTERNS) if (re.test(p)) return color
  return "transparent"
}

// P8: Portrait-like prompt detection
const PORTRAIT_KEYWORDS = /portrait|headshot|face|person|selfie|bust|close.?up/i
function isPortraitLike(prompt: string): boolean {
  return PORTRAIT_KEYWORDS.test(prompt.trim())
}

// Auto aspect ratio — detect optimal dimensions from prompt content
function smartAutoDims(prompt: string): { width: number; height: number; label: string } {
  const p = prompt.toLowerCase()
  // Story / vertical (9:16) — Instagram stories, TikTok, reels, phone wallpaper
  if (/\b(story|stories|reel|tiktok|short|phone wallpaper|vertical video|instagram story)\b/.test(p))
    return { width: 768, height: 1344, label: "Story 9:16" }
  // Portrait (3:4) — headshots, fashion, single person, profile photo
  if (/\b(portrait|headshot|selfie|profile photo|face|close.?up|bust shot|half body|full body|person standing|fashion model|editorial)\b/.test(p))
    return { width: 768, height: 1024, label: "Portrait 3:4" }
  // Widescreen (16:9) — landscapes, cinematic, YouTube thumbnail, banner, panorama
  if (/\b(landscape|panorama|cinematic|wide.?angle|youtube|thumbnail|banner|billboard|cover photo|desktop wallpaper|city.?scape|horizon|mountain range)\b/.test(p))
    return { width: 1344, height: 768, label: "Widescreen 16:9" }
  // Landscape (4:3) — general wide scenes, group photos, product in context
  if (/\b(wide|scene|group|outdoor|interior|room|architecture|building|street|product shot)\b/.test(p))
    return { width: 1024, height: 768, label: "Landscape 4:3" }
  // Poster / ad / flyer — tall portrait 4:5 format
  if (/\b(poster|flyer|ad\b|advertisement|instagram post|facebook post|saas|product launch|launch|announcement|sale|promo|marketing|campaign|brand|creative)\b/.test(p))
    return { width: 1024, height: 1280, label: "Portrait 4:5" }
  // Default: square
  return { width: 1024, height: 1024, label: "Square 1:1" }
}

const SESSION_KEY = "pg_last_result"

export default function GeneratePage() {
  const router = useRouter()
  const [prompt, setPrompt] = useState("")
  const [userPrompt, setUserPrompt] = useState<string>("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [multiResults, setMultiResults] = useState<GenerationResult[]>([]) // For admin testing mode
  const [isAdmin, setIsAdmin] = useState(false) // Admin detection
  const [error, setError] = useState<string | null>(null)
  const [selectedDimension, setSelectedDimension] = useState<DimensionPreset>(DIMENSION_PRESETS[0])
  const [sizeMode, setSizeMode] = useState<"preset" | "custom">("preset")
  const [customWidth, setCustomWidth] = useState<number>(1024)
  const [customHeight, setCustomHeight] = useState<number>(1024)
  const [qualityTier, setQualityTier] = useState<string>("1k")
  const [selectedStyle, setSelectedStyle] = useState<string>("Auto")
  const [referenceImage, setReferenceImage] = useState<string | null>(null)
  const [generationDimension, setGenerationDimension] = useState<DimensionPreset>(DIMENSION_PRESETS[0])
  const [showStyleMore, setShowStyleMore] = useState(false)
  const [generateShimmer, setGenerateShimmer] = useState(false)
  const [suggestionFilling, setSuggestionFilling] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [genStage, setGenStage] = useState(0)
  const [genProgress, setGenProgress] = useState(0)
  const [sseStage, setSseStage] = useState<string>("")
  const [briefData, setBriefData] = useState<{
    visual_concept: string; mood: string; lighting: string
    camera: string; color_palette: string; style_refs: string[]
  } | null>(null)
  const [activeModel, setActiveModel] = useState<string>("")
  // New state: creation mode, advanced panel, result details
  const [creationMode, setCreationMode] = useState<CreationMode>("image")
  const [negativePrompt, setNegativePrompt] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showFullPrompt, setShowFullPrompt] = useState(false)
  const [copiedPrompt, setCopiedPrompt] = useState(false)
  // Edit-existing-image mode (inline within Image/Poster)
  const [editMode, setEditMode] = useState(false)
  const [editSourceImage, setEditSourceImage] = useState<string | null>(null)
  const [editSourceUrl, setEditSourceUrl] = useState<string>("")
  const editFileInputRef = useRef<HTMLInputElement>(null)
  // Advanced edit modal + logo overlay modal + pack modal
  const [showEditModal, setShowEditModal]       = useState(false)
  const [showLogoModal, setShowLogoModal]       = useState(false)
  const [showPackModal, setShowPackModal]       = useState(false)
  // Poster inline editor state (updated image replaces result.image_url)
  const [posterImageUrl, setPosterImageUrl] = useState<string | null>(null)
  // Dual variant toggle (Phase 6)
  const [activeVariant, setActiveVariant] = useState<"safe" | "experimental">("safe")
  const stageTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const promptHistoryRef = useRef<string[]>([])
  const adaptiveToastShownRef = useRef(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null)
  const { toast } = useToast()

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`
    }
  }, [prompt])

  // Restore from sessionStorage after hydration (avoids SSR mismatch)
  useEffect(() => {
    try {
      const stored = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null")
      if (stored?.userPrompt) setUserPrompt(stored.userPrompt)
      if (stored?.result) setResult(stored.result)
    } catch { /* ignore */ }
  }, [])

  // Persist result to sessionStorage so back-navigation restores it
  useEffect(() => {
    try {
      if (result) {
        // For data: URLs (PIL-composited posters), store as-is but catch quota errors
        sessionStorage.setItem(SESSION_KEY, JSON.stringify({ result, userPrompt }))
      } else {
        sessionStorage.removeItem(SESSION_KEY)
      }
    } catch {
      // Storage quota exceeded (large data: URL) — try storing without the image
      try {
        if (result) {
          const slim = { ...result, image_url: result.image_url?.startsWith("data:") ? "" : result.image_url }
          sessionStorage.setItem(SESSION_KEY, JSON.stringify({ result: slim, userPrompt }))
        }
      } catch { /* give up */ }
    }
  }, [result, userPrompt])

  // Admin detection - check if user is dev@photogenius.local
  useEffect(() => {
    const checkAdmin = async () => {
      try {
        const res = await fetch("/api/user/current")
        if (res.ok) {
          const user = await res.json()
          setIsAdmin(user.email === "dev@photogenius.local")
        }
      } catch {
        // If API fails, assume not admin (safe default)
        setIsAdmin(false)
      }
    }
    checkAdmin()
  }, [])

  const canGenerate = (editMode
    ? (editSourceUrl.length > 0 && prompt.trim().length >= 3 && prompt.trim().length <= 2000)
    : (prompt.trim().length >= 3 && prompt.trim().length <= 2000)
  ) && !isGenerating
  const promptTint = useMemo(() => getPromptTint(prompt), [prompt])

  // Build final prompt
  const buildFinalPrompt = useCallback((base: string): string => {
    return base.trim()
  }, [])

  // ── Edit-existing-image upload (inline in Image/Poster mode) ─────────────────
  const handleEditImageSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      setEditSourceImage(ev.target?.result as string)
      setEditSourceUrl(ev.target?.result as string)
    }
    reader.readAsDataURL(file)
    e.target.value = ""
  }, [])

  const clearEditSource = useCallback(() => {
    setEditSourceImage(null)
    setEditSourceUrl("")
  }, [])

  const handleGenerate = useCallback(async (promptText?: string) => {
    const rawPrompt = promptText ?? prompt
    const finalPrompt = buildFinalPrompt(rawPrompt)
    if (finalPrompt.trim().length < 3 || isGenerating) return

    // ── Edit-existing-image path ───────────────────────────────────────────────
    if (editMode && editSourceUrl) {
      setUserPrompt(rawPrompt.trim())
      setIsGenerating(true)
      setError(null)
      setResult(null)
      setFeedbackGiven(null)
      setPosterImageUrl(null)
      setBriefData(null)
      setSseStage("generating")
      setGenProgress(40)
      try {
        const res = await fetch("/api/generate/edit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_url: editSourceUrl, instruction: finalPrompt.trim(), quality: qualityTier }),
        })
        const data = await res.json()
        if (data.success) {
          setResult({ success: true, image_url: data.image_url, enhanced_prompt: finalPrompt.trim(), model_used: data.model_used, total_time: data.total_time })
          setGenProgress(100)
        } else {
          setError(data.error || "Edit failed")
        }
      } catch {
        setError("Edit service unavailable")
      } finally {
        setIsGenerating(false)
        setSseStage("")
      }
      return
    }

    let genDims: { width: number; height: number }
    if (sizeMode === "custom") {
      genDims = { width: Math.round(customWidth / 64) * 64, height: Math.round(customHeight / 64) * 64 }
    } else if (selectedDimension.aspect === "auto") {
      // Smart auto: detect optimal aspect ratio from prompt
      const auto = smartAutoDims(rawPrompt)
      genDims = { width: auto.width, height: auto.height }
    } else {
      genDims = { width: selectedDimension.width, height: selectedDimension.height }
    }
    setUserPrompt(rawPrompt.trim())
    setGenerationDimension({ ...selectedDimension, width: genDims.width, height: genDims.height })
    setIsGenerating(true)
    setError(null)
    setResult(null)
    setMultiResults([]) // Reset multi-results for admin testing
    setFeedbackGiven(null)
    setPosterImageUrl(null)
    setBriefData(null)
    setActiveModel("")
    setSseStage("intent")
    setGenerateShimmer(true)
    setGenStage(0)
    setGenProgress(SSE_STAGES.intent.pct)
    setTimeout(() => setGenerateShimmer(false), 800)

    // Create abort controller with 3-minute timeout
    abortControllerRef.current?.abort()
    const abort = new AbortController()
    abortControllerRef.current = abort
    const timeoutId = setTimeout(() => abort.abort(), 180_000)

    // P8: Adaptive — suggest Portrait via toast with Apply (user consent)
    promptHistoryRef.current = [finalPrompt.trim(), ...promptHistoryRef.current].slice(0, 10)
    const portraitCount = promptHistoryRef.current.filter(isPortraitLike).length
    if (portraitCount >= 3 && !adaptiveToastShownRef.current) {
      adaptiveToastShownRef.current = true
      const portraitPreset = DIMENSION_PRESETS.find((d) => d.label === "Portrait")
      toast({
        title: "Based on your style",
        description: "Portrait format may work better. Apply?",
        action: portraitPreset ? (
          <ToastAction altText="Apply portrait format" onClick={() => setSelectedDimension(portraitPreset)}>Apply</ToastAction>
        ) : undefined,
      })
    }

    try {
      const res = await fetch("/api/generate/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abort.signal,
        body: JSON.stringify({
          prompt: finalPrompt.trim(),
          width: genDims.width,
          height: genDims.height,
          quality: qualityTier,
          style: selectedStyle !== "Auto" ? selectedStyle : undefined,
          reference_image: referenceImage || undefined,
          negative_prompt: negativePrompt.trim() || undefined,
          testing_mode: isAdmin, // Enable parallel testing for admin
        }),
      })

      if (!res.ok || !res.body) {
        const errData = await res.json().catch(() => ({}))
        throw new Error((errData as { error?: string }).error || `Request failed (${res.status})`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE messages separated by \n\n
        const messages = buffer.split("\n\n")
        buffer = messages.pop() ?? ""

        for (const msg of messages) {
          if (!msg.trim()) continue
          const eventMatch = msg.match(/^event:\s*(\w+)/m)
          const dataMatch = msg.match(/^data:\s*(.+)/m)
          if (!eventMatch || !dataMatch) continue

          const event = eventMatch[1]
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          let data: any
          try { data = JSON.parse(dataMatch[1]) } catch { continue }

          if (event === "intent_ready") {
            setSseStage("intent")
            setGenStage(0)
            setGenProgress(SSE_STAGES.intent.pct)

          } else if (event === "brief_ready") {
            setSseStage("brief")
            setBriefData(data)
            setGenStage(1)
            setGenProgress(SSE_STAGES.brief.pct)

          } else if (event === "generating") {
            setSseStage("generating")
            setGenStage(2)
            setGenProgress(SSE_STAGES.generating.pct)
            if (data.model) setActiveModel(data.model)

          } else if (event === "compositing") {
            setSseStage("compositing")
            setGenProgress(SSE_STAGES.compositing.pct)

          } else if (event === "quality_checking") {
            setSseStage("quality_checking")
            setGenProgress(SSE_STAGES.quality_checking.pct)

          } else if (event === "model_result") {
            // Admin testing mode: collect results as each model completes
            const newResult: GenerationResult = {
              success: true,
              image_url: data.imageUrl,
              enhanced_prompt: finalPrompt.trim(),
              detected_settings: {
                style: "Professional",
                mood: "Testing",
                lighting: "Auto",
                quality: getQualityMeta(qualityTier).label,
                category: "test",
              },
              model_used: data.modelId,
              total_time: data.latency,
              generationId: data.generationId,
            }
            setMultiResults(prev => [...prev, newResult])

          } else if (event === "testing_complete") {
            // All testing models finished
            setSseStage("done")
            setGenProgress(100)
            setPosterImageUrl(null)

          } else if (event === "final_ready") {
            setSseStage("done")
            setGenProgress(100)
            setPosterImageUrl(null) // reset inline editor override
            setActiveVariant("safe") // reset variant toggle

            // Check if admin testing mode returned multiple results
            if (isAdmin && data.model_results && Array.isArray(data.model_results)) {
              // Admin testing mode: multiple results from different models
              const results = data.model_results.map((mr: any) => ({
                success: true,
                image_url: mr.image_url,
                enhanced_prompt: data.enhanced_prompt,
                detected_settings: {
                  style: "Professional",
                  mood: data.brief?.mood || "Cinematic",
                  lighting: data.brief?.lighting?.split(",")[0] || "Natural",
                  quality: getQualityMeta(qualityTier).label,
                  category: data.capability_bucket || "photo",
                },
                model_used: mr.model_name,
                total_time: mr.generation_time,
                quality_score: data.quality_score,
                generationId: mr.generationId,
                creative_os: data.creative_os,
                capability_bucket: data.capability_bucket,
              }))
              setMultiResults(results)
              setResult(null) // Clear single result for admin
            } else {
              // Normal mode: single result
              setResult({
                success: true,
                image_url: data.image_url,
                enhanced_prompt: data.enhanced_prompt,
                detected_settings: {
                  style: "Professional",
                  mood: data.brief?.mood || "Cinematic",
                  lighting: data.brief?.lighting?.split(",")[0] || "Natural",
                  quality: getQualityMeta(qualityTier).label,
                  category: data.capability_bucket || "photo",
                },
                model_used: data.model_used,
                total_time: data.total_time,
                quality_score: data.quality_score,
                quality_gate: data.quality_gate,
                generationId: data.generationId,
                creative_os: data.creative_os,
                // Poster fields
                ad_copy: data.ad_copy,
                poster_design: data.poster_design,
                hero_url: data.hero_url,
                capability_bucket: data.capability_bucket,
                design_brief: data.design_brief,
                image_url_experimental: data.image_url_experimental ?? undefined,
                motion_hints: data.design_brief?.motion_hints,
                learning_logged: true, // Learning Engine logs all generations
              })
              setMultiResults([]) // Clear multi results for normal users
            }


          } else if (event === "heartbeat") {
            // Backend keeps SSE alive during long parallel gens (Hunyuan ~115s).
            // No UI action — just swallow so "unknown event" doesn't spam logs.

          } else if (event === "error") {
            throw new Error(data.message || "Generation failed")
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setError("Generation timed out — please try again")
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong")
      }
    } finally {
      clearTimeout(timeoutId)
      setIsGenerating(false)
      if (stageTimerRef.current) clearTimeout(stageTimerRef.current)
    }
  }, [prompt, isGenerating, selectedDimension, sizeMode, customWidth, customHeight, qualityTier, selectedStyle, referenceImage, negativePrompt, buildFinalPrompt, toast, editMode, editSourceUrl, isAdmin])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && canGenerate) {
      e.preventDefault()
      handleGenerate()
    }
  }

  const handleReset = () => {
    abortControllerRef.current?.abort()
    setResult(null)
    setError(null)
    setUserPrompt("")
    setReferenceImage(null)
    setPosterImageUrl(null)
    setFeedbackGiven(null)
  }

  const handleReferenceImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file?.type.startsWith("image/")) return
    if (file.size > 5 * 1024 * 1024) {
      toast({ title: "Image too large", description: "Reference image must be under 5 MB.", variant: "destructive" })
      e.target.value = ""
      return
    }
    const reader = new FileReader()
    reader.onload = () => setReferenceImage(reader.result as string)
    reader.readAsDataURL(file)
    e.target.value = ""
  }

  const removeReferenceImage = () => setReferenceImage(null)

  // Voice input (Web Speech API)
  const toggleVoice = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
      return
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const w = window as any
    const SpeechRecognitionAPI = typeof window !== "undefined" && (w.SpeechRecognition || w.webkitSpeechRecognition)
    if (!SpeechRecognitionAPI) {
      toast({ title: "Voice input", description: "Not supported in this browser. Try Chrome or Edge." })
      return
    }
    const recognition = new SpeechRecognitionAPI()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = "en-US"
    recognition.onresult = (e: { results: { [key: number]: { [key: number]: { transcript: string } } } }) => {
      const transcript = Array.from(Object.values(e.results) as Array<{ [key: number]: { transcript: string } }>)
        .map((r) => r[0].transcript)
        .join(" ")
      setPrompt((p) => (p ? `${p} ${transcript}` : transcript))
    }
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }, [isListening, toast])

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort()
      abortControllerRef.current?.abort()
    }
  }, [])

  // ── P3: Feedback (thumbs up/down) ─────────────────────────────────────────
  const [feedbackGiven, setFeedbackGiven] = useState<"up" | "down" | null>(null)

  const handleFeedback = async (thumbs: "up" | "down") => {
    if (!result?.generationId) return   // guard: no ID = nothing to record
    setFeedbackGiven(thumbs)
    try {
      await fetch("/api/preferences/thumbs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          generationId: result.generationId,
          imageUrl: result.image_url ?? "",
          thumbs,
          style: selectedStyle,
          bucket: result.creative_os?.intent
            ? (result.creative_os.intent as { creative_type?: string }).creative_type ?? "photorealism"
            : "photorealism",
          tier: qualityTier,
          enhancedPrompt: result.enhanced_prompt ?? "",
        }),
      })
    } catch { /* silent — feedback is best-effort */ }
  }

  const handleDownload = async () => {
    const url = posterImageUrl ?? result?.image_url
    if (!url) return
    try {
      // For data: URIs, anchor click works directly
      if (url.startsWith("data:")) {
        const link = document.createElement("a")
        link.href = url
        link.download = `photogenius-${Date.now()}.jpg`
        link.click()
        return
      }
      // For cross-origin CDN URLs, fetch → blob to trigger Save As
      const blob = await fetch(url).then(r => r.blob())
      const blobUrl = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = blobUrl
      link.download = `photogenius-${Date.now()}.jpg`
      link.click()
      URL.revokeObjectURL(blobUrl)
    } catch {
      // Last-resort: open in new tab
      window.open(url, "_blank")
    }
  }

  // Regenerate with same prompt
  const handleRegenerate = () => {
    if (userPrompt) handleGenerate(userPrompt)
  }

  // Edit prompt and go back to form
  const handleEditPrompt = () => {
    setPrompt(userPrompt)
    setResult(null)
    setError(null)
    setPosterImageUrl(null)
    setFeedbackGiven(null)
  }

  // Edit the generated image — open advanced edit modal
  const handleEditGeneratedImage = () => {
    // Loud visible signal — if click reaches here, user WILL see this
    try { (window as any).__editClickCount = ((window as any).__editClickCount || 0) + 1 } catch {}
    console.log("[EDIT-BTN] click fired. result:", result, "image_url:", result?.image_url)
    toast({ title: "Opening editor…", description: "Loading edit tools" })
    if (!result?.image_url) {
      toast({
        title: "No image to edit",
        description: `result=${result ? "exists" : "null"}, image_url=${result?.image_url ?? "missing"}`,
        variant: "destructive",
      })
      return
    }
    setShowEditModal(true)
  }

  // Copy enhanced prompt
  const handleCopyPrompt = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedPrompt(true)
    setTimeout(() => setCopiedPrompt(false), 2000)
  }

  // Format seconds to readable time
  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`
  }

  // P6: Suggestion click — fill prompt with animation
  const handleSuggestionClick = (item: (typeof SUGGESTION_CARDS)[0]) => {
    setSuggestionFilling(true)
    setPrompt(item.prompt)
    setTimeout(() => setSuggestionFilling(false), 400)
  }

  // ——— Result view ———
  if (result?.image_url || multiResults.length > 0) {
    const aspectStyle = { aspectRatio: `${generationDimension.width}/${generationDimension.height}` }
    const ds = result?.detected_settings

    // Admin multi-results grid
    if (multiResults.length > 0) {
      return (
        <div className="relative w-full generate-mesh py-6 px-4">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-7xl mx-auto"
          >
            <p className="text-xs text-muted-foreground/60 text-center mb-5 italic">&quot;{userPrompt}&quot;</p>

            {/* Multi-model results grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {multiResults.map((res, idx) => (
                <motion.div
                  key={res.generationId || idx}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: idx * 0.1 }}
                  className="relative rounded-2xl overflow-hidden border border-white/10 bg-black/20"
                >
                  <div className="relative w-full" style={aspectStyle}>
                    <Image
                      src={res.image_url || ""}
                      alt={`Result ${idx + 1}`}
                      fill
                      className="object-cover"
                      unoptimized
                      priority
                    />
                  </div>

                  {/* Per-card actions */}
                  <div className="p-3 bg-black/40 flex flex-col gap-2">
                    {/* Primary: promote to single-result view → unlocks full toolbar
                        (Canvas Editor, Add Logo, Regenerate, Edit Prompt, Gallery, etc) */}
                    <Button
                      onClick={() => {
                        setResult(res)
                        setMultiResults([])
                      }}
                      className="gap-2 btn-premium text-white rounded-xl text-sm"
                    >
                      <PenSquare className="h-3.5 w-3.5" /> Use This Image
                    </Button>

                    {/* Direct action row */}
                    <div className="grid grid-cols-3 gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={async () => {
                          const url = res.image_url
                          if (!url) return
                          try {
                            if (url.startsWith("data:")) {
                              const link = document.createElement("a")
                              link.href = url
                              link.download = `photogenius-${Date.now()}.jpg`
                              link.click()
                              return
                            }
                            const blob = await fetch(url).then(r => r.blob())
                            const blobUrl = URL.createObjectURL(blob)
                            const link = document.createElement("a")
                            link.href = blobUrl
                            link.download = `photogenius-${Date.now()}.jpg`
                            link.click()
                            URL.revokeObjectURL(blobUrl)
                          } catch {
                            window.open(url, "_blank")
                          }
                        }}
                        className="gap-1 rounded-xl border-white/[0.1] bg-white/[0.03] text-xs"
                      >
                        <Download className="h-3 w-3" />
                        Save
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          console.log("[EDIT-GRID] click fired. res:", res)
                          if (!res?.image_url) {
                            toast({
                              title: "No image URL in this result",
                              description: JSON.stringify(res).slice(0, 200),
                              variant: "destructive",
                            })
                            return
                          }
                          setResult(res)
                          setMultiResults([])
                          setShowEditModal(true)
                        }}
                        className="gap-1 rounded-xl border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 text-xs"
                      >
                        <Scissors className="h-3 w-3" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setResult(res)
                          setMultiResults([])
                          setShowLogoModal(true)
                        }}
                        className="gap-1 rounded-xl border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 text-xs"
                      >
                        <ImageIcon className="h-3 w-3" />
                        Logo
                      </Button>
                    </div>

                    {/* Rating */}
                    {res.generationId && (
                      <ImageRating generationId={res.generationId} imageUrl={res.image_url || ""} />
                    )}
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Back button */}
            <div className="flex justify-center mt-8">
              <Button
                onClick={handleReset}
                variant="ghost"
                className="gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                Generate Another
              </Button>
            </div>
          </motion.div>
        </div>
      )
    }

    // Normal single result view
    return (
      <div className="relative w-full generate-mesh py-6 px-4">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-6xl mx-auto"
        >
          {/* Prompt echo */}
          <p className="text-xs text-muted-foreground/60 text-center mb-5 italic truncate px-2">&quot;{userPrompt}&quot;</p>

          {/* 2-col: image + details */}
          <div className="grid grid-cols-1 md:grid-cols-[1fr_300px] lg:grid-cols-[1fr_320px] gap-5 items-start">

            {/* Image + inline editor column */}
            <div className="flex flex-col gap-0">
              {/* Dual Variant toggle — shown when experimental variant exists */}
              {result.image_url_experimental && (
                <div className="flex items-center gap-2 mb-2">
                  <button
                    onClick={() => setActiveVariant("safe")}
                    className="flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all"
                    style={{
                      background: activeVariant === "safe" ? "rgba(109,99,255,0.25)" : "rgba(255,255,255,0.05)",
                      border: `1px solid ${activeVariant === "safe" ? "#6C63FF" : "rgba(255,255,255,0.1)"}`,
                      color: activeVariant === "safe" ? "#a78bfa" : "#888",
                    }}
                  >Safe</button>
                  <button
                    onClick={() => setActiveVariant("experimental")}
                    className="flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all"
                    style={{
                      background: activeVariant === "experimental" ? "rgba(236,72,153,0.2)" : "rgba(255,255,255,0.05)",
                      border: `1px solid ${activeVariant === "experimental" ? "#ec4899" : "rgba(255,255,255,0.1)"}`,
                      color: activeVariant === "experimental" ? "#f472b6" : "#888",
                    }}
                  >Creative ✨</button>
                </div>
              )}
              <motion.div
                initial={{ opacity: 0, scale: 0.97 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.04 }}
                className="relative w-full rounded-2xl overflow-hidden result-card-glow border border-white/10 bg-black/20"
                style={{ ...aspectStyle, maxHeight: "78vh" }}
              >
                <Image
                  src={posterImageUrl ?? (activeVariant === "experimental" && result.image_url_experimental ? result.image_url_experimental : result.image_url)}
                  alt="Generated"
                  fill
                  className="object-contain"
                  unoptimized
                  priority
                />
              </motion.div>
            </div>

            {/* Details panel */}
            <motion.div
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.08 }}
              className="flex flex-col gap-3 lg:sticky lg:top-5"
            >

              {/* Quick stats */}
              <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="h-3.5 w-3.5 text-primary shrink-0" />
                  <span className="text-xs font-semibold text-foreground/80">AI Analysis</span>
                  <div className="flex-1" />
                  {result.creative_os?.jury?.grade && (
                    <span className={cn(
                      "text-[11px] font-bold px-2 py-0.5 rounded-md",
                      result.creative_os.jury.grade === "A" && "bg-emerald-500/20 text-emerald-400",
                      result.creative_os.jury.grade === "B" && "bg-blue-500/20 text-blue-400",
                      result.creative_os.jury.grade === "C" && "bg-amber-500/20 text-amber-400",
                      result.creative_os.jury.grade === "D" && "bg-orange-500/20 text-orange-400",
                      result.creative_os.jury.grade === "F" && "bg-red-500/20 text-red-400",
                    )}>
                      {result.creative_os.jury.grade}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-2">
                  {result.quality_gate?.total != null && (
                    <div className="flex items-center gap-1.5" title={result.quality_gate.critique || "AI quality score"}>
                      <Star className="h-3 w-3 text-amber-400 shrink-0" />
                      <span className="text-xs font-semibold text-amber-400">
                        {Math.round(result.quality_gate.total)}/100
                      </span>
                      <span className="text-[10px] text-muted-foreground/60">
                        grade {result.quality_gate.grade}
                        {result.quality_gate.auto_rerun_done ? " · refined" : ""}
                      </span>
                    </div>
                  )}
                  {result.quality_score != null && result.quality_gate?.total == null && (
                    <div className="flex items-center gap-1.5">
                      <Star className="h-3 w-3 text-amber-400 shrink-0" />
                      <span className="text-xs font-semibold text-amber-400">{Math.round(result.quality_score * 100)}%</span>
                      <span className="text-[10px] text-muted-foreground/60">quality</span>
                    </div>
                  )}
                  {result.total_time != null && (
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-xs text-muted-foreground/80">{formatTime(result.total_time)}</span>
                    </div>
                  )}
                </div>

                {/* Detected settings */}
                {ds && (
                  <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-white/[0.06]">
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-blue-500/15 text-blue-400">{ds.style}</span>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-purple-500/15 text-purple-400">{ds.mood}</span>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-500/15 text-amber-400">{ds.lighting}</span>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-emerald-500/15 text-emerald-400">{ds.category}</span>
                  </div>
                )}
              </div>

              {/* Jury scores — poster/ad only */}
              {result.creative_os?.jury && (
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4">
                  <p className="text-xs font-semibold text-foreground/70 mb-3">Design Scores</p>
                  <div className="space-y-2">
                    {[
                      { label: "Readability",  value: result.creative_os.jury.readability },
                      { label: "Balance",      value: result.creative_os.jury.balance },
                      { label: "Harmony",      value: result.creative_os.jury.color_harmony },
                      { label: "Composition",  value: result.creative_os.jury.composition },
                      { label: "Contrast",     value: result.creative_os.jury.wcag_contrast },
                      { label: "Text Quality", value: result.creative_os.jury.ocr_quality },
                    ].map(s => (
                      <div key={s.label} className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground/70 w-20 shrink-0">{s.label}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-white/[0.08] overflow-hidden">
                          <div
                            className={cn("h-full rounded-full transition-all",
                              s.value >= 0.7 ? "bg-emerald-500" : s.value >= 0.4 ? "bg-amber-500" : "bg-red-500"
                            )}
                            style={{ width: `${Math.round(s.value * 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-muted-foreground/50 w-7 text-right shrink-0">{Math.round(s.value * 100)}</span>
                      </div>
                    ))}
                  </div>
                  {result.creative_os.jury.issues.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1">
                      {result.creative_os.jury.issues.slice(0, 2).map((issue, i) => (
                        <span key={i} className="text-[9px] text-orange-400/80 bg-orange-500/10 px-1.5 py-0.5 rounded">
                          {issue}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Enhanced prompt */}
              {result.enhanced_prompt && result.enhanced_prompt !== userPrompt && (
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[10px] font-semibold text-muted-foreground/70 uppercase tracking-wide">Enhanced Prompt</span>
                    <div className="flex-1" />
                    <button
                      type="button"
                      onClick={() => handleCopyPrompt(result.enhanced_prompt!)}
                      className="p-1 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
                      title="Copy prompt"
                    >
                      {copiedPrompt ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowFullPrompt(!showFullPrompt)}
                      className="p-1 rounded-lg hover:bg-white/10 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showFullPrompt ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                    </button>
                  </div>
                  <p className={cn("text-xs text-muted-foreground/80 leading-relaxed", !showFullPrompt && "line-clamp-3")}>
                    {result.enhanced_prompt}
                  </p>
                </div>
              )}

              {/* Action buttons */}
              <div className="grid grid-cols-2 gap-2">
                <Button onClick={handleDownload} className="gap-2 btn-premium text-white rounded-xl col-span-2">
                  <Download className="h-4 w-4" /> Download
                </Button>
                {result.ad_copy && result.hero_url && (
                  <Button
                    onClick={() => setShowPackModal(true)}
                    className="gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-sm col-span-2"
                    variant="outline"
                  >
                    <Package className="h-3.5 w-3.5" /> Download Pack (4 sizes)
                  </Button>
                )}
                {/* Rating Component (replaces thumbs up/down) */}
                {result.generationId && (
                  <div className="col-span-2">
                    <ImageRating
                      generationId={result.generationId}
                      imageUrl={result.image_url}
                      currentRating={undefined}
                      onRatingSubmit={(rating, reason) => {
                        // Optional: Update local state or show toast
                        toast({
                          title: "Rating submitted",
                          description: `Thank you for rating this ${rating} stars!`,
                        })
                      }}
                    />
                  </div>
                )}
                <Button
                  type="button"
                  onClick={handleEditGeneratedImage}
                  onPointerDown={handleEditGeneratedImage}
                  className="gap-2 rounded-xl border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 text-sm col-span-2 relative z-10"
                  variant="outline"
                >
                  <Scissors className="h-3.5 w-3.5" /> Edit Image
                </Button>
                <Button onClick={() => setShowLogoModal(true)} className="gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 text-sm col-span-2" variant="outline">
                  <ImageIcon className="h-3.5 w-3.5" /> Add Logo
                </Button>
                <Button onClick={handleRegenerate} variant="outline" className="gap-2 rounded-xl border-white/[0.1] bg-white/[0.03] text-sm">
                  <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                </Button>
                <Button onClick={handleEditPrompt} variant="outline" className="gap-2 rounded-xl border-white/[0.1] bg-white/[0.03] text-sm">
                  <PenTool className="h-3.5 w-3.5" /> Edit Prompt
                </Button>
                <Link href="/gallery" className="contents">
                  <Button variant="outline" className="gap-2 rounded-xl border-white/[0.1] bg-white/[0.03] text-sm">
                    <ImageIcon className="h-3.5 w-3.5" /> Gallery
                  </Button>
                </Link>
                <Button onClick={handleReset} variant="outline" className="gap-2 rounded-xl border-white/[0.1] bg-white/[0.03] text-sm">
                  <RotateCcw className="h-3.5 w-3.5" /> New Image
                </Button>
              </div>

            </motion.div>{/* end details panel */}
          </div>{/* end 2-col grid */}
        </motion.div>

        {/* Poster Pack modal */}
        {result.ad_copy && result.hero_url && (
          <PosterPackModal
            open={showPackModal}
            onClose={() => setShowPackModal(false)}
            heroUrl={result.hero_url}
            adCopy={result.ad_copy}
            posterDesign={result.poster_design ?? {}}
            designBrief={result.design_brief}
          />
        )}
      </div>
    )
  }

  // ——— Main layout ———
  return (
    <div className="relative w-full generate-mesh overflow-x-hidden">
      {isGenerating && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background/95 backdrop-blur-xl"
        >
          <div className="loading-waveform mb-8">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <span key={i} />
            ))}
          </div>
          <div className="w-80 space-y-4 text-center">
            <motion.div
              key={sseStage || genStage}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <p className="text-base font-semibold text-foreground">
                {(sseStage && SSE_STAGES[sseStage]?.label) || GENERATION_STAGES[genStage]?.label}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {(sseStage && SSE_STAGES[sseStage]?.sub) || GENERATION_STAGES[genStage]?.sub}
              </p>
              {sseStage === "generating" && (
                <div className="flex items-center justify-center gap-2 mt-2">
                  <p className="text-[11px] text-muted-foreground/60">
                    {getQualityMeta(qualityTier).hint} est.
                  </p>
                </div>
              )}
            </motion.div>

            <div className="w-full h-1.5 rounded-full bg-white/10 overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-primary"
                initial={{ width: 0 }}
                animate={{ width: `${genProgress}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
            </div>

            <div className="flex justify-center gap-1.5">
              {GENERATION_STAGES.map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    "h-1 rounded-full transition-all duration-300",
                    i <= genStage ? "w-6 bg-primary" : "w-2 bg-white/20"
                  )}
                />
              ))}
            </div>

            {/* Creative Brief card — appears after Gemini brief is ready */}
            <AnimatePresence>
              {briefData && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.4 }}
                  className="rounded-xl bg-white/[0.04] border border-white/[0.08] p-4 text-left"
                >
                  <p className="text-[10px] font-semibold text-primary/70 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <Sparkles className="h-3 w-3" /> Creative Brief
                  </p>
                  {briefData.visual_concept && (
                    <p className="text-xs text-foreground/80 leading-relaxed mb-3">
                      {briefData.visual_concept.length > 110
                        ? `${briefData.visual_concept.slice(0, 110)}…`
                        : briefData.visual_concept}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    {briefData.mood && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary/90">
                        {briefData.mood}
                      </span>
                    )}
                    {briefData.lighting && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-muted-foreground">
                        {briefData.lighting.split(",")[0].trim()}
                      </span>
                    )}
                    {briefData.camera && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-muted-foreground">
                        {briefData.camera.split(",")[0].trim()}
                      </span>
                    )}
                    {briefData.style_refs?.slice(0, 2).map((ref, i) => (
                      <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.06] text-muted-foreground/70 italic">
                        {ref}
                      </span>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      )}

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed top-20 left-1/2 -translate-x-1/2 z-50 max-w-md w-full mx-4 p-4 rounded-xl border border-destructive/40 bg-destructive/10 backdrop-blur-xl flex items-start gap-3"
        >
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-destructive">Generation failed</p>
            <p className="text-xs text-destructive/90 truncate">{error}</p>
            <button
              type="button"
              onClick={() => handleGenerate()}
              className="text-xs text-destructive underline mt-1 hover:opacity-80"
            >
              Try again
            </button>
          </div>
          <button type="button" onClick={() => setError(null)} className="text-destructive/70 hover:text-destructive">
            <X className="h-4 w-4" />
          </button>
        </motion.div>
      )}

      {/* ── Main grid ── */}
      <div className="relative max-w-4xl mx-auto pt-3 pb-28 min-w-0">
        <div className="grid grid-cols-1 gap-5 min-w-0">

          {/* ── LEFT COLUMN ── */}
          <div className="flex flex-col gap-4 min-w-0 overflow-hidden">

            {/* Mode toggle + hint row */}
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center justify-between gap-3"
            >
              <div className="flex flex-1 sm:flex-none rounded-xl overflow-hidden border border-white/[0.08] bg-white/[0.02] p-0.5">
                {([
                  { id: "image",  icon: Camera,    label: "Image" },
                  { id: "poster", icon: Megaphone, label: "Poster / Ad" },
                ] as { id: CreationMode; icon: React.ElementType; label: string }[]).map(({ id, icon: Icon, label }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => {
                      setCreationMode(id)
                      setEditMode(false)
                      clearEditSource()
                    }}
                    className={cn(
                      "flex flex-1 sm:flex-none items-center justify-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-medium transition-all",
                      creationMode === id
                        ? "bg-primary/20 text-primary shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0" />
                    <span>{label}</span>
                  </button>
                ))}
              </div>
              <span className="hidden sm:flex items-center gap-1.5 text-[11px] text-muted-foreground/50 shrink-0">
                <kbd className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/[0.08] font-mono text-[10px]">↵</kbd>
                to generate
              </span>
            </motion.div>

            {/* ── HERO PROMPT AREA ── */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 }}
              className="relative rounded-2xl prompt-hero-box overflow-hidden shadow-xl shadow-black/5"
            >
              {promptTint !== "transparent" && (
                <div
                  className="absolute inset-0 pointer-events-none transition-opacity duration-500"
                  style={{ background: promptTint }}
                />
              )}

              {/* Textarea row */}
              <div className="relative p-5 pb-4">
                <div className="flex items-start gap-3">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleReferenceImageSelect}
                    className="hidden"
                    aria-label="Add reference image"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isGenerating}
                    className="btn-press mt-1.5 h-10 w-10 rounded-[13px] flex items-center justify-center shrink-0 bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 hover:scale-105 disabled:opacity-50 transition-all"
                    title="Add reference image"
                  >
                    <Plus className="h-4.5 w-4.5" />
                  </button>
                  <textarea
                    ref={textareaRef}
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={
                      editMode
                        ? '✏️ Describe the edit — "change jacket to red", "add snow", "remove background"'
                        : creationMode === "poster"
                        ? "✨ Describe the visual — background, subject, mood..."
                        : "✨ Describe your imagination — be as detailed as you like..."
                    }
                    rows={5}
                    disabled={isGenerating}
                    className="flex-1 resize-none bg-transparent px-2 py-1.5 text-[17px] font-medium leading-relaxed outline-none placeholder:text-muted-foreground/50 disabled:opacity-50 min-h-[150px] max-h-[280px]"
                  />
                  <button
                    type="button"
                    onClick={toggleVoice}
                    disabled={isGenerating}
                    className={cn(
                      "btn-press mt-1.5 h-10 w-10 rounded-[13px] flex items-center justify-center shrink-0 disabled:opacity-50 transition-all",
                      isListening
                        ? "bg-red-500/20 text-red-400 border border-red-500/30 scale-105"
                        : "bg-white/[0.05] text-muted-foreground border border-white/[0.08] hover:text-foreground hover:bg-white/10 hover:scale-105"
                    )}
                    title={isListening ? "Stop voice input" : "Voice input"}
                  >
                    {isListening ? <MicOff className="h-4.5 w-4.5" /> : <Mic className="h-4.5 w-4.5" />}
                  </button>
                </div>

                {/* Reference image preview */}
                {referenceImage && (
                  <div className="flex items-center gap-2.5 mt-3 pt-3 border-t border-white/[0.06]">
                    <div className="relative h-12 w-12 rounded-lg overflow-hidden border border-white/10 shrink-0">
                      <Image src={referenceImage} alt="Reference" fill className="object-cover" unoptimized />
                      <button
                        type="button"
                        onClick={removeReferenceImage}
                        className="absolute -top-1 -right-1 h-4.5 w-4.5 rounded-full bg-destructive flex items-center justify-center"
                      >
                        <X className="h-3 w-3 text-white" />
                      </button>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-foreground/80">Reference attached</p>
                      <p className="text-[10px] text-muted-foreground/60">AI will use this as style guide</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom toolbar */}
              <div className="border-t border-white/[0.06] px-5 py-2.5 flex items-center gap-2">
                <input ref={editFileInputRef} type="file" accept="image/*" onChange={handleEditImageSelect} className="hidden" />
                <button
                  type="button"
                  onClick={() => { setEditMode(!editMode); if (editMode) clearEditSource() }}
                  disabled={isGenerating}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all",
                    editMode
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-white/[0.08] bg-white/[0.04] text-muted-foreground hover:text-foreground hover:border-white/15 hover:bg-white/[0.06]"
                  )}
                >
                  <Scissors className="h-3 w-3" />
                  Edit existing
                </button>
                <div className="flex-1" />
                <div className="flex items-center gap-2">
                  {prompt.length > 0 && (
                    <span className={cn(
                      "text-[10px] font-semibold tabular-nums transition-colors px-2 py-0.5 rounded-md",
                      prompt.length > 1800
                        ? "text-amber-400 bg-amber-500/10"
                        : "text-muted-foreground/50"
                    )}>
                      {prompt.length}/2000
                    </span>
                  )}
                </div>
              </div>

              {/* Edit source upload */}
              <AnimatePresence>
                {editMode && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden border-t border-white/[0.06]"
                  >
                    <div className="p-3">
                      <div
                        onClick={() => editFileInputRef.current?.click()}
                        className={cn(
                          "relative w-full rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors",
                          editSourceImage
                            ? "h-36 border-primary/30 bg-primary/5"
                            : "h-24 border-white/[0.12] hover:border-primary/40 hover:bg-primary/5"
                        )}
                      >
                        {editSourceImage ? (
                          <>
                            <Image src={editSourceImage} alt="Source" fill className="object-contain rounded-xl p-1" unoptimized />
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); clearEditSource() }}
                              className="absolute top-1.5 right-1.5 h-5 w-5 rounded-full bg-black/60 flex items-center justify-center z-10"
                            >
                              <X className="h-3 w-3 text-white" />
                            </button>
                          </>
                        ) : (
                          <>
                            <Upload className="h-5 w-5 text-muted-foreground/60" />
                            <span className="text-xs text-muted-foreground/70">Click to upload image to edit</span>
                          </>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>

            {/* ── INSPIRATIONS ── */}
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.07 }}>
              <p className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                <Lightbulb className="h-3 w-3" />
                {creationMode === "poster" ? "Poster Templates" : "Try These"}
              </p>
              <div className="overflow-x-auto no-scrollbar flex gap-2 pb-1">
                {(creationMode === "poster" ? POSTER_SUGGESTION_CARDS : SUGGESTION_CARDS).map((item) => (
                  <motion.button
                    key={item.id}
                    onClick={() => handleSuggestionClick(item)}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={cn(
                      "shrink-0 flex items-center gap-2.5 px-4 py-2.5 rounded-xl border bg-gradient-to-br transition-all",
                      suggestionFilling && prompt === item.prompt
                        ? "border-primary/50 from-primary/15 to-primary/5 ring-2 ring-primary/30"
                        : "border-white/[0.08] from-white/[0.03] to-white/[0.01] hover:border-white/[0.15] hover:from-white/[0.06] hover:to-white/[0.02]"
                    )}
                  >
                    <span className="text-lg">{item.emoji}</span>
                    <span className="text-xs font-semibold text-foreground/80 whitespace-nowrap">{item.label}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>

            {/* ── WORLD-CLASS CONTROLS V2 ── */}
            <GenerationControlsV2
              dimensionPresets={DIMENSION_PRESETS}
              selectedDimension={selectedDimension}
              onDimensionChange={(preset) => { setSelectedDimension(preset); setSizeMode("preset") }}
              sizeMode={sizeMode}
              customWidth={customWidth}
              customHeight={customHeight}
              onCustomWidthChange={setCustomWidth}
              onCustomHeightChange={setCustomHeight}
              onSizeModeChange={(mode) => {
                if (mode === "custom") {
                  const d = sizeMode === "custom"
                    ? { width: customWidth, height: customHeight }
                    : { width: selectedDimension.width, height: selectedDimension.height }
                  setCustomWidth(d.width)
                  setCustomHeight(d.height)
                }
                setSizeMode(mode)
              }}
              qualityOptions={QUALITY_OPTIONS.map(q => ({
                value: q.value,
                label: q.label,
                hint: q.hint,
                note: q.note,
              }))}
              qualityTier={qualityTier}
              onQualityChange={setQualityTier}
              styles={STYLE_ALL}
              selectedStyle={selectedStyle}
              onStyleChange={setSelectedStyle}
              negativePrompt={negativePrompt}
              onNegativePromptChange={setNegativePrompt}
              showAdvanced={showAdvanced}
              onAdvancedToggle={() => setShowAdvanced(!showAdvanced)}
              isGenerating={isGenerating}
            />

          </div>{/* end LEFT COLUMN */}

        </div>{/* end grid */}
      </div>{/* end max-w wrapper */}

      {/* ── STICKY GENERATE BAR (World-Class) ── */}
      <div className="fixed bottom-0 left-0 lg:left-60 right-0 z-40 pointer-events-none">
        <div className="pointer-events-auto max-w-4xl mx-auto px-3 sm:px-4 pb-3 sm:pb-4" style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom, 12px))" }}>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="rounded-2xl border border-white/[0.12] bg-background/90 backdrop-blur-2xl p-3.5 flex items-center gap-3 shadow-2xl shadow-black/50"
          >
            <Button
              onClick={() => handleGenerate()}
              disabled={!canGenerate}
              className={cn(
                "btn-press w-full px-7 py-5 text-[15px] font-semibold rounded-[15px] btn-generate-hero transition-all hover:scale-[1.01] active:scale-[0.99]",
                generateShimmer && "shimmer"
              )}
            >
              {isGenerating ? (
                <span className="flex items-center gap-2.5">
                  <Loader2 className="h-4.5 w-4.5 animate-spin" />
                  <span>{editMode ? "Editing..." : "Creating..."}</span>
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <Sparkles className="h-4.5 w-4.5" />
                  <span>{editMode ? "Apply Edit" : creationMode === "poster" ? "Generate Poster" : "Generate Image"}</span>
                </span>
              )}
            </Button>
          </motion.div>
        </div>
      </div>

      {/* Edit Image Modal */}
      {showEditModal && result?.image_url && (
        <EditImageModal
          imageUrl={result.image_url}
          onClose={() => setShowEditModal(false)}
          onResult={(newUrl) => {
            setResult(prev => prev ? { ...prev, image_url: newUrl } : prev)
            setShowEditModal(false)
          }}
        />
      )}

      {/* Logo Overlay Modal */}
      {showLogoModal && result?.image_url && (
        <LogoOverlayModal
          imageUrl={result.image_url}
          onClose={() => setShowLogoModal(false)}
          onResult={(newUrl) => {
            setResult(prev => prev ? { ...prev, image_url: newUrl } : prev)
            setShowLogoModal(false)
          }}
        />
      )}
    </div>
  )
}
