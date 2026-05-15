"use client";

/**
 * /editor — AI photo editor.
 *
 * UI layout ported from the Lumen reference (apps/webs/src/routes/edit.tsx):
 * 3-pane — tool rail · canvas (checker bg + zoom toolbar) · layers + sources.
 *
 * Functionality wired to Pixium's backend:
 *  - Source image: picked from /api/generations, uploaded via /api/upload, or
 *    arrives via ?image= query param (from the Generate page "Edit" action).
 *  - Each AI tool maps to a Pixium edit_mode and calls POST /api/generate/edit.
 *  - Export downloads the current edited image.
 *  - Edit history kept in-memory for undo/redo.
 *
 * The poster-pack Fabric.js editor lives separately at /editor/[projectId].
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Brush, Eraser, Square, Layers as LayersIcon, Wand2, Undo2, Redo2,
  Image as ImageIcon, Type, Shapes, Stamp, UserRoundCog, Scissors,
  Palette, Expand, Sparkles, Download, Maximize, Minus, Plus,
  Upload, Loader2, AlertCircle, Eraser as RemoveIcon, Combine, Zap, Smile, ArrowUpToLine,
} from "lucide-react";

// ── Tool model ────────────────────────────────────────────────────────────────
type ToolId =
  | "brush" | "erase" | "rect"
  | "bg" | "removebg" | "person" | "restyle" | "expand" | "color"
  | "text" | "object" | "logo" | "removeobj" | "compose" | "inpaint";

// Map each AI tool to a Pixium edit_mode (see /api/generate/edit VALID_EDIT_MODES).
// Note: "upscale" is special — it uses /api/generate/upscale, not /edit.
const TOOL_EDIT_MODE: Partial<Record<ToolId, string>> = {
  bg: "background_swap",
  removebg: "background_swap",
  person: "instruction_edit",
  restyle: "style_remix",
  expand: "instruction_edit",
  color: "instruction_edit",
  text: "text_replace",
  object: "object_add",
  // "logo" handled separately via /api/logo-overlay
  removeobj: "object_remove",
  compose: "compose",
  inpaint: "inpaint_mask",
};

const UPSCALE_SCALES = [2, 4];

// Logo overlay — 9-position grid (matches /api/logo-overlay positions)
const LOGO_POSITIONS = [
  "top_left", "top_center", "top_right",
  "center_left", "center", "center_right",
  "bottom_left", "bottom_center", "bottom_right",
] as const;
const LOGO_POSITION_LABELS: Record<string, string> = {
  top_left: "↖", top_center: "↑", top_right: "↗",
  center_left: "←", center: "◎", center_right: "→",
  bottom_left: "↙", bottom_center: "↓", bottom_right: "↘",
};

// One-click quick actions (fixed prompt + mode) — ported from edit-image-modal.tsx
const QUICK_ACTIONS: { id: string; label: string; icon: typeof Zap; mode: string; instruction: string }[] = [
  { id: "enhance", label: "Auto-Enhance", icon: Zap, mode: "instruction_edit",
    instruction: "enhance overall quality: boost color vibrancy, sharpen fine details, improve lighting and contrast, fix any blur, professional photography finish" },
  { id: "clean_bg", label: "Clean BG", icon: ImageIcon, mode: "background_swap",
    instruction: "clean seamless studio white background, subject cleanly isolated, soft contact shadow" },
  { id: "fix_faces", label: "Fix Faces", icon: Smile, mode: "instruction_edit",
    instruction: "fix any facial distortions, ensure natural skin texture, correct eye alignment and catchlights, realistic features" },
];

// Theme presets for Restyle — ported from edit-image-modal.tsx
const THEME_PRESETS: { label: string; prompt: string }[] = [
  { label: "Cinematic",     prompt: "cinematic film still, teal-orange color grade, 35mm lens, shallow depth of field, dramatic moody lighting" },
  { label: "Anime",         prompt: "anime illustration, cel-shaded, vibrant colors, expressive line art, studio-quality" },
  { label: "Watercolor",    prompt: "soft watercolor painting, paper texture, delicate brush strokes, pastel palette" },
  { label: "Oil Painting",  prompt: "classical oil painting, rich thick brush strokes, dramatic chiaroscuro lighting, museum quality" },
  { label: "Cyberpunk",     prompt: "cyberpunk neon aesthetic, synthwave palette, chrome and holograms, rainy night city" },
  { label: "Vintage 70s",   prompt: "vintage 1970s photograph, warm film grain, faded color, nostalgic mood, Kodachrome" },
  { label: "3D Pixar",      prompt: "Pixar-style 3D render, soft global illumination, expressive features, cinematic composition" },
  { label: "Minimal",       prompt: "minimalist design, vast negative space, single accent color, clean geometric composition" },
  { label: "Pencil Sketch", prompt: "detailed graphite pencil sketch, cross-hatching, subtle shading, artistic line work" },
  { label: "Pop Art",       prompt: "pop art, bold outlines, halftone dot patterns, saturated primary colors, Lichtenstein-inspired" },
  { label: "Black & White", prompt: "high-contrast black and white photography, dramatic shadows, film noir mood, tri-x grain" },
  { label: "Vaporwave",     prompt: "vaporwave aesthetic, pastel pink and teal, retro 80s CRT glow, dreamlike mood" },
  { label: "Studio Ghibli", prompt: "Studio Ghibli hand-painted animation style, soft watercolor backgrounds, warm whimsical atmosphere" },
  { label: "Lego Blocks",   prompt: "render the scene built entirely out of Lego bricks, studio product-photo lighting" },
  { label: "Claymation",    prompt: "stop-motion claymation style, visible fingerprints in clay, charming handmade feel" },
  { label: "Pixel Art",     prompt: "16-bit pixel art, limited palette, crisp pixels, retro video-game aesthetic" },
];

const BRUSH_SIZES = [8, 16, 28, 44];
const MAX_EXTRAS = 3;
const MAX_COMPOSE_REFS = 4;
type MaskTool = "brush" | "circle" | "rect" | "eraser";

// Per-tool capability matrix: which universal features (mask, reference, prompt) are available
// and whether each is "required" (must use before Apply) or "optional" (helpful but skippable).
// "off" means hide that section entirely for this tool.
type CapLevel = "off" | "optional" | "required";
const TOOL_CAPS: Record<ToolId, { mask: CapLevel; reference: CapLevel; prompt: CapLevel; maxRefs?: number }> = {
  brush:     { mask: "required", reference: "off",      prompt: "off" },
  erase:     { mask: "required", reference: "off",      prompt: "off" },
  rect:      { mask: "required", reference: "off",      prompt: "off" },
  inpaint:   { mask: "required", reference: "optional", prompt: "required" },
  bg:        { mask: "optional", reference: "optional", prompt: "required" },
  removebg:  { mask: "off",      reference: "off",      prompt: "optional" },
  person:    { mask: "optional", reference: "optional", prompt: "required" },
  restyle:   { mask: "off",      reference: "optional", prompt: "required" },
  expand:    { mask: "off",      reference: "off",      prompt: "required" },
  color:     { mask: "off",      reference: "optional", prompt: "required" },
  text:      { mask: "optional", reference: "optional", prompt: "required" },
  object:    { mask: "optional", reference: "optional", prompt: "required" },
  logo:      { mask: "off",      reference: "off",      prompt: "off" }, // logo uses its own upload + position UI
  removeobj: { mask: "required", reference: "off",      prompt: "required" },
  compose:   { mask: "off",      reference: "required", prompt: "required", maxRefs: MAX_COMPOSE_REFS },
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const TOOL_GROUPS: { label: string; tools: { id: ToolId; icon: any; label: string }[] }[] = [
  {
    label: "Mask",
    tools: [
      { id: "inpaint", icon: Brush, label: "Inpaint" },
    ],
  },
  {
    label: "AI",
    tools: [
      { id: "bg", icon: ImageIcon, label: "Background" },
      { id: "removebg", icon: Scissors, label: "Remove BG" },
      { id: "person", icon: UserRoundCog, label: "Swap person" },
      { id: "restyle", icon: Sparkles, label: "Restyle" },
      { id: "expand", icon: Expand, label: "Outpaint" },
      { id: "color", icon: Palette, label: "Color grade" },
    ],
  },
  {
    label: "Add / Remove",
    tools: [
      { id: "text", icon: Type, label: "Text" },
      { id: "object", icon: Shapes, label: "Object" },
      { id: "logo", icon: Stamp, label: "Logo" },
      { id: "removeobj", icon: RemoveIcon, label: "Remove obj" },
      { id: "compose", icon: Combine, label: "Compose" },
    ],
  },
];

const TOOL_PANELS: Record<ToolId, { title: string; hint: string; chips?: string[]; placeholder?: string }> = {
  brush:    { title: "Brush",          hint: "Paint a mask over the area you want to change. (Mask-aware editing is applied to your instruction.)" },
  erase:    { title: "Erase",          hint: "Erase parts of the mask." },
  rect:     { title: "Region",         hint: "Drag a rectangular selection." },
  inpaint:  { title: "Inpaint",        hint: "Paint a mask over an area, then describe what should replace it. Optionally upload a reference for the fill.", chips: [
    "A wooden table surface with soft natural shadows",
    "A modern marble countertop with subtle veining",
    "Lush green grass with a few scattered wildflowers",
    "A clean studio backdrop in matching tones",
    "Smooth concrete floor with subtle texture",
  ], placeholder: "Fill the masked area with a wooden table surface" },
  bg:       { title: "Background",     hint: "Describe the new scene behind the subject. Optionally upload a reference image of the background you want.", chips: [
    "A cinematic mountain lake at golden-hour sunrise",
    "Neon-lit Tokyo street at dusk, shallow depth of field",
    "Vast Sahara desert dunes with long shadows",
    "A soft pastel studio gradient, minimalist",
    "Misty pine forest with morning fog rolling in",
  ], placeholder: "Replace the background with a cinematic mountain lake at sunrise…" },
  removebg: { title: "Remove background", hint: "Cut the subject onto a clean / transparent backdrop.", chips: [
    "Pure white studio with soft contact shadow",
    "Transparent background, edges feathered cleanly",
    "Solid black background, high-contrast cutout",
    "Light gradient (light gray to white) for product shots",
  ], placeholder: "Remove the background, keep the subject on a clean white studio backdrop" },
  person:   { title: "Swap person",    hint: "Describe the new subject. Optionally upload a reference photo of the person/look you want.", chips: [
    "A woman in her 30s, freckles, candid smile, natural light",
    "A businessman in his 40s, crisp suit, confident posture",
    "An elderly grandmother with warm smile and silver hair",
    "A teenager in casual streetwear, urban setting",
    "A toddler with curly hair, joyful expression",
  ], placeholder: "Replace the person with a woman in her 30s, freckles, candid smile, natural light" },
  restyle:  { title: "Restyle",        hint: "Apply a new visual language. Optionally upload a reference image whose style you want to match.", chips: [
    "Wong Kar-wai cinematic — saturated neon and rain",
    "Studio Ghibli hand-painted animation style",
    "Annie Leibovitz editorial portrait — dramatic light",
    "Wes Anderson symmetrical, pastel palette",
    "Y2K chrome and holographic aesthetic",
    "Risograph print — textured grain, limited palette",
  ], placeholder: "Restyle in the look of…" },
  expand:   { title: "Outpaint",       hint: "Extend the canvas / scene outward.", chips: [
    "Extend the scene to the left and right, continuing naturally",
    "Add more sky and atmospheric space above the subject",
    "Reveal more of the environment behind the subject",
    "Widen to a cinematic 16:9 frame, preserving composition",
  ], placeholder: "Extend the scene to the left and right, continuing the environment naturally" },
  color:    { title: "Color grade",    hint: "Adjust mood with a cinematic grade. Optionally upload a reference image whose color palette you want to match.", chips: [
    "Teal and orange Hollywood blockbuster grade",
    "Bleach bypass — desaturated, high-contrast film look",
    "Warm Kodachrome film grain with vintage tones",
    "Cool noir — deep shadows, blue highlights",
    "Soft warm film stock, pastel highlights",
  ], placeholder: "Apply a teal-and-orange cinematic color grade" },
  text:     { title: "Add / replace text", hint: 'Describe the text to add or replace. Tip: put exact text in "quotes".', chips: [
    'Add the headline "Pure Energy" in bold sans-serif, top-left',
    'Add "Limited Edition" in elegant gold serif at the bottom',
    'Place "50% OFF" as a bold red badge in the top-right',
    'Add the tagline "Stay Wild" in handwritten script across the center',
    'Add a small "NEW" pill badge in the corner',
  ], placeholder: 'Add the headline "Pure Energy" in bold sans-serif, top-left' },
  object:   { title: "Add object",     hint: "Insert a new object, logo, or image into the scene. Upload references (optional) and describe placement.", chips: [
    "A weathered leather satchel resting on the desk",
    "A vintage film camera placed beside the subject",
    "A bouquet of soft pink peonies in a glass vase",
    "A crystal whisky glass with amber liquid",
    "A glowing neon sign on the wall behind the subject",
  ], placeholder: "Add a weathered leather satchel on the desk" },
  logo:     { title: "Logo overlay",   hint: "Upload a logo (PNG/SVG, transparent recommended), then place & scale it on the image." },
  removeobj:{ title: "Remove object",  hint: "Paint a mask over the object, then describe what to remove (so the AI knows what to keep, e.g. background).", chips: [
    "Remove the person on the left and fill in naturally",
    "Remove the watermark in the bottom-right corner",
    "Remove the lamp post on the right side of the frame",
    "Remove the background clutter behind the subject",
    "Remove the text overlay and restore the original scene",
  ], placeholder: "Remove the lamp post on the right and fill in naturally" },
  compose:  { title: "Compose",        hint: "Combine this image with one or more reference images. Pick up to 4 from the Source panel, then describe the composition.", chips: [
    "Place the product from ref 1 onto the surface in ref 2",
    "Blend the lighting of ref 1 with the subject of ref 2",
    "Composite the subject into the environment from ref 1",
    "Match the color palette of ref 1 across the scene",
  ], placeholder: "Place the product from ref 1 onto the surface in ref 2, matching the lighting" },
};

interface SourceImage { id: string; src: string; prompt?: string }

const QUALITIES = [
  { id: "1k", name: "1K" },
  { id: "2k", name: "2K" },
  { id: "4k", name: "4K" },
];

export default function Editor() {
  const search = useSearchParams();
  const [tool, setTool] = useState<ToolId>("bg");
  const [prompt, setPrompt] = useState("");
  const [quality, setQuality] = useState("1k");
  const [upscaleScale, setUpscaleScale] = useState<number | null>(null);
  // Right inspector tab: "controls" shows tool settings, "history" shows history+sources
  const [inspectorTab, setInspectorTab] = useState<"controls" | "history">("controls");
  // Past generations (cross-session) for History tab
  const [pastGens, setPastGens] = useState<{ id: string; url: string; prompt: string }[]>([]);
  const [pastGensLoading, setPastGensLoading] = useState(false);
  // Logo overlay state
  const [logoData, setLogoData] = useState<string | null>(null);
  const [logoPosition, setLogoPosition] = useState<string>("bottom_right");
  const [logoSize, setLogoSize] = useState(20);
  const [logoOpacity, setLogoOpacity] = useState(90);
  const logoFileRef = useRef<HTMLInputElement>(null);
  const [zoom, setZoom] = useState<"fit" | number>("fit");

  // Source image + history (history[0] = oldest, last = current)
  const [history, setHistory] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState(-1);
  const current = histIdx >= 0 ? history[histIdx] : null;

  const [sources, setSources] = useState<SourceImage[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modelInfo, setModelInfo] = useState<string>("");
  // Compose mode: reference image URLs picked from the gallery (up to 4)
  const [composeRefs, setComposeRefs] = useState<string[]>([]);
  // Uploaded reference images (data URLs) for object/logo/compose — sent as extra_image_urls
  const [uploadedExtras, setUploadedExtras] = useState<string[]>([]);
  // Mask drawing tool (active when a MASK_TOOLS tool is selected)
  const [maskTool, setMaskTool] = useState<MaskTool>("brush");
  const [brushSize, setBrushSize] = useState(16);
  const [hasMask, setHasMask] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const extraFileRef = useRef<HTMLInputElement>(null);
  // Canvas refs for masking
  const imgRef = useRef<HTMLImageElement>(null);
  const maskCanvasRef = useRef<HTMLCanvasElement>(null);   // black/white mask (offscreen-ish)
  const displayCanvasRef = useRef<HTMLCanvasElement>(null); // red overlay shown to user
  const isDrawingRef = useRef(false);
  const shapeStartRef = useRef<{ x: number; y: number } | null>(null);
  const snapshotRef = useRef<ImageData | null>(null);

  const panel = TOOL_PANELS[tool];
  const zoomLabel = zoom === "fit" ? "Fit" : `${zoom}%`;
  const canUndo = histIdx > 0;
  const canRedo = histIdx >= 0 && histIdx < history.length - 1;
  const isAiTool = !!TOOL_EDIT_MODE[tool];
  const caps = TOOL_CAPS[tool] ?? { mask: "off", reference: "off", prompt: "off" };
  const isMaskMode = caps.mask !== "off";
  const isExtrasMode = caps.reference !== "off";
  const isInpaint = tool === "inpaint";
  const maskRequired = caps.mask === "required";
  const refRequired = caps.reference === "required";
  const maxRefsForTool = caps.maxRefs ?? MAX_EXTRAS;

  // Set initial source from ?image= and initial tool from ?tool=
  useEffect(() => {
    const q = search?.get("image");
    if (q) {
      setHistory([q]);
      setHistIdx(0);
    }
    const t = search?.get("tool") as ToolId | null;
    if (t && TOOL_GROUPS.some((g) => g.tools.some((x) => x.id === t))) {
      setTool(t);
    }
  }, [search]);

  useEffect(() => {
    (async () => {
      setPastGensLoading(true);
      try {
        const res = await fetch("/api/generations?limit=60");
        if (res.ok) {
          const data = await res.json();
          const items = (Array.isArray(data) ? data : data.generations || data.items || []) as Array<{
            id: string;
            imageUrl?: string;
            image_url?: string;
            selectedUrl?: string;
            outputUrls?: string[];
            previewUrl?: string;
            prompt?: string;
            originalPrompt?: string;
          }>;
          const mapped = items
            .map((g) => ({
              id: g.id,
              src: g.selectedUrl || (g.outputUrls && g.outputUrls[0]) || g.previewUrl || g.imageUrl || g.image_url || "",
              prompt: g.prompt || g.originalPrompt || "",
            }))
            .filter((g) => g.src);
          setSources(mapped.slice(0, 18));
          setPastGens(mapped.map((m) => ({ id: m.id, url: m.src, prompt: m.prompt })));
          // If nothing picked yet, default to the first source
          setHistory((prev) => (prev.length === 0 && mapped[0] ? [mapped[0].src] : prev));
          setHistIdx((i) => (i < 0 && mapped[0] ? 0 : i));
        }
      } catch {
        /* ignore */
      } finally {
        setLoadingSources(false);
        setPastGensLoading(false);
      }
    })();
  }, []);

  const pickSource = (src: string) => {
    setHistory([src]);
    setHistIdx(0);
    setError(null);
    setModelInfo("");
  };

  const handleUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      setHistory([dataUrl]);
      setHistIdx(0);
      setError(null);
      setModelInfo("");
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }, []);

  const pushHistory = (newUrl: string) => {
    setHistory((prev) => {
      const truncated = prev.slice(0, histIdx + 1);
      return [...truncated, newUrl];
    });
    setHistIdx((i) => i + 1);
  };

  // ── Mask canvas (inpaint) ─────────────────────────────────────────────────
  const redrawMaskOverlay = useCallback(() => {
    const mask = maskCanvasRef.current;
    const display = displayCanvasRef.current;
    if (!mask || !display) return;
    const dCtx = display.getContext("2d");
    if (!dCtx) return;
    const w = display.width, h = display.height;
    dCtx.clearRect(0, 0, w, h);
    const mData = mask.getContext("2d")!.getImageData(0, 0, w, h);
    const dData = dCtx.createImageData(w, h);
    for (let i = 0; i < mData.data.length; i += 4) {
      if (mData.data[i] > 128) {
        dData.data[i] = 255; dData.data[i + 1] = 50; dData.data[i + 2] = 50; dData.data[i + 3] = 140;
      }
    }
    dCtx.putImageData(dData, 0, 0);
  }, []);

  const setupMaskCanvas = useCallback(() => {
    const img = imgRef.current;
    const mask = maskCanvasRef.current;
    const display = displayCanvasRef.current;
    if (!img || !mask || !display) return;
    const w = Math.round(img.clientWidth || img.getBoundingClientRect().width);
    const h = Math.round(img.clientHeight || img.getBoundingClientRect().height);
    if (!w || !h) {
      // Image not laid out yet — retry next frame
      requestAnimationFrame(() => setupMaskCanvas());
      return;
    }
    if (mask.width !== w || mask.height !== h) {
      mask.width = w; mask.height = h;
      display.width = w; display.height = h;
      const mCtx = mask.getContext("2d");
      if (!mCtx) return;
      mCtx.fillStyle = "black";
      mCtx.fillRect(0, 0, w, h);
      setHasMask(false);
    }
    redrawMaskOverlay();
  }, [redrawMaskOverlay]);

  // Re-init the mask canvas whenever we enter a mask mode or the image changes.
  // Runs after render so the conditionally-mounted canvases exist.
  useEffect(() => {
    if (!isMaskMode || !current) return;
    const img = imgRef.current;
    if (!img) return;
    if (img.complete) { requestAnimationFrame(() => setupMaskCanvas()); return; }
    img.onload = () => setupMaskCanvas();
  }, [isMaskMode, current, zoom, setupMaskCanvas]);

  useEffect(() => {
    if (!isMaskMode) return;
    const onResize = () => setupMaskCanvas();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [isMaskMode, setupMaskCanvas]);

  // Map a pointer event to mask-bitmap coords. Uses the VISIBLE (display) canvas
  // for the bounding rect — the mask canvas itself is hidden (rect would be 0×0).
  const getCanvasPos = (e: React.MouseEvent | React.TouchEvent) => {
    const visible = displayCanvasRef.current;
    const mask = maskCanvasRef.current;
    if (!visible || !mask) return { x: 0, y: 0 };
    const rect = visible.getBoundingClientRect();
    const src = "touches" in e ? e.touches[0] : e;
    return {
      x: (src.clientX - rect.left) * (mask.width / rect.width),
      y: (src.clientY - rect.top) * (mask.height / rect.height),
    };
  };

  const onMaskDown = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isMaskMode) return;
    e.preventDefault();
    isDrawingRef.current = true;
    const pos = getCanvasPos(e);
    const mCtx = maskCanvasRef.current!.getContext("2d")!;
    if (maskTool === "brush" || maskTool === "eraser") {
      mCtx.beginPath();
      mCtx.arc(pos.x, pos.y, brushSize / 2, 0, Math.PI * 2);
      mCtx.fillStyle = maskTool === "eraser" ? "black" : "white";
      mCtx.fill();
      setHasMask(true);
      redrawMaskOverlay();
    } else {
      shapeStartRef.current = pos;
      const c = maskCanvasRef.current!;
      snapshotRef.current = mCtx.getImageData(0, 0, c.width, c.height);
    }
  };

  const onMaskMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isMaskMode || !isDrawingRef.current) return;
    e.preventDefault();
    const pos = getCanvasPos(e);
    const mCtx = maskCanvasRef.current!.getContext("2d")!;
    if (maskTool === "brush" || maskTool === "eraser") {
      mCtx.beginPath();
      mCtx.arc(pos.x, pos.y, brushSize / 2, 0, Math.PI * 2);
      mCtx.fillStyle = maskTool === "eraser" ? "black" : "white";
      mCtx.fill();
      setHasMask(true);
      redrawMaskOverlay();
    } else if (maskTool === "circle" && shapeStartRef.current) {
      mCtx.putImageData(snapshotRef.current!, 0, 0);
      const s = shapeStartRef.current;
      mCtx.beginPath();
      mCtx.ellipse((s.x + pos.x) / 2, (s.y + pos.y) / 2, Math.abs(pos.x - s.x) / 2, Math.abs(pos.y - s.y) / 2, 0, 0, Math.PI * 2);
      mCtx.fillStyle = "white";
      mCtx.fill();
      redrawMaskOverlay();
    } else if (maskTool === "rect" && shapeStartRef.current) {
      mCtx.putImageData(snapshotRef.current!, 0, 0);
      const s = shapeStartRef.current;
      mCtx.fillStyle = "white";
      mCtx.fillRect(Math.min(s.x, pos.x), Math.min(s.y, pos.y), Math.abs(pos.x - s.x), Math.abs(pos.y - s.y));
      redrawMaskOverlay();
    }
  };

  const onMaskUp = () => {
    if (!isDrawingRef.current) return;
    isDrawingRef.current = false;
    if (maskTool === "circle" || maskTool === "rect") setHasMask(true);
    shapeStartRef.current = null;
    snapshotRef.current = null;
  };

  const clearMask = () => {
    const mask = maskCanvasRef.current;
    if (!mask) return;
    const mCtx = mask.getContext("2d")!;
    mCtx.fillStyle = "black";
    mCtx.fillRect(0, 0, mask.width, mask.height);
    setHasMask(false);
    redrawMaskOverlay();
  };

  const buildMaskDataUrl = (): string | null => {
    const mask = maskCanvasRef.current;
    const img = imgRef.current;
    if (!mask || !img) return null;
    const nw = img.naturalWidth || mask.width;
    const nh = img.naturalHeight || mask.height;
    if (nw !== mask.width || nh !== mask.height) {
      const scaled = document.createElement("canvas");
      scaled.width = nw; scaled.height = nh;
      scaled.getContext("2d")!.drawImage(mask, 0, 0, nw, nh);
      return scaled.toDataURL("image/png");
    }
    return mask.toDataURL("image/png");
  };

  // ── Uploaded reference images (any tool with reference cap !== "off") ──
  const addUploadedExtras = useCallback(async (files: FileList | null) => {
    if (!files) return;
    const cap = maxRefsForTool;
    const urls: string[] = [];
    for (const f of Array.from(files)) {
      if (uploadedExtras.length + urls.length >= cap) break;
      if (!f.type.startsWith("image/")) continue;
      const du = await new Promise<string>((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result as string);
        r.onerror = () => rej(new Error("read failed"));
        r.readAsDataURL(f);
      });
      urls.push(du);
    }
    if (urls.length) setUploadedExtras((prev) => [...prev, ...urls].slice(0, cap));
  }, [uploadedExtras.length, maxRefsForTool]);

  const removeUploadedExtra = (i: number) => setUploadedExtras((prev) => prev.filter((_, idx) => idx !== i));

  // Clear mode-specific state when switching tools
  useEffect(() => {
    setError(null);
    if (!isMaskMode) { setHasMask(false); }
    if (!isExtrasMode) { setUploadedExtras([]); }
    if (tool !== "compose") { setComposeRefs([]); }
  }, [tool]); // eslint-disable-line react-hooks/exhaustive-deps

  // Generic edit runner — used by per-tool "Apply" and one-click Quick Actions.
  const runEdit = useCallback(async (
    mode: string,
    instruction: string,
    opts?: { extraImageUrls?: string[]; maskData?: string },
  ) => {
    if (!current || applying) return false;
    if (instruction.trim().length < 3) {
      setError("Describe the edit (at least 3 characters).");
      return false;
    }
    setApplying(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        image_url: current,
        instruction: instruction.trim(),
        quality,
        edit_mode: mode,
      };
      if (opts?.extraImageUrls?.length) body.extra_image_urls = opts.extraImageUrls;
      if (opts?.maskData) body.mask_data = opts.maskData;

      const res = await fetch("/api/generate/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const rawText = await res.text();
      let data: { success?: boolean; image_url?: string; model_used?: string; total_time?: number; error?: string } = {};
      try { data = JSON.parse(rawText); }
      catch {
        const timeoutish = rawText.includes("<html") || rawText.includes("504") || rawText.includes("timeout");
        throw new Error(timeoutish ? "Edit took too long and timed out — try again or use a simpler instruction." : `Edit failed (HTTP ${res.status})`);
      }
      if (res.ok && data.success && data.image_url) {
        pushHistory(data.image_url);
        setModelInfo(`${data.model_used ?? "edit"}${data.total_time ? ` · ${Math.round(data.total_time)}s` : ""}`);
        return true;
      }
      setError(data.error || `Edit failed (${res.status})`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Edit service unavailable");
    } finally {
      setApplying(false);
    }
    return false;
  }, [current, applying, quality, histIdx]);

  const applyEdit = useCallback(async () => {
    const editMode = TOOL_EDIT_MODE[tool];
    if (!editMode) {
      setError("Pick an AI tool to apply a model edit. (Brush / Erase / Region just paint a mask.)");
      return;
    }
    // Enforce required mask (Inpaint, Remove Object)
    if (maskRequired && !hasMask) {
      setError("Paint a mask over the area to change first (Brush / Region).");
      return;
    }
    // Build reference list — uploaded refs available for any tool with reference !== "off"
    const refs = [
      ...composeRefs,
      ...(isExtrasMode ? uploadedExtras : []),
    ];
    if (refRequired && refs.length === 0) {
      setError("Add at least one reference image for this tool.");
      return;
    }
    // Mask data — send if user painted one, regardless of tool (backend ignores if not applicable)
    const maskData = hasMask ? (buildMaskDataUrl() ?? undefined) : undefined;
    const ok = await runEdit(editMode, prompt, {
      extraImageUrls: refs.length ? refs : undefined,
      maskData,
    });
    if (ok) setPrompt("");
  }, [tool, prompt, composeRefs, uploadedExtras, hasMask, maskRequired, refRequired, isExtrasMode, runEdit]);

  const runQuickAction = useCallback(async (qa: typeof QUICK_ACTIONS[number]) => {
    await runEdit(qa.mode, qa.instruction);
  }, [runEdit]); // eslint-disable-line react-hooks/exhaustive-deps

  // Upscale uses the dedicated /api/generate/upscale endpoint (scale 2/4/8/16)
  const runUpscale = useCallback(async () => {
    if (!current || applying || upscaleScale === null) return;
    setApplying(true);
    setError(null);
    try {
      const res = await fetch("/api/generate/upscale", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_url: current, scale: upscaleScale }),
      });
      const rawText = await res.text();
      let data: { success?: boolean; image_url?: string; output_url?: string; url?: string; error?: string } = {};
      try { data = JSON.parse(rawText); }
      catch {
        const timeoutish = rawText.includes("<html") || rawText.includes("504") || rawText.includes("timeout");
        throw new Error(timeoutish ? "Upscale took too long and timed out — try a smaller scale." : `Upscale failed (HTTP ${res.status})`);
      }
      const out = data.image_url || data.output_url || data.url;
      if (res.ok && (data.success ?? !!out) && out) {
        pushHistory(out);
        setModelInfo(`upscaled ${upscaleScale}×`);
        return;
      }
      setError(data.error || `Upscale failed (${res.status})`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upscale service unavailable");
    } finally {
      setApplying(false);
    }
  }, [current, applying, upscaleScale, histIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  const onLogoFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => setLogoData(reader.result as string);
    reader.readAsDataURL(f);
    e.target.value = "";
  }, []);

  const runLogoOverlay = useCallback(async () => {
    if (!current || !logoData || applying) return;
    setApplying(true);
    setError(null);
    try {
      const res = await fetch("/api/logo-overlay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_url: current,
          logo_data: logoData,
          position: logoPosition,
          size_pct: logoSize,
          opacity: logoOpacity,
        }),
      });
      const data = await res.json();
      const out = data.image_url || data.output_url || data.url;
      if (res.ok && (data.success ?? !!out) && out) {
        pushHistory(out);
        setModelInfo(`logo · ${logoPosition}`);
        return;
      }
      setError(data.error || `Logo overlay failed (${res.status})`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Logo overlay service unavailable");
    } finally {
      setApplying(false);
    }
  }, [current, logoData, logoPosition, logoSize, logoOpacity, applying, histIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleComposeRef = (src: string) => {
    setComposeRefs((prev) =>
      prev.includes(src) ? prev.filter((u) => u !== src) : prev.length < 4 ? [...prev, src] : prev,
    );
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-5rem)] max-w-7xl flex-col px-3 sm:px-4">
      <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleUpload} />

      {/* Compact header */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 py-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="kerned text-white/40">Studio</span>
          <span className="text-white/20">/</span>
          <span className="font-display">Edit</span>
          {modelInfo && (
            <>
              <span className="text-white/20">·</span>
              <span className="font-mono text-[11px] text-white/50">{modelInfo}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="glass-panel inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs"
          >
            <Upload className="h-3.5 w-3.5" aria-hidden /> Upload
          </button>
          {current && (
            <a
              href={current}
              download="pixium-edit.png"
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-black"
              style={{ background: "var(--gradient-aurora)" }}
            >
              <Download className="h-3.5 w-3.5" aria-hidden /> Export
            </a>
          )}
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 pb-3 lg:grid-cols-[88px_minmax(0,1fr)_300px]">
        {/* Tool rail */}
        <aside
          aria-label="Editing tools"
          className="glass-panel no-scrollbar order-1 flex flex-row gap-3 overflow-x-auto rounded-2xl p-2 lg:flex-col lg:overflow-y-auto"
        >
          {TOOL_GROUPS.map((g) => (
            <div key={g.label} className="flex flex-row gap-1 lg:flex-col">
              <p className="kerned hidden px-1 pt-1 text-white/40 lg:block">{g.label}</p>
              {g.tools.map((t) => {
                const Icon = t.icon;
                const active = tool === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => { setTool(t.id); setError(null); setInspectorTab("controls"); }}
                    aria-pressed={active}
                    title={t.label}
                    className={`flex min-w-[64px] flex-col items-center justify-center gap-1 rounded-xl p-2 text-[10px] transition ${active ? "bg-white/15 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"}`}
                  >
                    <Icon className="h-4 w-4" aria-hidden /> {t.label}
                  </button>
                );
              })}
            </div>
          ))}
          <div className="mt-auto flex gap-1 lg:flex-col">
            <button
              onClick={() => canUndo && setHistIdx((i) => i - 1)}
              disabled={!canUndo}
              title="Undo" aria-label="Undo"
              className="flex min-w-[64px] flex-col items-center gap-1 rounded-xl p-2 text-[10px] text-white/70 hover:bg-white/5 disabled:opacity-30"
            >
              <Undo2 className="h-4 w-4" aria-hidden /> Undo
            </button>
            <button
              onClick={() => canRedo && setHistIdx((i) => i + 1)}
              disabled={!canRedo}
              title="Redo" aria-label="Redo"
              className="flex min-w-[64px] flex-col items-center gap-1 rounded-xl p-2 text-[10px] text-white/70 hover:bg-white/5 disabled:opacity-30"
            >
              <Redo2 className="h-4 w-4" aria-hidden /> Redo
            </button>
          </div>
        </aside>

        {/* Canvas */}
        <section aria-label="Canvas" className="glass-panel order-2 flex min-h-0 min-w-0 flex-col gap-2 rounded-3xl p-2 sm:p-3">
          <div
            className={`relative flex min-h-0 w-full flex-1 items-center justify-center rounded-2xl ${zoom === "fit" || zoom === 100 ? "overflow-hidden" : "overflow-auto"}`}
            style={{
              background: "repeating-conic-gradient(oklch(0.16 0 0) 0% 25%, oklch(0.12 0 0) 0% 50%) 50% / 18px 18px",
            }}
          >
            {current ? (
              <div className="relative inline-flex max-h-full max-w-full">
                <img
                  ref={imgRef}
                  src={current}
                  alt="Edit canvas"
                  className="block max-h-full max-w-full object-contain transition"
                  style={zoom === "fit" || zoom === 100
                    ? undefined
                    : { transform: `scale(${zoom / 100})`, transformOrigin: "center center" }}
                />
                {/* Mask drawing overlay — only interactive in mask modes */}
                {isMaskMode && (
                  <>
                    <canvas ref={maskCanvasRef} className="hidden" />
                    <canvas
                      ref={displayCanvasRef}
                      className="absolute inset-0 h-full w-full touch-none"
                      style={{ cursor: maskTool === "eraser" ? "cell" : "crosshair" }}
                      onMouseDown={onMaskDown}
                      onMouseMove={onMaskMove}
                      onMouseUp={onMaskUp}
                      onMouseLeave={onMaskUp}
                      onTouchStart={onMaskDown}
                      onTouchMove={onMaskMove}
                      onTouchEnd={onMaskUp}
                    />
                  </>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-white/30">
                <ImageIcon className="h-10 w-10" />
                <span className="kerned text-[10px]">Pick or upload an image</span>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10"
                >
                  Upload image
                </button>
              </div>
            )}

            {/* Overlays */}
            <div className="glass-panel absolute left-3 top-3 rounded-lg px-2 py-1 font-mono text-[10px]">
              {applying ? "Working…" : (modelInfo || panel.title)}
            </div>
            <div className="glass-panel absolute right-3 top-3 rounded-lg px-2 py-1 font-mono text-[10px]">
              {isInpaint ? (hasMask ? "Mask ready" : "Paint a mask") : panel.title}
            </div>

            {applying && (
              <div className="absolute inset-0 grid place-items-center bg-black/40 backdrop-blur-sm">
                <Loader2 className="h-8 w-8 animate-spin text-white/70" />
              </div>
            )}

            {/* Zoom toolbar */}
            <div className="glass-panel absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-full p-1 text-xs">
              <button onClick={() => setZoom("fit")} aria-pressed={zoom === "fit"} className={`grid h-7 w-7 place-items-center rounded-full ${zoom === "fit" ? "bg-white/15" : "hover:bg-white/10"}`} aria-label="Fit"><Maximize className="h-3.5 w-3.5" /></button>
              <button onClick={() => setZoom(typeof zoom === "number" ? Math.max(25, zoom - 25) : 75)} className="grid h-7 w-7 place-items-center rounded-full hover:bg-white/10" aria-label="Zoom out"><Minus className="h-3.5 w-3.5" /></button>
              <span className="w-12 text-center font-mono text-[11px] text-white/80">{zoomLabel}</span>
              <button onClick={() => setZoom(typeof zoom === "number" ? Math.min(400, zoom + 25) : 125)} className="grid h-7 w-7 place-items-center rounded-full hover:bg-white/10" aria-label="Zoom in"><Plus className="h-3.5 w-3.5" /></button>
              <button onClick={() => setZoom(100)} aria-pressed={zoom === 100} className={`rounded-full px-2 py-1 ${zoom === 100 ? "bg-white/15" : "hover:bg-white/10"}`}>100%</button>
            </div>
          </div>

          {/* Hidden file input for uploaded reference images */}
          <input ref={extraFileRef} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { addUploadedExtras(e.target.files); e.target.value = ""; }} />

          {/* Slim bottom bar: hint + Quick Actions + prompt + Apply only */}
          <div className="glass-panel shrink-0 rounded-2xl p-2.5">
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-[11px] text-white/55">{panel.hint}</p>
              {isAiTool && (
                <div className="flex shrink-0 items-center gap-0.5 rounded-lg bg-white/5 p-0.5">
                  {QUALITIES.map((q) => (
                    <button
                      key={q.id}
                      onClick={() => setQuality(q.id)}
                      className={`rounded-md px-2 py-0.5 text-[10px] font-medium ${quality === q.id ? "bg-white text-black" : "text-white/60 hover:bg-white/10"}`}
                    >
                      {q.name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="no-scrollbar mt-1.5 flex items-center gap-1.5 overflow-x-auto pb-0.5">
              {QUICK_ACTIONS.map((qa) => {
                const Icon = qa.icon;
                return (
                  <button
                    key={qa.id}
                    onClick={() => runQuickAction(qa)}
                    disabled={!current || applying}
                    className="inline-flex shrink-0 items-center gap-1 rounded-full border border-white/10 bg-white/[0.02] px-2.5 py-0.5 text-[10px] text-white/75 hover:bg-white/10 disabled:opacity-40"
                  >
                    <Icon className="h-3 w-3" /> {qa.label}
                  </button>
                );
              })}
              {/* Upscale quick action — pick a scale first, then click Upscale */}
              <div className="inline-flex shrink-0 items-center gap-1 rounded-full border border-white/10 bg-white/[0.02] py-0.5 pl-2.5 pr-0.5 text-[10px] text-white/75">
                <ArrowUpToLine className="h-3 w-3" />
                <button
                  onClick={runUpscale}
                  disabled={!current || applying || upscaleScale === null}
                  title={upscaleScale === null ? "Pick 2× or 4× first" : `Upscale ${upscaleScale}×`}
                  className="hover:text-white disabled:opacity-40"
                >
                  Upscale
                </button>
                <span className="mx-1 h-3 w-px bg-white/10" />
                {UPSCALE_SCALES.map((x) => (
                  <button
                    key={x}
                    onClick={() => setUpscaleScale((cur) => (cur === x ? null : x))}
                    className={`rounded-full px-1.5 py-0.5 transition ${upscaleScale === x ? "bg-white text-black" : "text-white/60 hover:text-white"}`}
                  >
                    {x}×
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-1.5 flex items-end gap-2">
              {tool === "logo" ? (
                <div className="flex flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2 text-[11px] text-white/45">
                  <span className="kerned text-white/40">Logo</span>
                  <span className="text-white/70">{logoData ? `${logoPosition} · ${logoSize}% · ${logoOpacity}% opacity` : "Upload a logo on the right to begin"}</span>
                </div>
              ) : panel.placeholder !== undefined ? (
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) applyEdit(); }}
                  placeholder={panel.placeholder}
                  aria-label={`${panel.title} prompt`}
                  rows={1}
                  className="max-h-24 min-h-9 flex-1 resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white/90 placeholder:text-white/30 focus:border-white/20 focus:outline-none"
                />
              ) : (
                <div className="flex flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2 text-[11px] text-white/45">
                  <span className="kerned text-white/40">Tip</span>
                  <span>Paint your mask, set brush on the right, then Apply.</span>
                </div>
              )}
              <button
                onClick={tool === "logo" ? runLogoOverlay : applyEdit}
                disabled={!current || applying || (tool === "logo" ? !logoData : !isAiTool)}
                className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl px-4 text-xs font-medium text-black disabled:opacity-50"
                style={{ background: "var(--gradient-aurora)" }}
              >
                {applying ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : tool === "logo" ? <Stamp className="h-3.5 w-3.5" aria-hidden /> : <Wand2 className="h-3.5 w-3.5" aria-hidden />}
                {applying ? "Applying…" : (tool === "logo" ? "Apply logo" : "Apply")}
              </button>
            </div>

            {error && (
              <div className="mt-1.5 flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-[11px] text-red-200">
                <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
                <span className="flex-1">{error}</span>
              </div>
            )}
          </div>
        </section>

        {/* Right inspector — Controls ↔ History tabs */}
        <aside
          aria-label="Inspector"
          className="no-scrollbar order-3 min-h-0 space-y-3 overflow-y-auto pr-1"
        >
          {/* Tab toggle */}
          <div className="glass-panel flex items-center gap-1 rounded-full p-1">
            <button
              onClick={() => setInspectorTab("controls")}
              className={`flex-1 rounded-full px-3 py-1.5 text-[11px] font-medium transition ${inspectorTab === "controls" ? "bg-white text-black" : "text-white/60 hover:bg-white/5"}`}
            >
              Controls
            </button>
            <button
              onClick={() => setInspectorTab("history")}
              className={`flex-1 rounded-full px-3 py-1.5 text-[11px] font-medium transition ${inspectorTab === "history" ? "bg-white text-black" : "text-white/60 hover:bg-white/5"}`}
            >
              History
            </button>
          </div>

          {inspectorTab === "controls" ? (
            <div className="glass-panel space-y-3 rounded-3xl p-4">
              <div>
                <p className="text-sm font-medium text-white/90">{panel.title}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-white/55">{panel.hint}</p>
              </div>

              {/* Mask painting (universal) */}
              {isMaskMode && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="kerned text-white/55">Paint mask</p>
                    <span className={`rounded-full px-1.5 py-0.5 text-[9px] ${maskRequired ? "bg-rose-400/15 text-rose-200" : "bg-white/5 text-white/45"}`}>
                      {maskRequired ? "REQUIRED" : "OPTIONAL"}
                    </span>
                  </div>
                  <p className="text-[10px] leading-snug text-white/45">
                    {maskRequired
                      ? "Paint over the area you want to change."
                      : "Optional — paint to focus the edit on a specific area, or leave empty to apply globally."}
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {([
                      { id: "brush", icon: Brush, label: "Brush" },
                      { id: "circle", icon: Maximize, label: "Circle" },
                      { id: "rect", icon: Square, label: "Box" },
                      { id: "eraser", icon: Eraser, label: "Eraser" },
                    ] as { id: MaskTool; icon: typeof Brush; label: string }[]).map((t) => {
                      const Icon = t.icon;
                      return (
                        <button
                          key={t.id}
                          onClick={() => setMaskTool(t.id)}
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] transition ${maskTool === t.id ? "bg-white text-black" : "border border-white/10 bg-white/5 text-white/75 hover:bg-white/10"}`}
                        >
                          <Icon className="h-3 w-3" /> {t.label}
                        </button>
                      );
                    })}
                  </div>
                  <div>
                    <p className="kerned mb-1 text-white/40">Brush size</p>
                    <div className="flex items-center gap-1">
                      {BRUSH_SIZES.map((s) => (
                        <button
                          key={s}
                          onClick={() => setBrushSize(s)}
                          title={`${s}px`}
                          className={`grid h-7 w-7 place-items-center rounded-md ${brushSize === s ? "bg-white/15 ring-1 ring-white/40" : "bg-white/5 hover:bg-white/10"}`}
                        >
                          <span className="rounded-full bg-white/70" style={{ width: Math.max(2, s / 5), height: Math.max(2, s / 5) }} />
                        </button>
                      ))}
                    </div>
                  </div>
                  <button onClick={clearMask} className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] text-red-300 hover:bg-red-500/10">
                    Clear mask
                  </button>
                </div>
              )}

              {/* Restyle theme presets */}
              {tool === "restyle" && (
                <div>
                  <p className="kerned mb-1.5 text-white/40">Theme presets</p>
                  <div className="flex flex-wrap gap-1.5">
                    {THEME_PRESETS.map((p) => (
                      <button
                        key={p.label}
                        onClick={() => setPrompt(p.prompt)}
                        className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[10px] text-white/75 hover:bg-white/10"
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}


              {/* Logo overlay controls */}
              {tool === "logo" && (
                <div className="space-y-2.5">
                  <div className="flex items-start gap-2">
                    <div className="grid h-16 w-16 shrink-0 place-items-center overflow-hidden rounded-lg border border-dashed border-white/15 bg-white/[0.02]">
                      {logoData ? (
                        <img src={logoData} alt="logo" className="h-full w-full object-contain" />
                      ) : (
                        <Stamp className="h-5 w-5 text-white/30" />
                      )}
                    </div>
                    <div className="flex flex-col gap-1">
                      <button onClick={() => logoFileRef.current?.click()} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] hover:bg-white/10">
                        <Plus className="h-3 w-3" /> {logoData ? "Replace" : "Upload logo"}
                      </button>
                      {logoData && (
                        <button onClick={() => setLogoData(null)} className="text-left text-[10px] text-white/40 hover:text-white/70">Remove</button>
                      )}
                      <input ref={logoFileRef} type="file" accept="image/*" onChange={onLogoFile} className="hidden" />
                    </div>
                  </div>
                  <div>
                    <p className="kerned mb-1 text-white/40">Position</p>
                    <div className="grid w-fit grid-cols-3 gap-1">
                      {LOGO_POSITIONS.map((p) => (
                        <button
                          key={p}
                          onClick={() => setLogoPosition(p)}
                          title={p}
                          className={`h-7 w-7 rounded transition ${logoPosition === p ? "bg-white text-black" : "border border-white/10 bg-white/5 hover:bg-white/10"}`}
                        >
                          <span className="block h-1.5 w-1.5 rounded-full mx-auto" style={{ background: logoPosition === p ? "#000" : "rgba(255,255,255,0.6)" }} />
                        </button>
                      ))}
                    </div>
                  </div>
                  <label className="block text-[11px] text-white/60">
                    <span className="kerned mb-0.5 block text-white/40">Size {logoSize}%</span>
                    <input type="range" min={5} max={50} value={logoSize} onChange={(e) => setLogoSize(Number(e.target.value))} className="w-full" />
                  </label>
                  <label className="block text-[11px] text-white/60">
                    <span className="kerned mb-0.5 block text-white/40">Opacity {logoOpacity}%</span>
                    <input type="range" min={10} max={100} value={logoOpacity} onChange={(e) => setLogoOpacity(Number(e.target.value))} className="w-full" />
                  </label>
                </div>
              )}

              {/* Reference images (universal) */}
              {isExtrasMode && (
                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-2.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="kerned text-white/55">Reference images</p>
                    <span className={`rounded-full px-1.5 py-0.5 text-[9px] ${refRequired ? "bg-rose-400/15 text-rose-200" : "bg-white/5 text-white/45"}`}>
                      {refRequired ? "REQUIRED" : "OPTIONAL"}
                    </span>
                  </div>
                  <p className="text-[10px] leading-snug text-white/45">
                    {refRequired
                      ? `Add up to ${maxRefsForTool} reference images to combine.`
                      : `Optional — upload images to guide the look (style, background, subject, etc). Up to ${maxRefsForTool}.`}
                  </p>
                  <p className="text-[10px] text-white/40">
                    {uploadedExtras.length + (tool === "compose" ? composeRefs.length : 0)} / {maxRefsForTool + (tool === "compose" ? 4 : 0)}
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {uploadedExtras.map((u, i) => (
                      <div key={i} className="group relative h-12 w-12 overflow-hidden rounded-lg hairline">
                        <img src={u} alt="" className="h-full w-full object-cover" />
                        <button onClick={() => removeUploadedExtra(i)} className="absolute right-0.5 top-0.5 grid h-4 w-4 place-items-center rounded-full bg-black/70 text-[9px] text-white opacity-0 transition group-hover:opacity-100">×</button>
                      </div>
                    ))}
                    {tool === "compose" && composeRefs.map((u, i) => (
                      <div key={`g${i}`} className="group relative h-12 w-12 overflow-hidden rounded-lg ring-1 ring-white/30">
                        <img src={u} alt="" className="h-full w-full object-cover" />
                        <button onClick={() => toggleComposeRef(u)} className="absolute right-0.5 top-0.5 grid h-4 w-4 place-items-center rounded-full bg-black/70 text-[9px] text-white opacity-0 transition group-hover:opacity-100">×</button>
                      </div>
                    ))}
                    {uploadedExtras.length < maxRefsForTool && (
                      <button
                        onClick={() => extraFileRef.current?.click()}
                        title="Upload reference image"
                        className="grid h-12 w-12 place-items-center rounded-lg border border-dashed border-white/15 text-white/40 hover:bg-white/5"
                      >
                        <Plus className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                  {tool === "compose" && (
                    <p className="text-[10px] text-white/35">
                      Tip: you can also tap gallery thumbnails in the History tab to use existing images as refs.
                    </p>
                  )}
                </div>
              )}

              {/* Quick ideas — one per line, full-width, truncate long text */}
              {panel.chips && (
                <div>
                  <p className="kerned mb-1.5 text-white/40">Quick ideas</p>
                  <div className="flex flex-col gap-1">
                    {panel.chips.map((c) => (
                      <button
                        key={c}
                        onClick={() => setPrompt(c)}
                        title={c}
                        className="group flex w-full items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-left text-[11px] text-white/75 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white"
                      >
                        <Sparkles className="h-3 w-3 shrink-0 text-white/30 group-hover:text-white/60" />
                        <span className="flex-1 truncate">{c}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* No-tool-specific-controls placeholder */}
              {!isMaskMode && tool !== "restyle" && tool !== "logo" && !isExtrasMode && !panel.chips && (
                <p className="text-[11px] text-white/40">Type a prompt below and hit Apply.</p>
              )}
            </div>
          ) : (
            <>
              <div className="glass-panel space-y-3 rounded-3xl p-4">
                <div className="flex items-center justify-between">
                  <p className="kerned text-white/50">All generations</p>
                  <LayersIcon className="h-4 w-4 text-white/40" aria-hidden />
                </div>
                {pastGensLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-white/30" />
                  </div>
                ) : pastGens.length === 0 ? (
                  <p className="text-xs text-white/40">No generations yet — create one to see it here.</p>
                ) : (
                  <div className="grid grid-cols-2 gap-1.5">
                    {pastGens.map((g) => (
                      <button
                        key={g.id}
                        onClick={() => pickSource(g.url)}
                        title={g.prompt}
                        className={`group relative aspect-square overflow-hidden rounded-lg hairline ${current === g.url ? "ring-2 ring-white" : ""}`}
                      >
                        <img src={g.url} alt="" className="h-full w-full object-cover transition group-hover:scale-105" />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {history.length > 1 && (
                <div className="glass-panel space-y-2 rounded-3xl p-4">
                  <p className="kerned text-white/50">This session</p>
                  <div className="space-y-2">
                    {history.map((h, i) => (
                      <button
                        key={i}
                        onClick={() => setHistIdx(i)}
                        className={`flex w-full items-center gap-2 rounded-xl border p-2 text-left transition ${i === histIdx ? "border-white/30 bg-white/10" : "border-white/10 bg-white/5 hover:bg-white/[0.08]"}`}
                      >
                        <div className="h-10 w-10 overflow-hidden rounded-md hairline">
                          <img src={h} alt="" className="h-full w-full object-cover" />
                        </div>
                        <div className="flex-1">
                          <p className="text-xs">{i === 0 ? "Original" : `Edit ${i}`}</p>
                          <p className="kerned text-white/40">{i === histIdx ? "Current" : "Step"}</p>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="glass-panel rounded-3xl p-4">
                <div className="mb-2 flex items-center justify-between">
                  <p className="kerned text-white/50">
                    {tool === "compose" ? "Source + refs" : "Source image"}
                  </p>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    title="Upload"
                    className="grid h-7 w-7 place-items-center rounded-lg border border-white/10 bg-white/5 hover:bg-white/10"
                  >
                    <Upload className="h-3.5 w-3.5 text-white/60" />
                  </button>
                </div>
                {tool === "compose" && (
                  <p className="mb-2 text-[11px] text-white/40">
                    Tap thumbnails to add up to 4 reference images ({composeRefs.length}/4). The current
                    canvas image is the base.
                  </p>
                )}
                {loadingSources ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-white/30" />
                  </div>
                ) : sources.length === 0 ? (
                  <p className="text-xs text-white/40">No saved images yet — upload one, or generate first.</p>
                ) : (
                  <div className="grid grid-cols-3 gap-1.5">
                    {sources.map((s) => {
                      const isCurrent = current === s.src;
                      const refIdx = composeRefs.indexOf(s.src);
                      const isRef = refIdx >= 0;
                      return (
                        <button
                          key={s.id}
                          onClick={() => (tool === "compose" ? toggleComposeRef(s.src) : pickSource(s.src))}
                          aria-label={`${tool === "compose" ? "Toggle ref" : "Use"} ${s.prompt || "image"}`}
                          className={`relative overflow-hidden rounded-lg hairline ${
                            tool === "compose"
                              ? isRef ? "ring-2 ring-white" : isCurrent ? "ring-1 ring-white/40" : ""
                              : isCurrent ? "ring-2 ring-white" : ""
                          }`}
                        >
                          <img src={s.src} alt="" className="aspect-square h-full w-full object-cover" />
                          {tool === "compose" && isRef && (
                            <span className="absolute right-0.5 top-0.5 grid h-4 w-4 place-items-center rounded-full bg-black/70 text-[9px] font-medium text-white">
                              {refIdx + 1}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
