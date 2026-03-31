/**
 * PhotoGenius UI v2 – World-Class Frontend
 * P1: Production UI with advanced controls.
 *
 * Features:
 * - Quality tier slider (STANDARD / PREMIUM / PERFECT)
 * - Physics toggles (wetness, lighting, gravity)
 * - Iteration count selector
 * - Real-time progress with previews
 * - "Surprise Me" mode (boosts surprise reward)
 *
 * Success Metric: 95%+ user satisfaction, <1% confusion rate.
 * Use: import PhotogeniusUIv2 from './frontend/photogenius-ui-v2.jsx' (or mount in React app).
 */

import React, { useState, useCallback } from "react";

// --- Constants ---
const QUALITY_TIERS = [
  { id: "STANDARD", label: "Standard", description: "Fast, good quality", time: "~15s" },
  { id: "PREMIUM", label: "Premium", description: "Better detail & consistency", time: "~25s" },
  { id: "PERFECT", label: "Perfect", description: "Highest quality, best for final art", time: "~45s" },
];

const ITERATION_OPTIONS = [1, 2, 4];

const PHYSICS_OPTIONS = [
  { id: "wetness", label: "Wetness", description: "Surface moisture & reflections" },
  { id: "lighting", label: "Lighting", description: "Realistic shadows & highlights" },
  { id: "gravity", label: "Gravity", description: "Natural fall and weight" },
];

// --- Styles (inline for portability; override via props or CSS) ---
const styles = {
  container: {
    maxWidth: 640,
    margin: "0 auto",
    padding: 24,
    fontFamily: "system-ui, -apple-system, sans-serif",
    color: "#fafafa",
    background: "linear-gradient(180deg, rgba(15,15,18,0.98) 0%, rgba(12,12,15,0.99) 100%)",
    borderRadius: 16,
    border: "1px solid rgba(255,255,255,0.06)",
  },
  section: { marginBottom: 24 },
  label: { fontSize: 12, fontWeight: 600, color: "rgba(255,255,255,0.5)", marginBottom: 8, display: "block" },
  sliderTrack: {
    height: 40,
    borderRadius: 12,
    background: "rgba(255,255,255,0.06)",
    display: "flex",
    padding: 4,
    gap: 4,
  },
  sliderSegment: (active) => ({
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
    cursor: "pointer",
    background: active ? "rgba(59, 130, 246, 0.25)" : "transparent",
    border: active ? "1px solid rgba(59, 130, 246, 0.5)" : "1px solid transparent",
    color: active ? "#93c5fd" : "rgba(255,255,255,0.6)",
    fontWeight: active ? 600 : 500,
    fontSize: 13,
  }),
  toggleRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "10px 12px",
    borderRadius: 10,
    background: "rgba(255,255,255,0.03)",
    marginBottom: 6,
    border: "1px solid rgba(255,255,255,0.05)",
  },
  toggleSwitch: (on) => ({
    width: 40,
    height: 22,
    borderRadius: 11,
    background: on ? "#3b82f6" : "rgba(255,255,255,0.12)",
    position: "relative",
    cursor: "pointer",
    transition: "background 0.2s",
  }),
  toggleKnob: (on) => ({
    width: 18,
    height: 18,
    borderRadius: "50%",
    background: "#fff",
    position: "absolute",
    top: 2,
    left: on ? 20 : 2,
    transition: "left 0.2s",
  }),
  iterationChips: { display: "flex", gap: 8, flexWrap: "wrap" },
  chip: (active) => ({
    padding: "8px 16px",
    borderRadius: 10,
    border: active ? "1px solid rgba(59, 130, 246, 0.6)" : "1px solid rgba(255,255,255,0.1)",
    background: active ? "rgba(59, 130, 246, 0.15)" : "rgba(255,255,255,0.04)",
    color: active ? "#93c5fd" : "rgba(255,255,255,0.7)",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: active ? 600 : 500,
  }),
  surpriseBanner: (on) => ({
    padding: 14,
    borderRadius: 12,
    border: on ? "1px solid rgba(234, 179, 8, 0.4)" : "1px solid rgba(255,255,255,0.08)",
    background: on ? "rgba(234, 179, 8, 0.12)" : "rgba(255,255,255,0.03)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 20,
  }),
  progressBar: {
    height: 6,
    borderRadius: 3,
    background: "rgba(255,255,255,0.08)",
    overflow: "hidden",
    marginBottom: 8,
  },
  progressFill: (pct) => ({
    height: "100%",
    width: `${pct}%`,
    background: "linear-gradient(90deg, #3b82f6, #8b5cf6)",
    borderRadius: 3,
    transition: "width 0.3s ease",
  }),
  previewBox: {
    aspectRatio: "1",
    maxHeight: 320,
    borderRadius: 12,
    background: "rgba(0,0,0,0.3)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    marginTop: 12,
    border: "1px solid rgba(255,255,255,0.06)",
  },
  previewImg: { width: "100%", height: "100%", objectFit: "cover" },
  textarea: {
    width: "100%",
    minHeight: 88,
    padding: 14,
    borderRadius: 12,
    border: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(255,255,255,0.04)",
    color: "#fafafa",
    fontSize: 14,
    resize: "vertical",
    boxSizing: "border-box",
  },
  button: (primary) => ({
    padding: "12px 24px",
    borderRadius: 12,
    border: "none",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    background: primary
      ? "linear-gradient(135deg, #3b82f6, #6366f1)"
      : "rgba(255,255,255,0.08)",
    color: primary ? "#fff" : "rgba(255,255,255,0.9)",
    border: primary ? "none" : "1px solid rgba(255,255,255,0.1)",
  }),
  error: {
    padding: 12,
    borderRadius: 10,
    background: "rgba(239, 68, 68, 0.15)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    color: "#fca5a5",
    fontSize: 13,
    marginTop: 12,
  },
};

