"use client"

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react"
import dynamic from "next/dynamic"

const EditImageModal   = dynamic(() => import("@/components/edit-image-modal"),   { ssr: false })
const LogoOverlayModal = dynamic(() => import("@/components/logo-overlay-modal"), { ssr: false })
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Sparkles,
  Loader2,
  Download,
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
  Type,
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
  total_time?: number
  model_used?: string
  creative_os?: CreativeOSData
}

// SSE-driven stage labels — updated by real backend events
const SSE_STAGES: Record<string, { label: string; sub: string; pct: number }> = {
  intent:     { label: "Reading your vision",     sub: "Detecting intent & creative type",  pct: 10 },
  brief:      { label: "Creative brief ready",    sub: "Photographer mindset applied",      pct: 35 },
  generating: { label: "Rendering with AI",       sub: "Flux Pro processing your image",    pct: 55 },
  done:       { label: "Finishing touches",       sub: "Optimizing quality",                pct: 95 },
}
// Fallback array for dot indicator (4 stages)
const GENERATION_STAGES = [
  { label: "Reading your vision",   sub: "Detecting intent & creative type", pct: 10 },
  { label: "Creative brief ready",  sub: "Photographer mindset applied",     pct: 35 },
  { label: "Rendering with AI",     sub: "Flux Pro processing your image",   pct: 55 },
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
  { value: "fast",     label: "Fast",     hint: "~8s",   note: "Quick draft"     },
  { value: "balanced", label: "Standard", hint: "~25s",  note: "ESRGAN 2× boost" },
  { value: "quality",  label: "Premium",  hint: "~45s",  note: "ESRGAN 4× boost" },
  { value: "ultra",    label: "Ultra",    hint: "~60s",  note: "Jury + 4× boost" },
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
  fast: "#71717a", balanced: "#3b82f6", quality: "#8b5cf6", ultra: "#d97706"
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

// P2: Reactive tint — keyword -> subtle bg tint
function getPromptTint(prompt: string): string {
  const p = prompt.toLowerCase()
  if (/\b(cyberpunk|neon|night|sci-fi)\b/.test(p)) return "rgba(0,255,255,0.04)"
  if (/\b(nature|forest|green|grass|tree)\b/.test(p)) return "rgba(34,197,94,0.05)"
  if (/\b(sunset|golden|warm|fire)\b/.test(p)) return "rgba(251,146,60,0.05)"
  if (/\b(portrait|headshot|face|person)\b/.test(p)) return "rgba(168,85,247,0.04)"
  return "transparent"
}

// P8: Portrait-like prompt detection
const PORTRAIT_KEYWORDS = /portrait|headshot|face|person|selfie|bust|close.?up/i
function isPortraitLike(prompt: string): boolean {
  return PORTRAIT_KEYWORDS.test(prompt.trim())
}

export default function GeneratePage() {
  const [prompt, setPrompt] = useState("")
  const [userPrompt, setUserPrompt] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [result, setResult] = useState<GenerationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedDimension, setSelectedDimension] = useState<DimensionPreset>(DIMENSION_PRESETS[0])
  const [sizeMode, setSizeMode] = useState<"preset" | "custom">("preset")
  const [customWidth, setCustomWidth] = useState<number>(1024)
  const [customHeight, setCustomHeight] = useState<number>(1024)
  const [qualityTier, setQualityTier] = useState<string>("balanced")
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
  // New state: creation mode, poster text fields, advanced panel, result details
  const [creationMode, setCreationMode] = useState<CreationMode>("image")
  const [posterHeadline, setPosterHeadline] = useState("")
  const [posterSubtitle, setPosterSubtitle] = useState("")
  const [posterCta, setPosterCta] = useState("")
  const [negativePrompt, setNegativePrompt] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showFullPrompt, setShowFullPrompt] = useState(false)
  const [copiedPrompt, setCopiedPrompt] = useState(false)
  // Edit-existing-image mode (inline within Image/Poster)
  const [editMode, setEditMode] = useState(false)
  const [editSourceImage, setEditSourceImage] = useState<string | null>(null)
  const [editSourceUrl, setEditSourceUrl] = useState<string>("")
  const editFileInputRef = useRef<HTMLInputElement>(null)
  // Advanced edit modal + logo overlay modal
  const [showEditModal, setShowEditModal]   = useState(false)
  const [showLogoModal, setShowLogoModal]   = useState(false)
  const stageTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
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


  const canGenerate = (editMode
    ? (editSourceUrl.length > 0 && prompt.trim().length >= 3)
    : prompt.trim().length >= 3
  ) && !isGenerating
  const promptTint = useMemo(() => getPromptTint(prompt), [prompt])

  // Build final prompt: for poster mode, append text fields automatically
  const buildFinalPrompt = useCallback((base: string): string => {
    if (creationMode !== "poster") return base.trim()
    let p = base.trim()
    const textParts: string[] = []
    if (posterHeadline.trim()) textParts.push(`text '${posterHeadline.trim()}'`)
    if (posterSubtitle.trim()) textParts.push(`text '${posterSubtitle.trim()}'`)
    if (posterCta.trim()) textParts.push(`text '${posterCta.trim()}'`)
    if (textParts.length > 0) {
      p = `${p} poster with ${textParts.join(" and ")}`
    }
    return p
  }, [creationMode, posterHeadline, posterSubtitle, posterCta])

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

    const genDims = sizeMode === "custom"
      ? { width: Math.round(customWidth / 64) * 64, height: Math.round(customHeight / 64) * 64 }
      : { width: selectedDimension.width, height: selectedDimension.height }
    setUserPrompt(rawPrompt.trim())
    setGenerationDimension({ ...selectedDimension, width: genDims.width, height: genDims.height })
    setIsGenerating(true)
    setError(null)
    setResult(null)
    setFeedbackGiven(null)
    setBriefData(null)
    setSseStage("intent")
    setGenerateShimmer(true)
    setGenStage(0)
    setGenProgress(SSE_STAGES.intent.pct)
    setTimeout(() => setGenerateShimmer(false), 800)

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
        body: JSON.stringify({
          prompt: finalPrompt.trim(),
          width: genDims.width,
          height: genDims.height,
          quality: qualityTier,
          style: selectedStyle !== "Auto" ? selectedStyle : undefined,
          reference_image: referenceImage || undefined,
          negative_prompt: negativePrompt.trim() || undefined,
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
          const data: any = JSON.parse(dataMatch[1])

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

          } else if (event === "final_ready") {
            setSseStage("done")
            setGenProgress(100)
            setResult({
              success: true,
              image_url: data.image_url,
              enhanced_prompt: data.enhanced_prompt,
              detected_settings: {
                style: "Professional",
                mood: data.brief?.mood || "Cinematic",
                lighting: data.brief?.lighting?.split(",")[0] || "Natural",
                quality: "Premium",
                category: data.capability_bucket || "photo",
              },
              model_used: data.model_used,
              total_time: data.total_time,
              quality_score: data.quality_score,
              generationId: data.generationId,
              creative_os: data.creative_os,
            })

          } else if (event === "error") {
            throw new Error(data.message || "Generation failed")
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setIsGenerating(false)
      if (stageTimerRef.current) clearTimeout(stageTimerRef.current)
    }
  }, [prompt, isGenerating, selectedDimension, sizeMode, customWidth, customHeight, qualityTier, selectedStyle, referenceImage, negativePrompt, buildFinalPrompt, toast, editMode, editSourceUrl])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && canGenerate) {
      e.preventDefault()
      handleGenerate()
    }
  }

  const handleReset = () => {
    setResult(null)
    setError(null)
    setUserPrompt("")
    setReferenceImage(null)
  }

  const handleReferenceImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file?.type.startsWith("image/")) return
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
    }
  }, [])

  // ── P3: Feedback (thumbs up/down) ─────────────────────────────────────────
  const [feedbackGiven, setFeedbackGiven] = useState<"up" | "down" | null>(null)

  const handleFeedback = async (thumbs: "up" | "down") => {
    if (!result) return
    setFeedbackGiven(thumbs)
    try {
      await fetch("/api/preferences/thumbs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          generationId: result.generationId ?? "",
          imageUrl: result.image_url ?? "",
          thumbs,
          style: selectedStyle,
          bucket: result.creative_os?.intent
            ? (result.creative_os.intent as { creative_type?: string }).creative_type ?? "photorealism"
            : "photorealism",
          tier: qualityTier,
        }),
      })
    } catch { /* silent — feedback is best-effort */ }
  }

  const handleDownload = () => {
    if (!result?.image_url) return
    const link = document.createElement("a")
    link.href = result.image_url
    link.download = `photogenius-${Date.now()}.png`
    link.click()
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
  }

  // Edit the generated image — open advanced edit modal
  const handleEditGeneratedImage = () => {
    if (!result?.image_url) return
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
  if (result?.image_url) {
    const aspectStyle = { aspectRatio: `${generationDimension.width}/${generationDimension.height}` }
    const ds = result.detected_settings
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

            {/* Image */}
            <motion.div
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.04 }}
              className="relative w-full rounded-2xl overflow-hidden result-card-glow border border-white/10 bg-black/20"
              style={{ ...aspectStyle, maxHeight: "78vh" }}
            >
              <Image src={result.image_url} alt="Generated" fill className="object-contain" unoptimized priority />
            </motion.div>

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
                  {result.quality_score != null && (
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
                {/* Thumbs feedback */}
                <div className="col-span-2 flex items-center gap-2">
                  <span className="text-[11px] text-muted-foreground/40 shrink-0">Rate this</span>
                  <button
                    type="button"
                    onClick={() => handleFeedback("up")}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl border text-sm font-medium transition-all",
                      feedbackGiven === "up"
                        ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-400"
                        : "border-white/[0.08] bg-white/[0.03] text-muted-foreground hover:border-emerald-500/30 hover:text-emerald-400 hover:bg-emerald-500/10"
                    )}
                  >
                    <ThumbsUp className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFeedback("down")}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl border text-sm font-medium transition-all",
                      feedbackGiven === "down"
                        ? "border-red-500/60 bg-red-500/15 text-red-400"
                        : "border-white/[0.08] bg-white/[0.03] text-muted-foreground hover:border-red-500/30 hover:text-red-400 hover:bg-red-500/10"
                    )}
                  >
                    <ThumbsDown className="h-3.5 w-3.5" />
                  </button>
                </div>
                <Button onClick={handleEditGeneratedImage} className="gap-2 rounded-xl border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 text-sm" variant="outline">
                  <Scissors className="h-3.5 w-3.5" /> Edit Image
                </Button>
                <Button onClick={() => setShowLogoModal(true)} className="gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 text-sm" variant="outline">
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
                <p className="text-[11px] text-muted-foreground/60 mt-2">
                  {qualityTier === "fast" ? "~8s" : qualityTier === "ultra" ? "~60s" : qualityTier === "quality" ? "~45s" : "~25s"} est.
                </p>
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
                    onClick={() => { setCreationMode(id); setEditMode(false); clearEditSource() }}
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

            {/* Prompt card */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.04 }}
              className="relative rounded-2xl prompt-hero-box overflow-hidden"
            >
              {promptTint !== "transparent" && (
                <div
                  className="absolute inset-0 pointer-events-none transition-opacity duration-500"
                  style={{ background: promptTint }}
                />
              )}

              {/* Textarea row */}
              <div className="relative p-4 pb-3">
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
                    className="btn-press mt-1 h-9 w-9 rounded-[12px] flex items-center justify-center shrink-0 bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 disabled:opacity-50 transition-all"
                    title="Add reference image"
                  >
                    <Plus className="h-4 w-4" />
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
                    className="flex-1 resize-none bg-transparent px-1 py-1 text-[16px] font-medium leading-relaxed outline-none placeholder:text-muted-foreground/50 disabled:opacity-50 min-h-[140px] max-h-[260px]"
                  />
                  <button
                    type="button"
                    onClick={toggleVoice}
                    disabled={isGenerating}
                    className={cn(
                      "btn-press mt-1 h-9 w-9 rounded-[12px] flex items-center justify-center shrink-0 disabled:opacity-50 transition-colors",
                      isListening
                        ? "bg-red-500/20 text-red-400 border border-red-500/30"
                        : "bg-white/[0.05] text-muted-foreground border border-white/[0.08] hover:text-foreground hover:bg-white/10"
                    )}
                    title={isListening ? "Stop voice input" : "Voice input"}
                  >
                    {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
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
              <div className="border-t border-white/[0.06] px-4 py-2 flex items-center gap-2">
                <input ref={editFileInputRef} type="file" accept="image/*" onChange={handleEditImageSelect} className="hidden" />
                <button
                  type="button"
                  onClick={() => { setEditMode(!editMode); if (editMode) clearEditSource() }}
                  disabled={isGenerating}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all",
                    editMode
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-white/[0.08] bg-white/[0.04] text-muted-foreground hover:text-foreground hover:border-white/15"
                  )}
                >
                  <Scissors className="h-3 w-3" />
                  Edit existing
                </button>
                <div className="flex-1" />
                <span className={cn(
                  "text-[10px] tabular-nums transition-colors",
                  prompt.length > 1800 ? "text-amber-400" : "text-muted-foreground/40"
                )}>
                  {prompt.length}/2000
                </span>
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

            {/* Poster Text Fields */}
            <AnimatePresence>
              {creationMode === "poster" && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="rounded-2xl border border-white/[0.08] bg-white/[0.025] p-4 space-y-3">
                    <p className="flex items-center gap-2 text-xs font-semibold text-foreground/80">
                      <Type className="h-3.5 w-3.5 text-primary" /> Poster Text
                    </p>
                    <div className="grid grid-cols-1 gap-2">
                      <input
                        type="text"
                        value={posterHeadline}
                        onChange={(e) => setPosterHeadline(e.target.value)}
                        placeholder="Headline — SUMMER SALE"
                        disabled={isGenerating}
                        className="px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-primary/40 focus:bg-primary/5 disabled:opacity-50 transition-colors"
                      />
                      <input
                        type="text"
                        value={posterSubtitle}
                        onChange={(e) => setPosterSubtitle(e.target.value)}
                        placeholder="Subtitle — Up to 50% OFF"
                        disabled={isGenerating}
                        className="px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-primary/40 focus:bg-primary/5 disabled:opacity-50 transition-colors"
                      />
                      <input
                        type="text"
                        value={posterCta}
                        onChange={(e) => setPosterCta(e.target.value)}
                        placeholder="CTA — Shop Now"
                        disabled={isGenerating}
                        className="px-3 py-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-primary/40 focus:bg-primary/5 disabled:opacity-50 transition-colors"
                      />
                    </div>
                    <p className="text-[10px] text-muted-foreground/50">AI renders these as professional poster text with effects</p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* ── Inspirations ── */}
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.07 }}>
              <p className="text-[11px] font-semibold text-muted-foreground/55 uppercase tracking-wider mb-2.5">
                {creationMode === "poster" ? "Poster Templates" : "Inspirations"}
              </p>
              <div className="overflow-x-auto no-scrollbar flex gap-2 px-1 py-1">
                {(creationMode === "poster" ? POSTER_SUGGESTION_CARDS : SUGGESTION_CARDS).map((item) => (
                  <motion.button
                    key={item.id}
                    onClick={() => handleSuggestionClick(item)}
                    whileTap={{ scale: 0.97 }}
                    className={cn(
                      "shrink-0 flex items-center gap-2 px-3 py-2 rounded-xl border border-white/[0.07] bg-white/[0.025] hover:bg-white/[0.06] hover:border-white/[0.14] transition-all",
                      suggestionFilling && prompt === item.prompt && "ring-1 ring-primary/50"
                    )}
                  >
                    <span className="text-base">{item.emoji}</span>
                    <span className="text-xs font-medium text-foreground/80 whitespace-nowrap">{item.label}</span>
                  </motion.button>
                ))}
              </div>
            </motion.div>

            {/* ── Aspect Ratio + Quality — 2-column same row ── */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
              <div className="grid grid-cols-2 gap-3 items-start">

                {/* Aspect Ratio */}
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-muted-foreground/55 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <ImageIcon className="h-3 w-3" /> Aspect
                  </p>
                  <div className="flex gap-1.5 overflow-x-auto no-scrollbar px-1 py-1">
                    {DIMENSION_PRESETS.map((preset) => {
                      const isSel = sizeMode === "preset" && selectedDimension.label === preset.label
                      const isAuto = preset.aspect === "auto"
                      const [w, h] = isAuto ? [1, 1] : preset.aspect.split(":").map(Number)
                      const ratio = w / h
                      const base = 18
                      const boxW = ratio >= 1 ? base : Math.round(base * ratio)
                      const boxH = ratio >= 1 ? Math.round(base / ratio) : base
                      return (
                        <button
                          key={preset.label}
                          type="button"
                          onClick={() => { setSelectedDimension(preset); setSizeMode("preset") }}
                          className={cn(
                            "shrink-0 flex flex-col items-center gap-1.5 px-2.5 py-2.5 rounded-xl border transition-all",
                            isSel
                              ? "border-primary bg-primary/15 text-primary"
                              : "border-white/[0.08] bg-white/[0.03] text-muted-foreground hover:text-foreground hover:bg-white/[0.06] hover:border-white/15"
                          )}
                        >
                          {isAuto ? (
                            <span className="flex items-center justify-center opacity-70 font-bold text-[11px]"
                              style={{ width: Math.max(base, 18), height: Math.max(base, 18) }}>✦</span>
                          ) : (
                            <span className="rounded-[3px] bg-current opacity-70 shrink-0 block"
                              style={{ width: Math.max(boxW, 9), height: Math.max(boxH, 9) }} />
                          )}
                          <span className="text-[10px] font-semibold leading-none">{preset.label}</span>
                          <span className={cn("text-[9px] leading-none", isSel ? "opacity-60" : "opacity-35")}>
                            {isAuto ? "any" : preset.aspect}
                          </span>
                        </button>
                      )
                    })}
                    {/* Custom */}
                    <button
                      type="button"
                      onClick={() => {
                        const d = sizeMode === "custom"
                          ? { width: customWidth, height: customHeight }
                          : { width: selectedDimension.width, height: selectedDimension.height }
                        setSizeMode("custom")
                        setCustomWidth(d.width)
                        setCustomHeight(d.height)
                      }}
                      className={cn(
                        "shrink-0 flex flex-col items-center gap-1.5 px-2.5 py-2.5 rounded-xl border transition-all",
                        sizeMode === "custom"
                          ? "border-primary bg-primary/15 text-primary"
                          : "border-white/[0.08] bg-white/[0.03] text-muted-foreground hover:text-foreground hover:bg-white/[0.06] hover:border-white/15"
                      )}
                    >
                      <span className="flex items-center justify-center opacity-70 font-bold text-[11px]"
                        style={{ width: 18, height: 18 }}>⊞</span>
                      <span className="text-[10px] font-semibold leading-none">Custom</span>
                      <span className={cn("text-[9px] leading-none", sizeMode === "custom" ? "opacity-60" : "opacity-35")}>W×H</span>
                    </button>
                  </div>
                </div>

                {/* Quality */}
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold text-muted-foreground/55 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                    <Zap className="h-3 w-3" /> Quality
                  </p>
                  <div className="flex gap-1.5 overflow-x-auto no-scrollbar px-1 py-1">
                    {QUALITY_OPTIONS.map((q) => {
                      const isSel = qualityTier === q.value
                      return (
                        <button
                          key={q.value}
                          type="button"
                          onClick={() => setQualityTier(q.value)}
                          className={cn(
                            "shrink-0 flex flex-col items-start gap-1.5 px-2.5 py-2.5 rounded-xl border transition-all text-left",
                            isSel
                              ? "border-primary bg-primary/15"
                              : "border-white/[0.08] bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.04]"
                          )}
                        >
                          <div className="flex items-center gap-1.5">
                            <span
                              className="h-2 w-2 rounded-full shrink-0"
                              style={{ backgroundColor: QUALITY_COLORS[q.value], opacity: isSel ? 1 : 0.35 }}
                            />
                            <span className={cn("text-xs font-semibold whitespace-nowrap leading-none", isSel ? "text-primary" : "text-foreground/75")}>{q.label}</span>
                          </div>
                          <span className={cn("text-[10px] tabular-nums whitespace-nowrap leading-none", isSel ? "text-primary/60" : "text-muted-foreground/40")}>{q.hint}</span>
                          <span className={cn("text-[9px] whitespace-nowrap leading-none", isSel ? "text-primary/40" : "text-muted-foreground/30")}>{q.note}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>

              </div>

              {/* Custom W×H steppers — full width, slides down below the 2-col grid */}
              <AnimatePresence>
                {sizeMode === "custom" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    {(() => {
                      const snap64 = (v: number) => Math.min(2048, Math.max(64, Math.round(v / 64) * 64))
                      return (
                        <div className="mt-3 space-y-2">
                          <div className="flex items-center gap-3">
                            {/* Width */}
                            <div className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.03] p-2.5">
                              <p className="text-[9px] text-muted-foreground/50 font-semibold uppercase tracking-wider mb-1.5">Width</p>
                              <div className="flex items-center gap-1.5">
                                <button type="button" onClick={() => setCustomWidth(w => snap64(w - 64))}
                                  className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0">−</button>
                                <input
                                  type="number" value={customWidth} min={64} max={2048} step={64}
                                  onChange={(e) => setCustomWidth(Number(e.target.value))}
                                  onBlur={(e) => setCustomWidth(snap64(Number(e.target.value)))}
                                  className="flex-1 min-w-0 text-center text-sm font-semibold text-foreground bg-transparent outline-none tabular-nums"
                                />
                                <button type="button" onClick={() => setCustomWidth(w => snap64(w + 64))}
                                  className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0">+</button>
                              </div>
                            </div>
                            <span className="text-muted-foreground/40 text-sm font-bold shrink-0">×</span>
                            {/* Height */}
                            <div className="flex-1 rounded-xl border border-white/[0.08] bg-white/[0.03] p-2.5">
                              <p className="text-[9px] text-muted-foreground/50 font-semibold uppercase tracking-wider mb-1.5">Height</p>
                              <div className="flex items-center gap-1.5">
                                <button type="button" onClick={() => setCustomHeight(h => snap64(h - 64))}
                                  className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0">−</button>
                                <input
                                  type="number" value={customHeight} min={64} max={2048} step={64}
                                  onChange={(e) => setCustomHeight(Number(e.target.value))}
                                  onBlur={(e) => setCustomHeight(snap64(Number(e.target.value)))}
                                  className="flex-1 min-w-0 text-center text-sm font-semibold text-foreground bg-transparent outline-none tabular-nums"
                                />
                                <button type="button" onClick={() => setCustomHeight(h => snap64(h + 64))}
                                  className="h-7 w-7 rounded-lg bg-white/[0.05] border border-white/[0.08] text-foreground/70 hover:bg-white/10 hover:text-foreground flex items-center justify-center text-base font-bold transition-all shrink-0">+</button>
                              </div>
                            </div>
                          </div>
                          <p className="text-[10px] text-muted-foreground/35 px-1">Steps of 64px · max 2048px · values auto-snap on blur</p>
                        </div>
                      )
                    })()}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>

            {/* ── Style — single unified filmstrip, all options ── */}
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.09 }}>
              <p className="text-[11px] font-semibold text-muted-foreground/55 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                <Palette className="h-3 w-3" /> Style
              </p>
              <div className="flex gap-2 overflow-x-auto no-scrollbar px-1 py-1">
                {STYLE_ALL.map(({ id, icon: Icon, label, from, to }) => {
                  const isSel = selectedStyle === id
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setSelectedStyle(id)}
                      className={cn(
                        "relative shrink-0 w-[68px] h-[90px] rounded-xl overflow-hidden border transition-all",
                        isSel
                          ? "border-primary ring-1 ring-primary/40 scale-[1.05]"
                          : "border-white/[0.1] hover:border-white/25 hover:scale-[1.02]"
                      )}
                    >
                      <div className="absolute inset-0" style={{ background: `linear-gradient(160deg, ${from}, ${to})` }} />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Icon className="h-5 w-5 text-white/55" />
                      </div>
                      <div className="absolute bottom-0 left-0 right-0 pb-2 pt-4 text-center bg-gradient-to-t from-black/80 via-black/30 to-transparent">
                        <span className="text-[10px] font-semibold text-white/90 leading-none">{label}</span>
                      </div>
                      {isSel && (
                        <div className="absolute top-1.5 right-1.5 h-3.5 w-3.5 rounded-full bg-primary flex items-center justify-center shadow-sm">
                          <Check className="h-2 w-2 text-white" />
                        </div>
                      )}
                    </button>
                  )
                })}
              </div>
            </motion.div>

            {/* ── Advanced ── */}
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.12 }}
              className="rounded-xl border border-white/[0.07] bg-white/[0.015] overflow-hidden"
            >
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 px-4 py-2.5 text-[11px] font-semibold text-muted-foreground/60 hover:text-foreground/80 w-full uppercase tracking-wider"
              >
                <SlidersHorizontal className="h-3 w-3" />
                Advanced
                <div className="flex-1" />
                {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
              <AnimatePresence>
                {showAdvanced && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden border-t border-white/[0.06]"
                  >
                    <div className="p-3 space-y-2">
                      <textarea
                        value={negativePrompt}
                        onChange={(e) => setNegativePrompt(e.target.value)}
                        placeholder="What to avoid — blurry, low quality, text..."
                        rows={2}
                        disabled={isGenerating}
                        className="w-full px-3 py-2 rounded-xl bg-white/[0.04] border border-white/[0.08] text-xs text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-primary/30 resize-none disabled:opacity-50"
                      />
                      <p className="text-[10px] text-muted-foreground/40 flex items-center gap-1.5">
                        <Sparkles className="h-3 w-3 shrink-0" /> AI auto-adds quality negatives.
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>

          </div>{/* end LEFT COLUMN */}

        </div>{/* end grid */}
      </div>{/* end max-w wrapper */}

      {/* ── Sticky Generate Bar ── */}
      <div className="fixed bottom-0 left-0 lg:left-60 right-0 z-40 pointer-events-none">
        <div className="pointer-events-auto max-w-4xl mx-auto px-3 sm:px-4 pb-3 sm:pb-4" style={{ paddingBottom: "max(12px, env(safe-area-inset-bottom, 12px))" }}>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="rounded-2xl border border-white/[0.1] bg-background/85 backdrop-blur-xl p-3 flex items-center gap-3 shadow-2xl shadow-black/40"
          >
            <Button
              onClick={() => handleGenerate()}
              disabled={!canGenerate}
              className={cn(
                "btn-press w-full px-6 py-5 text-base rounded-[14px] btn-generate-hero",
                generateShimmer && "shimmer"
              )}
            >
              {isGenerating ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {editMode ? "Editing..." : "Creating..."}
                </span>
              ) : (
                editMode ? "✦ Apply Edit" : creationMode === "poster" ? "✦ Generate Poster" : "✦ Generate Image"
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
