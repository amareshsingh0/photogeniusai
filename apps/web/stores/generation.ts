import { create } from "zustand";
import type { GenerationMode } from "@photogenius/types";

export type Phase =
  | "idle"
  | "generating_preview"
  | "preview_ready"
  | "polishing"
  | "complete";

export interface PreviewData {
  preview_image: string;
  message: string;
  estimated_time: string;
  quality_level: string;
}

export interface GenerationState {
  mode: GenerationMode;
  prompt: string;
  agreed: boolean;
  phase: Phase;
  previewData: PreviewData | null;
  finalImage: string | null;
  results: string[];
  polishProgress: number;
  error: string | null;
  isMock: boolean;
  setMode: (m: GenerationMode) => void;
  setPrompt: (p: string) => void;
  setAgreed: (a: boolean) => void;
  setPhase: (p: Phase) => void;
  setPreviewData: (d: PreviewData | null) => void;
  setFinalImage: (url: string | null) => void;
  setResults: (urls: string[]) => void;
  setPolishProgress: (n: number) => void;
  setError: (e: string | null) => void;
  setIsMock: (v: boolean) => void;
  reset: () => void;
}

const initial = {
  mode: "realism" as GenerationMode,
  prompt: "",
  agreed: false,
  phase: "idle" as Phase,
  previewData: null as PreviewData | null,
  finalImage: null as string | null,
  results: [] as string[],
  polishProgress: 0,
  error: null as string | null,
  isMock: false,
};

export const useGenerationStore = create<GenerationState>((set) => ({
  ...initial,
  setMode: (mode) => set({ mode }),
  setPrompt: (prompt) => set({ prompt }),
  setAgreed: (agreed) => set({ agreed }),
  setPhase: (phase) => set({ phase }),
  setPreviewData: (previewData) => set({ previewData }),
  setFinalImage: (finalImage) => set({ finalImage }),
  setResults: (results) => set({ results }),
  setPolishProgress: (polishProgress) => set({ polishProgress }),
  setError: (error) => set({ error }),
  setIsMock: (isMock) => set({ isMock }),
  reset: () =>
    set({
      phase: "idle",
      previewData: null,
      finalImage: null,
      results: [],
      polishProgress: 0,
      error: null,
      isMock: false,
    }),
}));
