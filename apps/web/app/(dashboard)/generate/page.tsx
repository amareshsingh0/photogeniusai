"use client";

import React, { useState, useMemo, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Sparkles, Lock, Shuffle, Download, Maximize2,
  ChevronDown, Image as ImageIcon, Layers, Plus, Settings2,
  Palette, Type, Clock, X, ArrowLeft, ArrowUpToLine, Pencil,
  Wand, Gauge, SlidersHorizontal, Megaphone, Loader2, AlertCircle,
  UserRoundCog, Package, Stamp, Users,
} from "lucide-react";
import { samples, types, styles as styleList } from "@/lib/pixium/samples";
import { brandedImageUrl } from "@/lib/image-url";

// ─── Domain types ─────────────────────────────────────────────────────────────
interface GenerationResult {
  success: boolean;
  image_url?: string;
  enhanced_prompt?: string;
  model_used?: string;
  total_time?: number;
  generationId?: string;
  quality_score?: number;
  capability_bucket?: string;
  ad_copy?: unknown;
  poster_design?: unknown;
}

const ratios = [
  { id: "1:1",  w: 1024, h: 1024, vw: 1,  vh: 1  },
  { id: "3:4",  w: 832,  h: 1216, vw: 3,  vh: 4  },
  { id: "4:3",  w: 1216, h: 832,  vw: 4,  vh: 3  },
  { id: "2:3",  w: 832,  h: 1248, vw: 2,  vh: 3  },
  { id: "3:2",  w: 1248, h: 832,  vw: 3,  vh: 2  },
  { id: "16:9", w: 1344, h: 768,  vw: 16, vh: 9  },
  { id: "9:16", w: 768,  h: 1344, vw: 9,  vh: 16 },
  { id: "21:9", w: 1536, h: 640,  vw: 21, vh: 9  },
  { id: "9:21", w: 640,  h: 1536, vw: 9,  vh: 21 },
  { id: "5:4",  w: 1152, h: 928,  vw: 5,  vh: 4  },
  { id: "4:5",  w: 928,  h: 1152, vw: 4,  vh: 5  },
  { id: "7:5",  w: 1280, h: 912,  vw: 7,  vh: 5  },
];

// Quality tiers — only 1K / 2K / 4K shown to user.
const qualities = [
  { id: "1k", name: "1K", cost: 1,  tier: "1k" },
  { id: "2k", name: "2K", cost: 4,  tier: "2k" },
  { id: "4k", name: "4K", cost: 10, tier: "4k" },
];

const batches = [1, 2, 4];
const MAX_REFS = 5;

// Map each style to a sample image so the Style picker shows visual thumbnails.
// Picks the first sample whose `style` matches; falls back to a generic image.
const STYLE_PREVIEWS: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const s of samples) {
    if (!out[s.style]) out[s.style] = s.src;
  }
  // explicit fallbacks for styles without a sample
  if (!out["Photoreal"]) out["Photoreal"] = samples[0]?.src ?? "";
  if (!out["Landscape"]) out["Landscape"] = samples.find((s) => s.style === "Landscape")?.src ?? samples[0]?.src ?? "";
  return out;
})();
const STYLE_FALLBACK = samples[0]?.src ?? "";

const RAIL = [
  { id: "image",  icon: ImageIcon, label: "Image" },
  { id: "poster", icon: Megaphone, label: "Poster" },
  { id: "batch",  icon: Layers,    label: "Batch" },
  { id: "brand",  icon: Palette,   label: "Brand" },
  { id: "assets", icon: Type,      label: "Assets" },
];