// --- Toggle component ---
function Toggle({ on, onChange, "aria-label": ariaLabel }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      style={styles.toggleSwitch(on)}
      onClick={() => onChange(!on)}
    >
      <span style={styles.toggleKnob(on)} />
    </button>
  );
}

/**
 * PhotogeniusUIv2 – main component
 * Props:
 *   - onSubmit: (params) => Promise<void>
 *     params: { prompt, quality_tier, iterations, physics: { wetness, lighting, gravity }, surpriseMe, mode? }
 *   - onProgress?: (data) => void  e.g. { progress, step, previewImage? }
 *   - progress?: number 0–100
 *   - currentStep?: string
 *   - previewImage?: string (data URL or URL)
 *   - error?: string
 *   - resultImages?: string[]
 *   - disabled?: boolean
 */
export function PhotogeniusUIv2({
  onSubmit,
  onProgress,
  progress = 0,
  currentStep = "",
  previewImage = null,
  error = null,
  resultImages = [],
  disabled = false,
}) {
  const [prompt, setPrompt] = useState("");
  const [qualityTier, setQualityTier] = useState("PREMIUM");
  const [iterations, setIterations] = useState(2);
  const [physics, setPhysics] = useState({ wetness: true, lighting: true, gravity: false });
  const [surpriseMe, setSurpriseMe] = useState(false);

  const handleSubmit = useCallback(
    (e) => {
      e?.preventDefault();
      if (!prompt.trim() || disabled) return;
      onSubmit({
        prompt: prompt.trim(),
        quality_tier: qualityTier,
        iterations,
        physics: { ...physics },
        surpriseMe,
        mode: surpriseMe ? "MAX_SURPRISE" : "REALISM",
      });
    },
    [prompt, qualityTier, iterations, physics, surpriseMe, disabled, onSubmit]
  );

  const isGenerating = progress > 0 && progress < 100 && !error;

  return (
    <div style={styles.container} className="photogenius-ui-v2">
      <form onSubmit={handleSubmit}>
        {/* Quality tier slider */}
        <section style={styles.section} aria-labelledby="quality-tier-label">
          <span id="quality-tier-label" style={styles.label}>
            Quality tier
          </span>
          <div style={styles.sliderTrack} role="group" aria-label="Quality tier">
            {QUALITY_TIERS.map((tier) => {
              const active = qualityTier === tier.id;
              return (
                <button
                  key={tier.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  aria-label={`${tier.label}: ${tier.description}`}
                  style={styles.sliderSegment(active)}
                  onClick={() => !disabled && setQualityTier(tier.id)}
                  disabled={disabled}
                >
                  <span>{tier.label}</span>
                  <span style={{ fontSize: 11, opacity: 0.8 }}>{tier.time}</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* Physics toggles */}
        <section style={styles.section} aria-labelledby="physics-label">
          <span id="physics-label" style={styles.label}>
            Physics & realism
          </span>
          {PHYSICS_OPTIONS.map(({ id, label, description }) => (
            <div key={id} style={styles.toggleRow}>
              <div>
                <div style={{ fontWeight: 500, fontSize: 14 }}>{label}</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>{description}</div>
              </div>
              <Toggle
                on={physics[id]}
                onChange={(v) => setPhysics((p) => ({ ...p, [id]: v }))}
                aria-label={`Toggle ${label}`}
              />
            </div>
          ))}
        </section>

        {/* Iteration count */}
        <section style={styles.section} aria-labelledby="iterations-label">
          <span id="iterations-label" style={styles.label}>
            Number of images
          </span>
          <div style={styles.iterationChips} role="group" aria-label="Iteration count">
            {ITERATION_OPTIONS.map((n) => (
              <button
                key={n}
                type="button"
                style={styles.chip(iterations === n)}
                onClick={() => !disabled && setIterations(n)}
                disabled={disabled}
              >
                {n} {n === 1 ? "image" : "images"}
              </button>
            ))}
          </div>
        </section>

        {/* Surprise Me */}
        <section style={styles.section}>
          <span style={styles.label}>Surprise Me</span>
          <div style={styles.surpriseBanner(surpriseMe)}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>Boost surprise & creativity</div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", marginTop: 2 }}>
                More unconventional, bold results
              </div>
            </div>
            <Toggle
              on={surpriseMe}
              onChange={setSurpriseMe}
              aria-label="Surprise Me mode"
            />
          </div>
        </section>

        {/* Prompt */}
        <section style={styles.section}>
          <label htmlFor="prompt-input" style={styles.label}>
            Describe your image
          </label>
          <textarea
            id="prompt-input"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Professional headshot, soft lighting, confident smile..."
            style={styles.textarea}
            disabled={disabled}
            minLength={10}
            maxLength={500}
            aria-describedby="prompt-hint"
          />
          <span id="prompt-hint" style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>
            {prompt.length}/500 {prompt.length < 10 && "· min 10 characters"}
          </span>
        </section>

        {/* Progress + preview */}
        {(isGenerating || previewImage) && (
          <section style={styles.section} aria-live="polite">
            <div style={styles.progressBar}>
              <div style={styles.progressFill(progress)} />
            </div>
            {currentStep && (
              <p style={{ fontSize: 13, color: "rgba(255,255,255,0.6)" }}>{currentStep}</p>
            )}
            {previewImage && (
              <div style={styles.previewBox}>
                <img
                  src={previewImage}
                  alt="Generation preview"
                  style={styles.previewImg}
                />
              </div>
            )}
          </section>
        )}

        {error && <div style={styles.error} role="alert">{error}</div>}

        {/* Submit */}
        <button
          type="submit"
          style={styles.button(true)}
          disabled={disabled || prompt.trim().length < 10 || isGenerating}
          aria-busy={isGenerating}
        >
          {isGenerating ? "Generating…" : "Generate"}
        </button>
      </form>

      {/* Result thumbnails (if provided) */}
      {resultImages.length > 0 && (
        <section style={{ ...styles.section, marginTop: 24 }}>
          <span style={styles.label}>Results</span>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {resultImages.map((src, i) => (
              <img
                key={i}
                src={src}
                alt={`Result ${i + 1}`}
                style={{ width: 100, height: 100, objectFit: "cover", borderRadius: 8 }}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default PhotogeniusUIv2;
