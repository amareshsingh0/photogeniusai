/**
 * Enhanced API Client with Axios, Clerk JWT auth, retry logic,
 * and React Query hooks for all endpoints.
 */

import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from "axios"
import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from "@tanstack/react-query"

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const apiClient: AxiosInstance = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "/api",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
})

// Request interceptor – attach Clerk session JWT
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (typeof window !== "undefined") {
    try {
      const clerkInstance = (window as any)?.__clerk
      if (clerkInstance) {
        const token = await clerkInstance.session?.getToken()
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
      }
    } catch {
      // Clerk not loaded yet – continue without token
    }
  }
  return config
})

// Response interceptor – handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      window.location.href = "/login"
    }
    return Promise.reject(error)
  }
)

// ---------------------------------------------------------------------------
// Retry wrapper (retries on 5xx / timeout, up to 2 retries with backoff)
// ---------------------------------------------------------------------------

async function withRetry<T>(fn: () => Promise<T>, retries = 2, delayMs = 1000): Promise<T> {
  let lastError: unknown
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastError = err
      if (attempt < retries) {
        const isRetryable =
          axios.isAxiosError(err) &&
          (!err.response || err.response.status >= 500 || err.code === "ECONNABORTED")
        if (!isRetryable) throw err
        await new Promise((r) => setTimeout(r, delayMs * (attempt + 1)))
      }
    }
  }
  throw lastError
}

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

export interface ApiError {
  message: string
  code?: string
  errors?: Record<string, string[]>
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiError | undefined
    return data?.message || error.message || "An error occurred"
  }
  if (error instanceof Error) return error.message
  return "An unexpected error occurred"
}

// ---------------------------------------------------------------------------
// React Query Hooks – Generations
// ---------------------------------------------------------------------------

export function useGenerations(options?: Partial<UseQueryOptions<GenerationListItem[]>>) {
  return useQuery({
    queryKey: ["generations"],
    queryFn: () => withRetry(async () => (await apiClient.get<GenerationListItem[]>("/generations")).data),
    ...options,
  })
}

/** Alias for useGenerations */
export function useGenerationHistory(options?: Partial<UseQueryOptions<GenerationListItem[]>>) {
  return useGenerations(options)
}

export function useCreateGeneration(
  options?: UseMutationOptions<GenerationListItem, Error, CreateGenerationRequest>
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: CreateGenerationRequest) =>
      (await apiClient.post<GenerationListItem>("/generations", data)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["generations"] }),
    ...options,
  })
}

export function useUpdateGeneration(
  options?: UseMutationOptions<void, Error, { id: string; data: Partial<GenerationListItem> }>
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }) => { await apiClient.patch(`/generations/${id}`, data) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["generations"] }),
    ...options,
  })
}

export function useDeleteGeneration(options?: UseMutationOptions<void, Error, string>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => { await apiClient.delete(`/generations/${id}`) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["generations"] }),
    ...options,
  })
}

/** Poll generation status by id (refetches every 2s while enabled) */
export function useGenerationStatus(
  generationId: string | null,
  options?: Partial<UseQueryOptions<GenerationListItem>>
) {
  return useQuery({
    queryKey: ["generation", generationId],
    queryFn: () =>
      withRetry(async () => (await apiClient.get<GenerationListItem>(`/generations/${generationId}`)).data),
    enabled: !!generationId,
    refetchInterval: 2000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// React Query Hooks – Identities
// ---------------------------------------------------------------------------

export function useIdentities(options?: Partial<UseQueryOptions<IdentityListItem[]>>) {
  return useQuery({
    queryKey: ["identities"],
    queryFn: () => withRetry(async () => (await apiClient.get<IdentityListItem[]>("/identities")).data),
    ...options,
  })
}

export function useCreateIdentity(
  options?: UseMutationOptions<IdentityListItem, Error, CreateIdentityRequest>
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: CreateIdentityRequest) =>
      (await apiClient.post<IdentityListItem>("/identities", data)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["identities"] }),
    ...options,
  })
}

export function useDeleteIdentity(options?: UseMutationOptions<void, Error, string>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => { await apiClient.delete(`/identities/${id}`) },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["identities"] }),
    ...options,
  })
}

/** Poll training status for an identity (refetches every 2s while enabled) */
export function useIdentityStatus(
  identityId: string | null,
  options?: Partial<UseQueryOptions<IdentityListItem>>
) {
  return useQuery({
    queryKey: ["identity", identityId],
    queryFn: () =>
      withRetry(async () => (await apiClient.get<IdentityListItem>(`/identities/${identityId}`)).data),
    enabled: !!identityId,
    refetchInterval: 2000,
    ...options,
  })
}

export function useStartTraining(options?: UseMutationOptions<TrainingResponse, Error, string>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (identityId: string) =>
      (await apiClient.post<TrainingResponse>(`/identities/${identityId}/train`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["identities"] }),
    ...options,
  })
}

