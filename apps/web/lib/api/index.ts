/**
 * API Client - Main Export File
 * Centralized exports for all API functionality
 */

// Axios client
export { apiClient, getErrorMessage, getApiError } from "./axios-client"
export type { ApiResponse, ApiError } from "./axios-client"

// React Query configuration
export { createQueryClient, queryKeys, invalidateQueries } from "./react-query-config"

// Identity hooks
export {
  useIdentities,
  useIdentity,
  useCreateIdentity,
  useIdentityStatus,
  useStartTraining,
  useDeleteIdentity,
  useUpdateIdentity,
  type Identity,
  type CreateIdentityRequest,
  type IdentityStatusResponse,
} from "./hooks/use-identities"

// Generation hooks
export {
  useGenerate,
  useGenerationStatus,
  useGenerationHistory,
  useGeneration,
  useUpdateGeneration,
  useDeleteGeneration,
  useDownloadImage,
  type Generation,
  type CreateGenerationRequest,
  type GenerationStatusResponse,
} from "./hooks/use-generation"

// Gallery hooks
export {
  useGalleryImages,
  useImageDetail,
  useDeleteImage,
  useBulkActions,
  useDownloadImage as useDownloadGalleryImage,
  type GalleryImage,
  type GalleryListResponse,
  type BulkActionRequest,
} from "./hooks/use-gallery"

// File upload service
export {
  uploadFile,
  uploadFiles,
  uploadToS3,
  getPreSignedUrl,
  validatePhotos,
  type UploadProgress,
  type UploadOptions,
  type UploadResponse,
  type PreSignedUrlResponse,
} from "./services/file-upload"

// WebSocket service
export {
  createSocket,
  useSocket,
  useTrainingProgress,
  useGenerationProgress,
  useMultipleTrainingProgress,
  type SocketConfig,
  type TrainingProgress,
  type GenerationProgress,
} from "./services/websocket"
