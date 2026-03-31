/**
 * Generation types for PhotoGenius AI
 */

export type GenerationMode =
  | "realism"
  | "creative"
  | "romantic"
  | "cinematic"
  | "fashion"
  | "cool_edgy"
  | "artistic"
  | "max_surprise";
export type GenerationStatus = "pending" | "preview" | "complete" | "failed" | "blocked";

export interface GenerationRequest {
  prompt: string;
  mode: GenerationMode;
  identityId?: string;
  preset?: string;
  numOutputs?: number;
}

export interface GenerationResult {
  id: string;
  previewUrl?: string;
  imageUrls: string[];
  selectedUrl?: string;
  qualityReport?: QualityReport;
  status: GenerationStatus;
  blockedReason?: string;
}

export interface QualityReport {
  overallScore: number;        // 0-100
  faceMatchPercent?: number;   // 0-100, null if no identity
  aestheticScore: number;      // 0-10 (LAION scale)
  technicalQuality: number;    // 0-100
  promptAdherence: number;     // 0-100 (CLIP similarity)
}

export interface PreviewResponse {
  previewImage: string;
  message: string;
  estimatedTime: string;
  qualityLevel: string;
}

export interface FullQualityResponse {
  finalImage: string;
  message: string;
  qualityReport?: QualityReport;
}