// ---------------------------------------------------------------------------
// React Query Hooks – Gallery
// ---------------------------------------------------------------------------

export function useGalleryImages(
  params?: { page?: number; limit?: number; mode?: string; identityId?: string },
  options?: Partial<UseQueryOptions<GenerationListItem[]>>
) {
  return useQuery({
    queryKey: ["gallery", params],
    queryFn: () =>
      withRetry(async () => (await apiClient.get<GenerationListItem[]>("/generations", { params })).data),
    ...options,
  })
}

export function useImageDetail(
  imageId: string | null,
  options?: Partial<UseQueryOptions<GenerationListItem>>
) {
  return useQuery({
    queryKey: ["image", imageId],
    queryFn: () =>
      withRetry(async () => (await apiClient.get<GenerationListItem>(`/generations/${imageId}`)).data),
    enabled: !!imageId,
    ...options,
  })
}

/** Alias for useDeleteGeneration */
export function useDeleteImage(options?: UseMutationOptions<void, Error, string>) {
  return useDeleteGeneration(options)
}

/** Bulk actions for gallery: delete multiple + download multiple */
export function useBulkActions() {
  const qc = useQueryClient()

  const bulkDelete = useMutation({
    mutationFn: async (ids: string[]) => {
      await Promise.all(ids.map((id) => apiClient.delete(`/generations/${id}`)))
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["generations"] }),
  })

  const bulkDownload = async (images: { url: string; id: string }[]) => {
    for (const img of images) {
      const a = document.createElement("a")
      a.href = img.url
      a.download = `photogenius-${img.id}.png`
      a.target = "_blank"
      a.rel = "noopener"
      a.click()
      await new Promise((r) => setTimeout(r, 150))
    }
  }

  return { bulkDelete, bulkDownload }
}

/** Download a single image by triggering a browser download */
export function useDownloadImage() {
  return {
    download: (url: string, filename?: string) => {
      const a = document.createElement("a")
      a.href = url
      a.download = filename || `photogenius-${Date.now()}.png`
      a.target = "_blank"
      a.rel = "noopener"
      a.click()
    },
  }
}

// ---------------------------------------------------------------------------
// React Query Hooks – Dashboard
// ---------------------------------------------------------------------------

export function useDashboardStats(options?: Partial<UseQueryOptions<DashboardStats>>) {
  return useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () =>
      withRetry(async () => (await apiClient.get<DashboardStats>("/dashboard/stats")).data),
    refetchInterval: 30000,
    ...options,
  })
}

// ---------------------------------------------------------------------------
// File Upload with progress tracking
// ---------------------------------------------------------------------------

export function useFileUpload(
  options?: UseMutationOptions<{ url: string }, Error, File> & {
    onUploadProgress?: (percent: number) => void
  }
) {
  const { onUploadProgress, ...mutationOptions } = options || {}
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append("file", file)
      const response = await apiClient.post<{ url: string }>("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (event.total && onUploadProgress) {
            onUploadProgress(Math.round((event.loaded / event.total) * 100))
          }
        },
      })
      return response.data
    },
    ...mutationOptions,
  })
}

// ---------------------------------------------------------------------------
// Photo Validation
// ---------------------------------------------------------------------------

export function useValidatePhotos(
  options?: UseMutationOptions<ValidationResponse, Error, File[]>
) {
  return useMutation({
    mutationFn: async (photos: File[]) => {
      const formData = new FormData()
      photos.forEach((p) => formData.append("photos", p))
      return (
        await apiClient.post<ValidationResponse>("/identities/validate", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data
    },
    ...options,
  })
}

// Types
export interface GenerationListItem {
  id: string
  prompt: string
  mode: string
  preset?: string
  previewUrl?: string
  outputUrls: string[]
  selectedUrl?: string
  status: string
  createdAt: string
  scores?: {
    face_match: number
    aesthetic: number
    technical: number
    total: number
  }
  identity?: {
    id: string
    name: string
  }
}

export interface CreateGenerationRequest {
  prompt: string
  mode: string
  preset?: string
  previewUrl?: string
  outputUrls: string[]
  selectedUrl?: string
  qualityScore?: number
  faceMatchPct?: number
  aestheticScore?: number
  identityId?: string
}

export interface IdentityListItem {
  id: string
  name?: string
  imageUrls: string[]
  status: string
  createdAt: string
  trainingProgress?: number
  trainingStatus?: string
  trainingError?: string
}

export interface CreateIdentityRequest {
  name?: string
  imageUrls: string[]
}

export interface TrainingResponse {
  success: boolean
  message: string
  identityId?: string
}

export interface DashboardStats {
  credits: number
  imagesGenerated: number
  identitiesCount: number
}

export interface ValidationResponse {
  valid: boolean
  errors: string[]
  photoCount: number
}

// Export axios instance for direct use if needed
export { apiClient }
export default apiClient