export default function Generate() {
  const search = useSearchParams();

  // ── State (Pixium-shaped, Lumen-named where they overlap) ────────────────
  // Seed initial values from query params (?prompt=, ?style=, ?type=) — used when
  // arriving from the landing-page hero prompt bar or the /types catalog.
  const [prompt, setPrompt] = useState(search?.get("prompt") ?? "");
  const [negative, setNegative] = useState("");
  const [activeType, setActiveType] = useState(search?.get("type") ?? "auto");
  const [style, setStyle] = useState(search?.get("style") ?? "Auto");
  const [ratio, setRatio] = useState("1:1");
  const [customMode, setCustomMode] = useState(false);
  const [customW, setCustomW] = useState(1024);
  const [customH, setCustomH] = useState(1024);
  const [quality, setQuality] = useState("1k"); // 1k default
  const [guidance, setGuidance] = useState(7.5);
  const [batch, setBatch] = useState(1);
  const [seed, setSeed] = useState("742193");
  const [locked, setLocked] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [mode, setMode] = useState<string>("poster");
  const [focused, setFocused] = useState<number | null>(null);
  // Zoom for the focused-result view. "fit" = contain to viewport, number = percentage of natural size.
  const [focusZoom, setFocusZoom] = useState<"fit" | number>("fit");
  const focusImgRef = useRef<HTMLImageElement | null>(null);
  const [showHistory, setShowHistory] = useState(false); // toggles the right panel: controls ↔ history
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false); // mobile-only bottom sheet for Settings/History
  const [history, setHistory] = useState<{ id: string; url: string; prompt?: string }[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [refsOpen, setRefsOpen] = useState(false);
  // Slotted references: named multi-image slots (people/products/logos) + extras pool.
  // Each named slot accepts 1+ images (couple, group of actors, product variants, etc).
  // The flat `referenceImages` is derived from these and sent to backend in slot order:
  // people first, then products, logos, extras. Backend treats reference_image[0] as primary.
  const [refPeople, setRefPeople] = useState<string[]>([]);
  const [refProducts, setRefProducts] = useState<string[]>([]);
  const [refLogos, setRefLogos] = useState<string[]>([]);
  const [refExtras, setRefExtras] = useState<string[]>([]);
  // Per-slot caps. People is the highest (group shots possible).
  const SLOT_CAPS = { people: 4, products: 4, logos: 2, extras: 2 } as const;
  // Slot the file picker should fill on the next change event. null = legacy flat add.
  const [pendingRefSlot, setPendingRefSlot] = useState<"people" | "products" | "logos" | "extras" | null>(null);
  const referenceImages = useMemo<string[]>(() => {
    return [...refPeople, ...refProducts, ...refLogos, ...refExtras];
  }, [refPeople, refProducts, refLogos, refExtras]);

  // ── Generation lifecycle ──────────────────────────────────────────────────
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [sseStage, setSseStage] = useState<string>("");
  const [activeModel, setActiveModel] = useState<string>("");
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [multiResults, setMultiResults] = useState<GenerationResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const refFileInput = useRef<HTMLInputElement>(null);

  const activeQuality = qualities.find((q) => q.id === quality)!;
  const activeRatio = ratios.find((r) => r.id === ratio) ?? ratios[0];
  const activeTypeMeta = types.find((t) => t.id === activeType) ?? types[0];

  const suggestions = useMemo(() => {
    if (prompt.trim().length < 8) return [];
    return [
      `${prompt}, cinematic 35mm, soft golden hour light`,
      `${prompt}, editorial fashion, rim light, shallow depth of field`,
      `${prompt}, hyper-detailed, octane render, 8k`,
    ];
  }, [prompt]);

  // ── Reference image upload ────────────────────────────────────────────────
  const handleRefSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const slot = pendingRefSlot ?? "extras";
    const cap = SLOT_CAPS[slot];
    const cur = slot === "people" ? refPeople.length : slot === "products" ? refProducts.length : slot === "logos" ? refLogos.length : refExtras.length;
    if (cur >= cap) {
      setError(`Max ${cap} ${slot} reference images`);
      e.target.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      if (slot === "people") setRefPeople((p) => [...p, dataUrl]);
      else if (slot === "products") setRefProducts((p) => [...p, dataUrl]);
      else if (slot === "logos") setRefLogos((p) => [...p, dataUrl]);
      else setRefExtras((p) => [...p, dataUrl]);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
    setPendingRefSlot(null);
    setRefsOpen(false);
  }, [pendingRefSlot, refPeople.length, refProducts.length, refLogos.length, refExtras.length]);

  // Helper to trigger upload for a specific slot
  const triggerSlotUpload = useCallback((slot: "people" | "products" | "logos" | "extras") => {
    setPendingRefSlot(slot);
    refFileInput.current?.click();
  }, []);

  // Remove a reference by its index in the flat referenceImages array.
  const removeReferenceAt = useCallback((flatIdx: number) => {
    let i = flatIdx;
    if (i < refPeople.length) { setRefPeople((p) => p.filter((_, idx) => idx !== i)); return; }
    i -= refPeople.length;
    if (i < refProducts.length) { setRefProducts((p) => p.filter((_, idx) => idx !== i)); return; }
    i -= refProducts.length;
    if (i < refLogos.length) { setRefLogos((p) => p.filter((_, idx) => idx !== i)); return; }
    i -= refLogos.length;
    setRefExtras((prev) => prev.filter((_, idx) => idx !== i));
  }, [refPeople.length, refProducts.length, refLogos.length]);

  // ── Detect admin (enables parallel multi-model testing mode on the backend) ──
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/user/current");
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && data?.email === "dev@photogenius.local") setIsAdmin(true);
      } catch {
        /* assume not admin on failure (safe default) */
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ── History drawer — fetch the user's recent generations when opened ──────
  // /api/generations returns a flat array of { id, prompt, selectedUrl, outputUrls[], previewUrl, ... }
  // When switching to Batch mode, default batch to 2 if it was 1. When leaving, snap back to 1.
  useEffect(() => {
    if (mode === "batch") {
      setBatch((b) => (b > 1 ? b : 2));
    } else {
      setBatch(1);
    }
  }, [mode]);

  useEffect(() => {
    if (!showHistory || history.length > 0) return;
    setHistoryLoading(true);
    (async () => {
      try {
        const res = await fetch("/api/generations?limit=40");
        if (res.ok) {
          const data = await res.json();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const items: any[] = Array.isArray(data) ? data : (data.generations || data.items || []);
          setHistory(
            items
              .map((g) => ({
                id: g.id as string,
                url: (g.selectedUrl || (Array.isArray(g.outputUrls) && g.outputUrls[0]) || g.previewUrl || g.thumbnailUrl || g.imageUrl || g.image_url || "") as string,
                prompt: (g.prompt || g.originalPrompt) as string | undefined,
              }))
              .filter((g) => g.url),
          );
        }
      } catch {
        /* ignore — drawer just shows empty state */
      } finally {
        setHistoryLoading(false);
      }
    })();
  }, [showHistory, history.length]);

  // ── Single SSE generation request (one image). Called once or N times in parallel for batch. ──
  const runOneGeneration = useCallback(async (
    signal: AbortSignal,
    slot: number,
    onProgressEvent: (e: { stage?: string; progress?: number; model?: string }) => void
  ): Promise<GenerationResult | null> => {
    let final: GenerationResult | null = null;
    const res = await fetch("/api/generate/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal,
      body: JSON.stringify({
        prompt: prompt.trim(),
        width: customMode ? customW : activeRatio.w,
        height: customMode ? customH : activeRatio.h,
        quality: activeQuality.tier,
        style: style !== "Auto" ? style : undefined,
        reference_image: referenceImages[0] || undefined,
        extra_reference_images: referenceImages.length > 1 ? referenceImages.slice(1) : undefined,
        // Slotted references — backend can compose a structured prompt from these
        // Slotted reference arrays (May 16 2026): each slot accepts multiple images
        // (couple/group for people, product variants, primary+secondary logo, etc).
        reference_people: refPeople.length ? refPeople : undefined,
        reference_products: refProducts.length ? refProducts : undefined,
        reference_logos: refLogos.length ? refLogos : undefined,
        negative_prompt: negative.trim() || undefined,
        capability_bucket: activeType !== "fast" && activeType !== "auto" ? activeType : undefined,
        testing_mode: isAdmin,
        // Per-slot seed so each batch slot gets a different image
        seed: locked ? Number(seed) || undefined : Math.floor(Math.random() * 1_000_000) + slot * 7919,
      }),
    });
    if (!res.ok || !res.body) {
      const errData = await res.json().catch(() => ({}));
      throw new Error((errData as { error?: string }).error || `Request failed (${res.status})`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const messages = buffer.split("\n\n");
      buffer = messages.pop() ?? "";
      for (const msg of messages) {
        if (!msg.trim()) continue;
        const eventMatch = msg.match(/^event:\s*(\w+)/m);
        const dataMatch = msg.match(/^data:\s*(.+)/m);
        if (!eventMatch || !dataMatch) continue;
        const event = eventMatch[1];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        let data: any;
        try { data = JSON.parse(dataMatch[1]); } catch { continue; }

        if (event === "intent_ready") onProgressEvent({ stage: "intent", progress: 15 });
        else if (event === "brief_ready") onProgressEvent({ stage: "brief", progress: 35 });
        else if (event === "generating") onProgressEvent({ stage: "generating", progress: 60, model: data.model });
        else if (event === "compositing") onProgressEvent({ stage: "compositing", progress: 78 });
        else if (event === "quality_checking") onProgressEvent({ stage: "quality_checking", progress: 90 });
        else if (event === "final_ready") {
          onProgressEvent({ stage: "done", progress: 100 });
          final = {
            success: true,
            image_url: data.image_url,
            enhanced_prompt: data.enhanced_prompt,
            model_used: data.model_used,
            total_time: data.total_time,
            quality_score: data.quality_score,
            generationId: data.generationId,
            capability_bucket: data.capability_bucket,
            ad_copy: data.ad_copy,
            poster_design: data.poster_design,
          };
        }
        else if (event === "error") throw new Error(data.message || "Generation failed");
      }
    }
    return final;
  }, [prompt, activeRatio, activeQuality, style, referenceImages, refPeople, refProducts, refLogos, negative, activeType, customMode, customW, customH, locked, seed, isAdmin]);

  // ── Real generation: Pixium SSE pipeline (single or batch) ──────────────────────────────────
  const generate = useCallback(async () => {
    if (prompt.trim().length < 3 || isGenerating) return;

    setIsGenerating(true);
    setError(null);
    setResult(null);
    setMultiResults([]);
    setProgress(5);
    setSseStage("intent");
    setActiveModel("");
    setFocused(null);

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const timeoutId = setTimeout(() => ctrl.abort(), 240_000);

    try {
      // BATCH > 1: fire N parallel single-image generations, collect into multiResults
      if (batch > 1) {
        const slots = Array.from({ length: batch }, (_, i) => i);
        // Track progress as average across slots
        const slotProgress = new Array(batch).fill(0);
        const updateOverall = () => {
          const avg = slotProgress.reduce((a, b) => a + b, 0) / batch;
          setProgress(Math.max(5, Math.round(avg)));
        };
        const results = await Promise.allSettled(
          slots.map((i) =>
            runOneGeneration(ctrl.signal, i, ({ stage, progress: p, model }) => {
              if (typeof p === "number") { slotProgress[i] = p; updateOverall(); }
              if (stage) setSseStage(stage);
              if (model && !activeModel) setActiveModel(model);
            }).then((r) => {
              if (r) {
                // Stream tiles in as each one completes
                setMultiResults((prev) => [...prev, r]);
              }
              return r;
            })
          )
        );
        const succeeded = results.filter((r) => r.status === "fulfilled" && r.value).length;
        if (succeeded === 0) {
          const firstReason = results.find((r) => r.status === "rejected") as PromiseRejectedResult | undefined;
          throw new Error(firstReason?.reason?.message || "All batch generations failed");
        }
        setSseStage("done");
        setProgress(100);
        if (!locked) setSeed(String(Math.floor(Math.random() * 999999)));
        return;
      }

      // BATCH === 1: original single-call path (preserves admin parallel-testing grid via model_results)
      const res = await fetch("/api/generate/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ctrl.signal,
        body: JSON.stringify({
          prompt: prompt.trim(),
          width: customMode ? customW : activeRatio.w,
          height: customMode ? customH : activeRatio.h,
          quality: activeQuality.tier,
          style: style !== "Auto" ? style : undefined,
          reference_image: referenceImages[0] || undefined,
          extra_reference_images: referenceImages.length > 1 ? referenceImages.slice(1) : undefined,
          reference_people: refPeople.length ? refPeople : undefined,
          reference_products: refProducts.length ? refProducts : undefined,
          reference_logos: refLogos.length ? refLogos : undefined,
          negative_prompt: negative.trim() || undefined,
          capability_bucket: activeType !== "fast" && activeType !== "auto" ? activeType : undefined,
          testing_mode: isAdmin,
        }),
      });

      if (!res.ok || !res.body) {
        const errData = await res.json().catch(() => ({}));
        throw new Error((errData as { error?: string }).error || `Request failed (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split("\n\n");
        buffer = messages.pop() ?? "";

        for (const msg of messages) {
          if (!msg.trim()) continue;
          const eventMatch = msg.match(/^event:\s*(\w+)/m);
          const dataMatch = msg.match(/^data:\s*(.+)/m);
          if (!eventMatch || !dataMatch) continue;
          const event = eventMatch[1];
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          let data: any;
          try { data = JSON.parse(dataMatch[1]); } catch { continue; }

          if (event === "intent_ready") { setSseStage("intent"); setProgress(15); }
          else if (event === "brief_ready") { setSseStage("brief"); setProgress(35); }
          else if (event === "generating") { setSseStage("generating"); setProgress(60); if (data.model) setActiveModel(data.model); }
          else if (event === "compositing") { setSseStage("compositing"); setProgress(78); }
          else if (event === "quality_checking") { setSseStage("quality_checking"); setProgress(90); }
          else if (event === "model_result") {
            // Admin testing parallel mode
            setMultiResults((prev) => [...prev, {
              success: true,
              image_url: data.imageUrl,
              model_used: data.modelId,
              total_time: data.latency,
              generationId: data.generationId,
            }]);
          }
          else if (event === "testing_complete") { setSseStage("done"); setProgress(100); }
          else if (event === "final_ready") {
            setSseStage("done");
            setProgress(100);
            if (data.model_results && Array.isArray(data.model_results) && data.model_results.length > 1) {
              setMultiResults(data.model_results.map((mr: { image_url: string; model_name?: string; generation_time?: number; generationId?: string }) => ({
                success: true,
                image_url: mr.image_url,
                model_used: mr.model_name,
                total_time: mr.generation_time,
                generationId: mr.generationId,
              })));
              setResult(null);
            } else {
              setResult({
                success: true,
                image_url: data.image_url,
                enhanced_prompt: data.enhanced_prompt,
                model_used: data.model_used,
                total_time: data.total_time,
                quality_score: data.quality_score,
                generationId: data.generationId,
                capability_bucket: data.capability_bucket,
                ad_copy: data.ad_copy,
                poster_design: data.poster_design,
              });
              setMultiResults([]);
            }
          }
          else if (event === "error") { throw new Error(data.message || "Generation failed"); }
          // else "heartbeat" — swallow
        }
      }

      if (!locked) setSeed(String(Math.floor(Math.random() * 999999)));
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") setError("Generation timed out — try again");
      else setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      clearTimeout(timeoutId);
      setIsGenerating(false);
    }
  }, [prompt, isGenerating, activeRatio, activeQuality, style, referenceImages, refPeople, refProducts, refLogos, negative, activeType, locked, customMode, customW, customH, batch, runOneGeneration, activeModel, isAdmin]);

  // ── Visible tiles: real result(s) > one placeholder sample matching aspect ──
  const visibleTiles = useMemo<GenerationResult[]>(() => {
    if (multiResults.length > 0) return multiResults;
    if (result?.image_url) return [result];
    // Single placeholder matching selected aspect — no duplicates.
    const wantRatio: "portrait" | "landscape" | "square" =
      activeRatio.vw === activeRatio.vh ? "square"
        : activeRatio.vw > activeRatio.vh ? "landscape"
        : "portrait";
    const matched = samples.filter((s) => s.ratio === wantRatio);
    const pool = matched.length > 0 ? matched : samples;
    const pick = pool[0];
    return pick ? [{
      image_url: pick.src,
      enhanced_prompt: pick.prompt,
      model_used: pick.model,
    } as GenerationResult] : [];
  }, [result, multiResults, activeRatio]);

  const hasContent = true;
  const tileCount = isGenerating ? batch : visibleTiles.length;
  const gridCols = tileCount === 1 ? "grid-cols-1" : "grid-cols-2";
  // Figure fills the available column height; the image inside object-contains.
  const aspectStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    minHeight: 160,
    margin: "0 auto",
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-5rem)] max-w-[1480px] flex-col px-2 pt-2 pb-[88px] sm:px-4 lg:pb-[88px]">
      <input
        ref={refFileInput}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleRefSelect}
      />
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-[64px_minmax(0,1fr)_520px]">
        {/* LEFT ICON RAIL — scrollable */}
        <aside className="no-scrollbar hidden flex-col items-center gap-1 overflow-y-auto rounded-2xl border border-white/10 bg-white/[0.02] p-2 lg:flex">
          {RAIL.map((r) => {
            const Icon = r.icon;
            const active = mode === r.id;
            return (
              <button
                key={r.id}
                onClick={() => setMode(r.id)}
                aria-pressed={active}
                title={r.label}
                className={`flex w-full shrink-0 flex-col items-center gap-1 rounded-xl py-2.5 text-[10px] transition ${active ? "bg-white/10 text-white" : "text-white/55 hover:bg-white/5 hover:text-white"}`}
              >
                <Icon className="h-4 w-4" />
                {r.label}
              </button>
            );
          })}
          <div className="my-1 h-px w-full shrink-0 bg-white/10" />
          <button
            onClick={() => setShowHistory((v) => !v)}
            aria-pressed={showHistory}
            title="History"
            className={`flex w-full shrink-0 flex-col items-center gap-1 rounded-xl py-2.5 text-[10px] transition ${showHistory ? "bg-white/10 text-white" : "text-white/55 hover:bg-white/5 hover:text-white"}`}
          >
            <Clock className="h-4 w-4" /> History
          </button>
        </aside>

        {/* CENTER */}
        <section className="flex min-h-0 min-w-0 flex-col">
          {/* Top header — mobile/tablet only. Desktop is header-less for max canvas space;
              History tab lives inside the right inspector (Settings ↔ History pill). */}
          <div className="flex shrink-0 items-center justify-between gap-2 py-1 lg:hidden">
            <div className="flex min-w-0 items-center gap-2 text-sm">
              <span className="font-display text-base font-medium">Create</span>
              <div className="hidden items-center gap-1 rounded-full border border-white/10 bg-white/[0.03] p-1 text-xs md:flex">
                {RAIL.slice(0, 3).map((r) => (
                  <button key={r.id} onClick={() => setMode(r.id)} className={`rounded-full px-2.5 py-1 ${mode === r.id ? "bg-white text-black" : "text-white/65"}`}>{r.label}</button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setMobileSheetOpen(true)}
                className="glass-panel inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs md:hidden"
                aria-label="Open settings"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" /> Settings
              </button>
              <button
                onClick={() => setShowHistory((v) => !v)}
                className={`hidden items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition md:inline-flex ${showHistory ? "bg-white text-black" : "glass-panel"}`}
              >
                <Clock className="h-3.5 w-3.5" /> History
              </button>
            </div>
          </div>

          {/* Batch mode banner */}
          {mode === "batch" && (
            <div className="mb-2 flex shrink-0 flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-sm">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-white/70" />
                <span className="font-medium text-white/90">Batch mode</span>
                <span className="text-[11px] text-white/45">— generate multiple variations in parallel</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="kerned text-white/45">Variations</span>
                <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1">
                  {[2, 4].map((b) => (
                    <button
                      key={b}
                      onClick={() => setBatch(b)}
                      className={`min-w-[44px] rounded-full px-3 py-1 text-xs font-medium transition ${batch === b ? "bg-white text-black" : "text-white/70 hover:bg-white/10"}`}
                    >
                      {b}×
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setMode("image")}
                  className="text-[11px] text-white/45 hover:text-white"
                  title="Exit batch mode"
                >
                  Exit
                </button>
              </div>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="mb-2 flex shrink-0 items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="flex-1">{error}</div>
              <button onClick={() => setError(null)} className="text-white/50 hover:text-white"><X className="h-4 w-4" /></button>
            </div>
          )}

          {/* Reference image previews */}
          {referenceImages.length > 0 && (
            <div className="mb-2 flex shrink-0 gap-2">
              {referenceImages.map((url, i) => (
                <div key={i} className="group relative h-12 w-12 overflow-hidden rounded-lg hairline">
                  <img src={url} alt="" className="h-full w-full object-cover" />
                  <button
                    onClick={() => removeReferenceAt(i)}
                    className="absolute right-0.5 top-0.5 grid h-4 w-4 place-items-center rounded-full bg-black/70 text-[9px] text-white opacity-0 transition group-hover:opacity-100"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Canvas grid OR focused — fills remaining height */}
          {focused === null ? (
            <div className={`grid min-h-0 flex-1 ${gridCols} gap-2 sm:gap-3 ${hasContent ? "" : "place-items-center"}`}>
              {Array.from({ length: tileCount }).map((_, i) => {
                const tile = visibleTiles[i];
                const tileUrl = tile?.image_url;
                return (
                  <figure
                    key={i}
                    className="group relative mx-auto flex w-full items-center justify-center overflow-hidden rounded-2xl hairline bg-white/[0.02]"
                    style={aspectStyle}
                  >
                    {isGenerating ? (
                      <div className="absolute inset-0 grid place-items-center">
                        <div className="shimmer absolute inset-0" />
                        <div className="relative z-10 flex flex-col items-center gap-2">
                          <div className="h-1 w-32 overflow-hidden rounded-full bg-white/10">
                            <div className="h-full bg-white transition-all" style={{ width: `${progress}%` }} />
                          </div>
                          <span className="kerned font-mono text-[10px] text-white/60">
                            {sseStage || "starting"} · {Math.round(progress)}%
                          </span>
                        </div>
                      </div>
                    ) : tileUrl ? (
                      <>
                        <img
                          src={brandedImageUrl(tileUrl)}
                          alt={prompt || tile.enhanced_prompt || ""}
                          loading="lazy"
                          onClick={() => setFocused(i)}
                          className="block max-h-full max-w-full cursor-pointer object-contain transition duration-700 group-hover:scale-[1.02]"
                          style={{ width: "auto", height: "auto" }}
                        />
                        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent opacity-0 transition group-hover:opacity-100" />
                        <div className="absolute inset-x-2 bottom-2 flex items-end justify-between opacity-0 transition group-hover:opacity-100">
                          <p className="line-clamp-2 max-w-[60%] font-mono text-[10px] text-white/85">{prompt || tile.enhanced_prompt}</p>
                          <div className="flex gap-1">
                            {tileUrl && <Link href={`/editor?image=${encodeURIComponent(tileUrl)}`} title="Edit" className="glass-panel grid h-7 w-7 place-items-center rounded-lg"><Pencil className="h-3.5 w-3.5" /></Link>}
                            {tileUrl && <Link href={`/editor?tool=logo&image=${encodeURIComponent(tileUrl)}`} title="Logo overlay" className="glass-panel grid h-7 w-7 place-items-center rounded-lg"><Wand className="h-3.5 w-3.5" /></Link>}
                            {tileUrl && <Link href={`/editor?tool=upscale&image=${encodeURIComponent(tileUrl)}`} title="Upscale" className="glass-panel grid h-7 w-7 place-items-center rounded-lg"><ArrowUpToLine className="h-3.5 w-3.5" /></Link>}
                          </div>
                        </div>
                        <span className="glass-panel absolute left-2 top-2 rounded-md px-1.5 py-0.5 font-mono text-[10px] text-white/70">v{i + 1}</span>
                        <button onClick={() => setFocused(i)} title="Open" className="glass-panel absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-lg opacity-0 transition group-hover:opacity-100"><Maximize2 className="h-3.5 w-3.5" /></button>
                      </>
                    ) : (
                      <div className="absolute inset-0 grid place-items-center">
                        <div className="flex flex-col items-center gap-2 text-white/30">
                          <Sparkles className="h-8 w-8" />
                          <span className="kerned text-[10px]">Your image will appear here</span>
                        </div>
                      </div>
                    )}
                  </figure>
                );
              })}
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col gap-2">
              <div
                className={`relative flex flex-1 items-center justify-center rounded-2xl hairline bg-white/[0.02] ${focusZoom === "fit" ? "overflow-hidden" : "overflow-auto"}`}
                style={{ minHeight: 160 }}
                onWheel={(e) => {
                  if (!e.ctrlKey && !e.metaKey) return; // require Ctrl/Cmd to zoom (don't trap normal page scroll)
                  e.preventDefault();
                  setFocusZoom((cur) => {
                    const base = cur === "fit" ? 100 : cur;
                    const next = e.deltaY < 0 ? base + 25 : base - 25;
                    return Math.max(25, Math.min(400, next));
                  });
                }}
              >
                <img
                  ref={focusImgRef}
                  src={brandedImageUrl(visibleTiles[focused]?.image_url)}
                  alt=""
                  className={focusZoom === "fit" ? "max-h-full max-w-full object-contain" : "block"}
                  style={focusZoom === "fit"
                    ? undefined
                    : {
                        width: focusImgRef.current?.naturalWidth
                          ? `${(focusImgRef.current.naturalWidth * focusZoom) / 100}px`
                          : `${focusZoom}%`,
                        height: "auto",
                        maxWidth: "none",
                        maxHeight: "none",
                      }}
                />
                <button onClick={() => { setFocused(null); setFocusZoom("fit"); }} className="glass-panel absolute left-3 top-3 inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs"><ArrowLeft className="h-3.5 w-3.5" /> Back</button>
                <div className="absolute right-3 top-3 flex gap-1">
                  <Link href={`/editor?image=${encodeURIComponent(visibleTiles[focused]?.image_url || "")}`} className="glass-panel inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs"><Pencil className="h-3.5 w-3.5" /> Edit</Link>
                  <Link href={`/editor?tool=logo&image=${encodeURIComponent(visibleTiles[focused]?.image_url || "")}`} className="glass-panel inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs"><Wand className="h-3.5 w-3.5" /> Logo</Link>
                  <Link href={`/editor?tool=upscale&image=${encodeURIComponent(visibleTiles[focused]?.image_url || "")}`} className="glass-panel inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs"><ArrowUpToLine className="h-3.5 w-3.5" /> Upscale</Link>
                  <a href={brandedImageUrl(visibleTiles[focused]?.image_url)} download className="glass-panel inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs"><Download className="h-3.5 w-3.5" /></a>
                </div>
                {/* Zoom HUD */}
                <div className="glass-panel absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-full p-1 text-xs">
                  <button onClick={() => setFocusZoom("fit")} aria-pressed={focusZoom === "fit"} className={`grid h-7 w-7 place-items-center rounded-full ${focusZoom === "fit" ? "bg-white/15" : "hover:bg-white/10"}`} aria-label="Fit"><Maximize2 className="h-3.5 w-3.5" /></button>
                  <button onClick={() => setFocusZoom((cur) => Math.max(25, (cur === "fit" ? 100 : cur) - 25))} className="grid h-7 w-7 place-items-center rounded-full hover:bg-white/10" aria-label="Zoom out">−</button>
                  <span className="kerned px-1.5 font-mono text-[11px] text-white/70">{focusZoom === "fit" ? "Fit" : `${focusZoom}%`}</span>
                  <button onClick={() => setFocusZoom((cur) => Math.min(400, (cur === "fit" ? 100 : cur) + 25))} className="grid h-7 w-7 place-items-center rounded-full hover:bg-white/10" aria-label="Zoom in">+</button>
                  <button onClick={() => setFocusZoom(100)} aria-pressed={focusZoom === 100} className={`rounded-full px-2 py-1 ${focusZoom === 100 ? "bg-white/15" : "hover:bg-white/10"}`}>100%</button>
                </div>
              </div>
              {visibleTiles.length > 1 && (
                <div className="flex shrink-0 gap-2">
                  {visibleTiles.map((s, i) => (
                    <button key={i} onClick={() => { setFocused(i); setFocusZoom("fit"); }} className={`relative h-14 w-14 overflow-hidden rounded-lg ${focused === i ? "ring-2 ring-white" : "ring-1 ring-white/10"}`}>
                      <img src={brandedImageUrl(s.image_url)} alt="" className="h-full w-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>

        {/* RIGHT PANEL — Settings ↔ History tabbed inspector */}
        <aside className="no-scrollbar hidden min-h-0 space-y-3 overflow-y-auto pr-1 lg:block">
          {/* Tab toggle pill — matches editor */}
          <div className="glass-panel flex items-center gap-1 rounded-full p-1">
            <button
              onClick={() => setShowHistory(false)}
              className={`flex-1 rounded-full px-3 py-1.5 text-[11px] font-medium transition ${!showHistory ? "bg-white text-black" : "text-white/60 hover:bg-white/5"}`}
            >
              Settings
            </button>
            <button
              onClick={() => setShowHistory(true)}
              className={`flex-1 rounded-full px-3 py-1.5 text-[11px] font-medium transition ${showHistory ? "bg-white text-black" : "text-white/60 hover:bg-white/5"}`}
            >
              History
            </button>
          </div>

          {showHistory ? (
            <div className="glass-panel rounded-2xl p-3">
              <header className="mb-2.5">
                <h3 className="text-[13px] font-semibold tracking-tight text-white">History</h3>
                <p className="mt-0.5 text-[11px] leading-snug text-white/55">Your recent renders. Click any to load it as the current result.</p>
              </header>
              {historyLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-white/30" />
                </div>
              ) : history.length === 0 ? (
                <div className="rounded-lg border border-white/[0.08] bg-white/[0.015] p-4 text-center">
                  <p className="text-[11px] text-white/45">No generations yet — your renders will appear here.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-1.5">
                  {history.map((h) => (
                    <button
                      key={h.id}
                      onClick={() => {
                        setResult({ success: true, image_url: h.url, enhanced_prompt: h.prompt });
                        setMultiResults([]);
                        setFocused(0);
                        // stay on History tab — user can keep browsing
                      }}
                      title={h.prompt}
                      className="group relative aspect-square overflow-hidden rounded-md hairline"
                    >
                      <img src={brandedImageUrl(h.url)} alt="" loading="lazy" className="h-full w-full object-cover transition group-hover:scale-105" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <Inspector
              activeType={activeTypeMeta}
              style={style} setStyle={setStyle}
              ratio={ratio} setRatio={setRatio}
              customMode={customMode} setCustomMode={setCustomMode}
              customW={customW} setCustomW={setCustomW}
              customH={customH} setCustomH={setCustomH}
              quality={quality} setQuality={setQuality}
              guidance={guidance} setGuidance={setGuidance}
              negative={negative} setNegative={setNegative}
              seed={seed} setSeed={setSeed}
              locked={locked} setLocked={setLocked}
              showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced}
              refPeople={refPeople}
              refProducts={refProducts}
              refLogos={refLogos}
              refExtras={refExtras}
              onSlotUpload={triggerSlotUpload}
              onSlotItemRemove={(slot, idx) => {
                if (slot === "people") setRefPeople((p) => p.filter((_, i) => i !== idx));
                else if (slot === "products") setRefProducts((p) => p.filter((_, i) => i !== idx));
                else if (slot === "logos") setRefLogos((p) => p.filter((_, i) => i !== idx));
                else setRefExtras((p) => p.filter((_, i) => i !== idx));
              }}
            />
          )}
        </aside>
      </div>

      {/* ── MOBILE BOTTOM SHEET — Settings / History ── */}
      {mobileSheetOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close"
            onClick={() => setMobileSheetOpen(false)}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          <div
            className="absolute inset-x-0 bottom-0 max-h-[88vh] overflow-y-auto rounded-t-3xl border-t border-white/10 p-3"
            style={{ background: "var(--ink-soft)" }}
          >
            <div className="mx-auto mb-2 h-1.5 w-12 rounded-full bg-white/20" />
            {/* Settings/History tab pill — matches desktop */}
            <div className="glass-panel mb-3 flex items-center gap-1 rounded-full p-1">
              <button
                onClick={() => setShowHistory(false)}
                className={`flex-1 rounded-full px-3 py-1.5 text-[11px] font-medium transition ${!showHistory ? "bg-white text-black" : "text-white/60"}`}
              >Settings</button>
              <button
                onClick={() => setShowHistory(true)}
                className={`flex-1 rounded-full px-3 py-1.5 text-[11px] font-medium transition ${showHistory ? "bg-white text-black" : "text-white/60"}`}
              >History</button>
            </div>
            {/* Mobile: Type pills row above settings (always visible) */}
            {!showHistory && (
              <div className="no-scrollbar mb-3 flex items-center gap-1 overflow-x-auto">
                <button
                  onClick={() => setActiveType("auto")}
                  className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium transition ${activeType === "auto" ? "bg-white text-black" : "border border-white/10 bg-white/[0.03] text-white/65"}`}
                >Auto</button>
                {types.filter((t) => t.id !== "fast").map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setActiveType(t.id)}
                    className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium transition ${activeType === t.id ? "bg-white text-black" : "border border-white/10 bg-white/[0.03] text-white/65"}`}
                  >{t.name}</button>
                ))}
              </div>
            )}
            {showHistory ? (
              <div className="glass-panel rounded-2xl p-3">
                <p className="kerned mb-2 text-white/55">History</p>
                {historyLoading ? (
                  <div className="flex items-center justify-center py-12"><Loader2 className="h-5 w-5 animate-spin text-white/30" /></div>
                ) : history.length === 0 ? (
                  <p className="text-[11px] text-white/45">No generations yet.</p>
                ) : (
                  <div className="grid grid-cols-3 gap-1.5">
                    {history.map((h) => (
                      <button
                        key={h.id}
                        onClick={() => {
                          setResult({ success: true, image_url: h.url, enhanced_prompt: h.prompt });
                          setMultiResults([]);
                          setFocused(0);
                          setMobileSheetOpen(false);
                        }}
                        title={h.prompt}
                        className="group relative aspect-square overflow-hidden rounded-md hairline"
                      >
                        <img src={brandedImageUrl(h.url)} alt="" loading="lazy" className="h-full w-full object-cover" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <Inspector
                activeType={activeTypeMeta}
                style={style} setStyle={setStyle}
                ratio={ratio} setRatio={setRatio}
                customMode={customMode} setCustomMode={setCustomMode}
                customW={customW} setCustomW={setCustomW}
                customH={customH} setCustomH={setCustomH}
                quality={quality} setQuality={setQuality}
                guidance={guidance} setGuidance={setGuidance}
                negative={negative} setNegative={setNegative}
                seed={seed} setSeed={setSeed}
                locked={locked} setLocked={setLocked}
                showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced}
                refPeople={refPeople}
                refProducts={refProducts}
                refLogos={refLogos}
                refExtras={refExtras}
                onSlotUpload={triggerSlotUpload}
                onSlotItemRemove={(slot, idx) => {
                  if (slot === "people") setRefPeople((p) => p.filter((_, i) => i !== idx));
                  else if (slot === "products") setRefProducts((p) => p.filter((_, i) => i !== idx));
                  else if (slot === "logos") setRefLogos((p) => p.filter((_, i) => i !== idx));
                  else setRefExtras((p) => p.filter((_, i) => i !== idx));
                }}
              />
            )}
          </div>
        </div>
      )}

      {/* ── STICKY PROMPT BAR ── */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 pb-[88px] backdrop-blur-xl lg:pb-0" style={{ background: "color-mix(in oklab, var(--ink) 88%, transparent)" }}>
        <div className="mx-auto max-w-[1480px] px-2 py-2.5 sm:px-4">
          {suggestions.length > 0 && !isGenerating && (
            <div className="mb-2 flex gap-1.5 overflow-x-auto px-1 pb-1">
              <span className="kerned shrink-0 self-center text-white/40">Try</span>
              {suggestions.map((s, i) => (
                <button key={i} onClick={() => setPrompt(s)} className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-white/75 hover:bg-white/10">
                  {s.length > 60 ? s.slice(0, 60) + "…" : s}
                </button>
              ))}
            </div>
          )}

          <div className="glass-panel relative flex items-end gap-1.5 rounded-2xl p-2">
            {/* + references */}
            <div className="relative">
              <button
                onClick={() => setRefsOpen((v) => !v)}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/5 hover:bg-white/10"
                aria-label="Add references"
              >
                <Plus className="h-4 w-4" />
              </button>
              {refsOpen && (
                <div className="glass-panel absolute bottom-12 left-0 z-50 w-60 rounded-2xl p-2 text-sm" style={{ boxShadow: "var(--shadow-float)" }}>
                  <button
                    onClick={() => refFileInput.current?.click()}
                    disabled={referenceImages.length >= MAX_REFS}
                    className="flex w-full items-start gap-2.5 rounded-xl p-2 text-left hover:bg-white/5 disabled:opacity-40"
                  >
                    <ImageIcon className="mt-0.5 h-4 w-4 text-white/60" />
                    <div>
                      <p className="text-[13px]">Reference image</p>
                      <p className="kerned text-white/40">{referenceImages.length}/{MAX_REFS} added</p>
                    </div>
                  </button>
                  <button onClick={() => setRefsOpen(false)} className="flex w-full items-start gap-2.5 rounded-xl p-2 text-left hover:bg-white/5 opacity-50">
                    <Type className="mt-0.5 h-4 w-4" />
                    <div>
                      <p className="text-[13px]">Character ref</p>
                      <p className="kerned text-white/40">Coming soon</p>
                    </div>
                  </button>
                </div>
              )}
            </div>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) generate(); }}
              placeholder="Describe what you want to see — ⌘+Enter to generate"
              rows={1}
              className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-white/30"
            />

            <button onClick={() => setSettingsOpen(true)} className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-white/5 hover:bg-white/10 lg:hidden" aria-label="Settings">
              <SlidersHorizontal className="h-4 w-4" />
            </button>

            <div className="hidden items-center gap-0.5 rounded-xl bg-white/5 p-0.5 sm:flex">
              {batches.map((b) => (
                <button
                  key={b}
                  onClick={() => setBatch(b)}
                  className={`h-8 w-7 rounded-lg text-[11px] ${batch === b ? "bg-white text-black" : "text-white/65 hover:bg-white/10"}`}
                >{b}</button>
              ))}
            </div>

            <button
              onClick={generate}
              disabled={isGenerating || prompt.trim().length < 3}
              className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl px-4 text-sm font-medium text-black disabled:opacity-60"
              style={{ background: "var(--gradient-aurora)", boxShadow: "var(--shadow-glow)" }}
            >
              {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {isGenerating ? "Generating…" : "Generate"}
            </button>
          </div>

          <div className="mt-1.5 flex items-center justify-between gap-2 px-2 text-[10px] text-white/45">
            <span className="kerned truncate">
              {activeType === "auto" ? "Auto" : activeTypeMeta.name} · {style} · {ratio} · {activeQuality.name}
            </span>
          </div>
        </div>
      </div>

      {/* ── MOBILE SETTINGS SHEET ── */}
      {settingsOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSettingsOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-3xl border-t border-white/10 p-4" style={{ backgroundColor: "#16161a" }}>
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-white/15" />
            <div className="mb-3 flex items-center justify-between">
              <p className="font-display text-xl">Settings</p>
              <button onClick={() => setSettingsOpen(false)} className="grid h-8 w-8 place-items-center rounded-full bg-white/5"><X className="h-4 w-4" /></button>
            </div>
            <Inspector
              activeType={activeTypeMeta}
              style={style} setStyle={setStyle}
              ratio={ratio} setRatio={setRatio}
              customMode={customMode} setCustomMode={setCustomMode}
              customW={customW} setCustomW={setCustomW}
              customH={customH} setCustomH={setCustomH}
              quality={quality} setQuality={setQuality}
              guidance={guidance} setGuidance={setGuidance}
              negative={negative} setNegative={setNegative}
              seed={seed} setSeed={setSeed}
              locked={locked} setLocked={setLocked}
              showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced}
              refPeople={refPeople}
              refProducts={refProducts}
              refLogos={refLogos}
              refExtras={refExtras}
              onSlotUpload={triggerSlotUpload}
              onSlotItemRemove={(slot, idx) => {
                if (slot === "people") setRefPeople((p) => p.filter((_, i) => i !== idx));
                else if (slot === "products") setRefProducts((p) => p.filter((_, i) => i !== idx));
                else if (slot === "logos") setRefLogos((p) => p.filter((_, i) => i !== idx));
                else setRefExtras((p) => p.filter((_, i) => i !== idx));
              }}
            />
          </div>
        </div>
      )}

    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Inspector
// ─────────────────────────────────────────────────────────────────────────────
type InspectorProps = {
  activeType: typeof types[number];
  style: string; setStyle: (v: string) => void;
  ratio: string; setRatio: (v: string) => void;
  customMode: boolean; setCustomMode: (v: boolean) => void;
  customW: number; setCustomW: (v: number) => void;
  customH: number; setCustomH: (v: number) => void;
  quality: string; setQuality: (v: string) => void;
  guidance: number; setGuidance: (v: number) => void;
  negative: string; setNegative: (v: string) => void;
  seed: string; setSeed: (v: string) => void;
  locked: boolean; setLocked: (v: boolean) => void;
  showAdvanced: boolean; setShowAdvanced: (v: boolean) => void;
  // Slotted multi-image references — each slot accepts 1+ images
  refPeople: string[];
  refProducts: string[];
  refLogos: string[];
  refExtras: string[];
  onSlotUpload: (slot: "people" | "products" | "logos" | "extras") => void;
  onSlotItemRemove: (slot: "people" | "products" | "logos" | "extras", idx: number) => void;
};

function Inspector(p: InspectorProps) {
  const styleOptions = ["Auto", ...styleList];
  return (
    <div className="glass-panel rounded-2xl p-3">
      <header className="mb-2.5">
        <h3 className="text-[13px] font-semibold tracking-tight text-white">Settings</h3>
        <p className="mt-0.5 text-[11px] leading-snug text-white/55">Upload references, pick a style, set aspect & quality.</p>
      </header>

      <div className="space-y-2">
        {/* REFERENCES — multi-image slots (People / Products / Logos) + extras */}
        <section className="rounded-lg border border-white/[0.08] bg-white/[0.015] p-2.5">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/65">References</h4>
            <span className="font-mono text-[10px] text-white/55">
              {p.refPeople.length + p.refProducts.length + p.refLogos.length + p.refExtras.length}
            </span>
          </div>
          <p className="mb-2.5 text-[10.5px] leading-snug text-white/50">
            Tell the AI <em>what</em> each image is. Each slot accepts multiple — couples, product variants, multi-mark brands.
          </p>

          {/* Named slots — stacked, each with its own thumb row */}
          <div className="space-y-2">
            {([
              { key: "people",   label: "People",   hint: "Model, actor, couple, group — up to 4", Icon: Users,   cap: 4, value: p.refPeople },
              { key: "products", label: "Products", hint: "Item(s) to feature — up to 4 variants",  Icon: Package, cap: 4, value: p.refProducts },
              { key: "logos",    label: "Logos",    hint: "Primary + secondary brand mark",         Icon: Stamp,   cap: 2, value: p.refLogos },
            ] as const).map((s) => (
              <div key={s.key} className="rounded-md border border-white/[0.06] bg-white/[0.015] p-1.5">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <s.Icon className="h-3.5 w-3.5 text-white/55" />
                    <span className="text-[10.5px] font-medium text-white/85">{s.label}</span>
                    <span className="font-mono text-[9.5px] text-white/40">{s.value.length}/{s.cap}</span>
                  </div>
                  <span className="hidden text-[9.5px] text-white/35 sm:block">{s.hint}</span>
                </div>
                <div className="flex flex-wrap items-center gap-1">
                  {s.value.map((url, i) => (
                    <div key={i} className="group relative h-11 w-11 overflow-hidden rounded-md hairline">
                      <img src={url} alt={`${s.label} ${i + 1}`} className="h-full w-full object-cover" />
                      <span className="absolute left-0.5 top-0.5 rounded bg-black/60 px-1 font-mono text-[8.5px] text-white/90">{i + 1}</span>
                      <button
                        onClick={() => p.onSlotItemRemove(s.key, i)}
                        className="absolute right-0.5 top-0.5 grid h-4 w-4 place-items-center rounded-full bg-black/70 text-[9px] text-white opacity-0 transition group-hover:opacity-100"
                        aria-label="Remove"
                      >×</button>
                    </div>
                  ))}
                  {s.value.length < s.cap && (
                    <button
                      onClick={() => p.onSlotUpload(s.key)}
                      title={`Add ${s.label.toLowerCase()} reference`}
                      className="grid h-11 w-11 place-items-center rounded-md border border-dashed border-white/15 text-white/40 transition hover:border-white/30 hover:bg-white/[0.04] hover:text-white/70"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Extras pool */}
          <div className="mt-2 rounded-md border border-white/[0.06] bg-white/[0.015] p-1.5">
            <div className="mb-1 flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5">
                <ImageIcon className="h-3.5 w-3.5 text-white/55" />
                <span className="text-[10.5px] font-medium text-white/85">Other</span>
                <span className="font-mono text-[9.5px] text-white/40">{p.refExtras.length}/2</span>
              </div>
              <span className="hidden text-[9.5px] text-white/35 sm:block">Background, mood, style</span>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              {p.refExtras.map((url, i) => (
                <div key={i} className="group relative h-11 w-11 overflow-hidden rounded-md hairline">
                  <img src={url} alt={`Other ${i + 1}`} className="h-full w-full object-cover" />
                  <button
                    onClick={() => p.onSlotItemRemove("extras", i)}
                    className="absolute right-0.5 top-0.5 grid h-4 w-4 place-items-center rounded-full bg-black/70 text-[9px] text-white opacity-0 transition group-hover:opacity-100"
                    aria-label="Remove"
                  >×</button>
                </div>
              ))}
              {p.refExtras.length < 2 && (
                <button
                  onClick={() => p.onSlotUpload("extras")}
                  title="Add another reference"
                  className="grid h-11 w-11 place-items-center rounded-md border border-dashed border-white/15 text-white/40 transition hover:border-white/30 hover:bg-white/[0.04] hover:text-white/70"
                >
                  <Plus className="h-4 w-4" />
                </button>
              )}
            </div>
            <p className="mt-1 text-[9.5px] text-white/35">
              Describe role in your prompt: &quot;blend product into scene from Other 1&quot;.
            </p>
          </div>
        </section>

        {/* STYLE — visual thumbnail grid */}
        <section className="rounded-lg border border-white/[0.08] bg-white/[0.015] p-2.5">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/65">Style</h4>
            <span className="font-mono text-[10px] text-white/55">{p.style}</span>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {/* "Auto" tile uses a gradient placeholder */}
            <button
              onClick={() => p.setStyle("Auto")}
              title="Auto — let the AI pick"
              className={`group relative aspect-square overflow-hidden rounded-md transition ${p.style === "Auto" ? "ring-2 ring-white" : "ring-1 ring-white/[0.08] hover:ring-white/25"}`}
            >
              <div className="grid h-full w-full place-items-center" style={{ background: "var(--gradient-aurora)" }}>
                <Wand className="h-4 w-4 text-black/70" />
              </div>
              <span className="absolute inset-x-0 bottom-0 truncate bg-linear-to-t from-black/85 via-black/40 to-transparent px-1 pt-3 pb-0.5 text-center text-[9px] font-medium text-white">
                Auto
              </span>
            </button>
            {styleList.map((s) => {
              const src = STYLE_PREVIEWS[s] || STYLE_FALLBACK;
              return (
                <button
                  key={s}
                  onClick={() => p.setStyle(s)}
                  title={s}
                  className={`group relative aspect-square overflow-hidden rounded-md transition ${p.style === s ? "ring-2 ring-white" : "ring-1 ring-white/[0.08] hover:ring-white/25"}`}
                >
                  <img src={src} alt={s} className="h-full w-full object-cover transition group-hover:scale-105" />
                  <span className="absolute inset-x-0 bottom-0 truncate bg-linear-to-t from-black/85 via-black/40 to-transparent px-1 pt-3 pb-0.5 text-center text-[9px] font-medium text-white">
                    {s}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        {/* ASPECT */}
        <section className="rounded-lg border border-white/[0.08] bg-white/[0.015] p-2.5">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/65">Aspect</h4>
            <span className="font-mono text-[10px] text-white/55">{p.customMode ? `${p.customW}×${p.customH}` : p.ratio}</span>
          </div>
          <div className="no-scrollbar -mx-2.5 flex gap-1 overflow-x-auto px-2.5 pb-0.5">
            {ratios.map((r) => {
              const active = !p.customMode && p.ratio === r.id;
              const box = 22;
              const rw = r.vw >= r.vh ? box : (box * r.vw) / r.vh;
              const rh = r.vh >= r.vw ? box : (box * r.vh) / r.vw;
              return (
                <button
                  key={r.id}
                  onClick={() => { p.setRatio(r.id); p.setCustomMode(false); }}
                  title={r.id}
                  className={`flex h-12 w-12 shrink-0 flex-col items-center justify-center gap-0.5 rounded-md border transition ${active ? "border-white/40 bg-white/[0.08]" : "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.05]"}`}
                >
                  <span className="block rounded-[1.5px] border border-white/70" style={{ width: rw, height: rh }} />
                  <span className="font-mono text-[8.5px] text-white/55">{r.id}</span>
                </button>
              );
            })}
            <button
              onClick={() => p.setCustomMode(true)}
              title="Custom dimensions"
              className={`flex h-12 w-12 shrink-0 flex-col items-center justify-center gap-0.5 rounded-md border transition ${p.customMode ? "border-white/40 bg-white/[0.08]" : "border-dashed border-white/15 bg-white/[0.02] hover:bg-white/[0.05]"}`}
            >
              <Settings2 className="h-3.5 w-3.5 text-white/55" />
              <span className="font-mono text-[8.5px] text-white/55">Custom</span>
            </button>
          </div>
          {p.customMode && (
            <div className="mt-2 flex items-end gap-2">
              <label className="flex-1 block">
                <span className="mb-0.5 block text-[10px] uppercase tracking-wider text-white/45">Width</span>
                <input
                  type="number"
                  min={256} max={4096} step={64}
                  value={p.customW}
                  onChange={(e) => p.setCustomW(Math.max(256, Math.min(4096, +e.target.value || 1024)))}
                  className="w-full rounded-md border border-white/10 bg-black/30 p-1.5 font-mono text-[11px] outline-none focus:border-white/30"
                />
              </label>
              <span className="pb-1.5 text-white/30">×</span>
              <label className="flex-1 block">
                <span className="mb-0.5 block text-[10px] uppercase tracking-wider text-white/45">Height</span>
                <input
                  type="number"
                  min={256} max={4096} step={64}
                  value={p.customH}
                  onChange={(e) => p.setCustomH(Math.max(256, Math.min(4096, +e.target.value || 1024)))}
                  className="w-full rounded-md border border-white/10 bg-black/30 p-1.5 font-mono text-[11px] outline-none focus:border-white/30"
                />
              </label>
            </div>
          )}
        </section>

        {/* QUALITY */}
        <section className="rounded-lg border border-white/[0.08] bg-white/[0.015] p-2.5">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <h4 className="text-[10px] font-semibold uppercase tracking-[0.08em] text-white/65">Quality</h4>
            <span className="font-mono text-[10px] text-white/55">{p.quality.toUpperCase()}</span>
          </div>
          <div className="grid grid-cols-3 gap-1">
            {qualities.map((q) => (
              <button
                key={q.id}
                onClick={() => p.setQuality(q.id)}
                className={`rounded-md border py-2 text-center transition ${p.quality === q.id ? "border-white/40 bg-white/[0.1]" : "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.05]"}`}
              >
                <p className="font-display text-sm font-medium">{q.name}</p>
              </button>
            ))}
          </div>
          <div className="mt-2">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-white/45">
                <Gauge className="h-3 w-3" /> Guidance
              </span>
              <span className="font-mono text-[10px] text-white/70">{p.guidance.toFixed(1)}</span>
            </div>
            <input
              type="range" min={1} max={20} step={0.5}
              value={p.guidance}
              onChange={(e) => p.setGuidance(+e.target.value)}
              className="w-full accent-white"
            />
          </div>
        </section>

        {/* ADVANCED */}
        <button
          onClick={() => p.setShowAdvanced(!p.showAdvanced)}
          className="flex w-full items-center justify-between rounded-md px-1 py-1 text-[11px] text-white/55 transition hover:text-white"
        >
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em]">Advanced</span>
          <ChevronDown className={`h-3.5 w-3.5 transition ${p.showAdvanced ? "rotate-180" : ""}`} />
        </button>
        {p.showAdvanced && (
          <section className="rounded-lg border border-white/[0.08] bg-white/[0.015] p-2.5 space-y-2.5">
            <div>
              <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-white/65">Negative prompt</h4>
              <textarea
                value={p.negative}
                onChange={(e) => p.setNegative(e.target.value)}
                placeholder="blur, lowres, watermark…"
                className="min-h-14 w-full resize-none rounded-md border border-white/10 bg-black/30 p-2 font-mono text-[11px] outline-none placeholder:text-white/25 focus:border-white/30"
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-1.5">
                <Settings2 className="h-3 w-3 shrink-0 text-white/40" />
                <span className="text-[10px] uppercase tracking-wider text-white/45">Seed</span>
                <span className="truncate font-mono text-[11px] text-white/80">{p.seed}</span>
              </div>
              <div className="flex gap-1">
                <button
                  onClick={() => p.setLocked(!p.locked)}
                  className={`rounded p-1.5 transition ${p.locked ? "bg-white/15 text-white" : "bg-white/[0.04] text-white/60 hover:bg-white/10"}`}
                  aria-label="Lock seed"
                  title={p.locked ? "Seed locked — same image each time" : "Lock seed"}
                ><Lock className="h-3 w-3" /></button>
                <button
                  onClick={() => p.setSeed(String(Math.floor(Math.random() * 999999)))}
                  className="rounded bg-white/[0.04] p-1.5 text-white/60 transition hover:bg-white/10 hover:text-white"
                  aria-label="Random seed"
                  title="Randomize seed"
                ><Shuffle className="h-3 w-3" /></button>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
