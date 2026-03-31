"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Zap, Sparkles, Loader2, CheckCircle2 } from "lucide-react";
import { GradientButton } from "@/components/ui/gradient-button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { generatePreview, generateFullQuality, FULL_QUALITY_DELAY_MS } from "@/lib/instantMagicPreview";
import { cn } from "@/lib/utils";

type Phase = "idle" | "generating_preview" | "preview_ready" | "polishing" | "complete";

export default function InstantMagicPreview() {
  const [prompt, setPrompt] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [previewData, setPreviewData] = useState<{
    preview_image: string;
    message: string;
    estimated_time: string;
    quality_level: string;
  } | null>(null);
  const [finalImage, setFinalImage] = useState<string | null>(null);
  const [polishProgress, setPolishProgress] = useState(0);

  const runGeneration = useCallback(async () => {
    const p = prompt.trim() || "Fantasy portrait with soft lighting";
    setPhase("generating_preview");
    setPreviewData(null);
    setFinalImage(null);
    setPolishProgress(0);

    try {
      const preview = await generatePreview(p);
      setPreviewData(preview);
      setPhase("preview_ready");
      await new Promise((r) => setTimeout(r, 800));
      setPhase("polishing");

      const start = Date.now();
      const duration = FULL_QUALITY_DELAY_MS;
      const tick = () => {
        const elapsed = Date.now() - start;
        const value = Math.min(100, (elapsed / duration) * 100);
        setPolishProgress(value);
        if (value < 100) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);

      const full = await generateFullQuality(p);
      setFinalImage(full.final_image);
      setPolishProgress(100);
      setPhase("complete");
    } catch (e) {
      console.error(e);
      setPhase("idle");
    }
  }, [prompt]);

  const reset = useCallback(() => {
    setPhase("idle");
    setPreviewData(null);
    setFinalImage(null);
    setPolishProgress(0);
  }, []);

  return (
    <section id="instant-magic-preview" className="relative py-24 px-4 overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-0 w-1/2 h-96 bg-primary/5 blur-3xl rounded-full" />
        <div className="absolute top-1/2 right-0 w-1/2 h-96 bg-secondary/5 blur-3xl rounded-full" />
      </div>

      <div className="relative max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-card mb-6">
            <Zap className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-muted-foreground">First impression = everything</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Instant Magic <span className="gradient-text">Preview</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Preview in ~3 seconds, then we polish full quality (~25s).
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="glass-card rounded-2xl p-6 md:p-8 space-y-6"
        >
          {(phase === "idle" || phase === "generating_preview") && (
            <div className="flex flex-col sm:flex-row gap-3">
              <Input
                placeholder="Describe your portrait (e.g. fantasy glamour, soft neon)"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runGeneration()}
                disabled={phase === "generating_preview"}
                className="flex-1 rounded-xl h-12"
              />
              <GradientButton
                size="lg"
                variant="glow"
                onClick={runGeneration}
                disabled={phase === "generating_preview"}
                className="rounded-xl min-w-[140px]"
              >
                {phase === "generating_preview" ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Generate
                  </>
                )}
              </GradientButton>
            </div>
          )}

          <AnimatePresence mode="wait">
            {phase === "generating_preview" && (
              <motion.div
                key="preview-loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="rounded-xl bg-muted/50 aspect-[4/5] max-h-[420px] flex flex-col items-center justify-center gap-4"
              >
                <Loader2 className="w-12 h-12 text-primary animate-spin" />
                <p className="text-muted-foreground font-medium">Generating preview...</p>
                <p className="text-sm text-muted-foreground/80">0-3 sec, SDXL-Turbo</p>
              </motion.div>
            )}

            {(phase === "preview_ready" || phase === "polishing" || phase === "complete") && previewData && (
              <motion.div
                key="preview-result"
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-4"
              >
                <div className="relative rounded-xl overflow-hidden bg-muted/30 aspect-[4/5] max-h-[420px]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={finalImage ?? previewData.preview_image}
                    alt="Generated preview"
                    className={cn("w-full h-full object-cover transition-all duration-500", finalImage && "ring-2 ring-primary/50")}
                  />
                  {phase === "complete" && (
                    <div className="absolute top-3 right-3 px-3 py-1.5 rounded-full bg-primary/90 text-primary-foreground text-xs font-semibold flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Best-of-2
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <AnimatePresence mode="wait">
                    {phase === "preview_ready" && (
                      <motion.div
                        key="preview-msg"
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        className="flex flex-wrap items-center gap-2"
                      >
                        <span className="text-primary font-medium">Quick preview ready!</span>
                        <span className="text-muted-foreground">Generating full quality...</span>
                      </motion.div>
                    )}
                    {phase === "polishing" && (
                      <motion.p key="polish-msg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-muted-foreground">
                        Polishing full quality...
                      </motion.p>
                    )}
                    {phase === "complete" && (
                      <motion.p
                        key="done-msg"
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="text-primary font-medium flex items-center gap-2"
                      >
                        <CheckCircle2 className="w-4 h-4" />
                        Final best-of-2 ready
                      </motion.p>
                    )}
                  </AnimatePresence>

                  {phase === "preview_ready" && (
                    <p className="text-sm text-muted-foreground">
                      Estimated time: {previewData.estimated_time}. {previewData.quality_level}
                    </p>
                  )}

                  {(phase === "polishing" || phase === "complete") && (
                    <Progress value={polishProgress} className="h-2" />
                  )}
                </div>

                {phase === "complete" && (
                  <GradientButton variant="outline" onClick={reset} className="w-full sm:w-auto">
                    Generate another
                  </GradientButton>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  );
}
