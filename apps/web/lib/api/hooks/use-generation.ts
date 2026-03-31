/**
 * API Hooks for Generation
 * - useGenerate: Trigger generation
 * - useGenerationStatus: Poll generation progress (WebSocket)
 * - useGenerationHistory: Past generations
 * - useDownloadImage: Download result
 */

import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from "@tanstack/react-query"
import { apiClient, getErrorMessage, ApiResponse } from "../axios-client"
import { queryKeys, invalidateQueries } from "../react-query-config"

// Types
export interface Generation {
  id: string
  prompt: string
  mode: "REALISM" | "CREATIVE" | "ROMANTIC"
  preset?: string
  identityId: string
  previewUrl?: string
  outputUrls: string[]
  selectedUrl?: string
  status: "PENDING" | "GENERATING" | "COMPLETED" | "FAILED"
  progress?: number
  currentStep?: string
  scores?: {
    face_match: number
    aesthetic: number
    technical: number
    total: number
  }
  creditsUsed?: number
  createdAt: string
  completedAt?: string
}

export interface CreateGenerationRequest {
  identityId: string
  prompt: string
  mode: Generation["mode"]
  preset?: string
}

export interface GenerationStatusResponse {
  id: string
  status: Generation["status"]
  progress?: number
  currentStep?: string
  outputUrls?: string[]
  error?: string
}

/**
 * Trigger new generation
 */
export function useGenerate(
  options?: UseMutationOptions<Generation, Error, CreateGenerationRequest>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: CreateGenerationRequest) => {
      const response = await apiClient.post<ApiResponse<Generation>>("/generations", data)
      return response.data.data || response.data
    },
    onSuccess: (data) => {
      // Optimistically add to list
      queryClient.setQueryData<Generation[]>(
        queryKeys.generations.lists(),
        (old = []) => [data, ...old]
      )
      // Invalidate to refetch
      invalidateQueries.generations(queryClient)
      invalidateQueries.dashboard(queryClient)
    },
    onError: (error) => {
      console.error("Failed to start generation:", getErrorMessage(error))
    },
    ...options,
  })
}

/**
 * Poll generation status
 */
export function useGenerationStatus(
  generationId: string | null,
  options?: Omit<UseQueryOptions<GenerationStatusResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.generations.status(generationId!),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<GenerationStatusResponse>>(
        `/generations/${generationId}/status`
      )
      return response.data.data || response.data
    },
    enabled: !!generationId,
    refetchInterval: (query) => {
      // Stop polling if generation is complete or failed
      const data = query.state.data
      if (data?.status === "COMPLETED" || data?.status === "FAILED") {
        return false
      }
      // Poll every 1 second while generating
      return 1000
    },
    staleTime: 0, // Always consider stale for real-time updates
    ...options,
  })
}

/**
 * Get generation history (paginated)
 */
export function useGenerationHistory(
  filters?: { page?: number; limit?: number; mode?: Generation["mode"] },
  options?: Omit<UseQueryOptions<{ data: Generation[]; total: number; page: number }>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.generations.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams()
      if (filters?.page) params.append("page", filters.page.toString())
      if (filters?.limit) params.append("limit", filters.limit.toString())
      if (filters?.mode) params.append("mode", filters.mode)

      const response = await apiClient.get<ApiResponse<{ data: Generation[]; total: number; page: number }>>(
        `/generations?${params.toString()}`
      )
      return response.data.data || response.data
    },
    staleTime: 60 * 1000, // 1 minute
    ...options,
  })
}

/**
 * Get single generation by ID
 */
export function useGeneration(
  id: string | null,
  options?: Omit<UseQueryOptions<Generation>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.generations.detail(id!),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Generation>>(`/generations/${id}`)
      return response.data.data || response.data
    },
    enabled: !!id,
    staleTime: 60 * 1000,
    ...options,
  })
}

/**
 * Update generation (e.g., select preferred image)
 */
export function useUpdateGeneration(
  options?: UseMutationOptions<Generation, Error, { id: string; data: Partial<Generation> }>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, data }) => {
      const response = await apiClient.patch<ApiResponse<Generation>>(`/generations/${id}`, data)
      return response.data.data || response.data
    },
    onSuccess: (data, variables) => {
      // Optimistically update in list
      queryClient.setQueryData<Generation[]>(
        queryKeys.generations.lists(),
        (old = []) =>
          old.map((gen) => (gen.id === variables.id ? { ...gen, ...data } : gen))
      )
      queryClient.setQueryData(queryKeys.generations.detail(variables.id), data)
    },
    ...options,
  })
}

/**
 * Delete generation
 */
export function useDeleteGeneration(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (generationId: string) => {
      await apiClient.delete(`/generations/${generationId}`)
    },
    onSuccess: (_, generationId) => {
      // Optimistically remove from list
      queryClient.setQueryData<Generation[]>(
        queryKeys.generations.lists(),
        (old = []) => old.filter((gen) => gen.id !== generationId)
      )
      queryClient.removeQueries({ queryKey: queryKeys.generations.detail(generationId) })
      invalidateQueries.dashboard(queryClient)
    },
    ...options,
  })
}

/**
 * Download generated image
 */
export function useDownloadImage(
  options?: UseMutationOptions<Blob, Error, { imageUrl: string; filename?: string }>
) {
  return useMutation({
    mutationFn: async ({ imageUrl, filename }) => {
      const response = await apiClient.get<Blob>(`/generations/download`, {
        params: { url: imageUrl },
        responseType: "blob",
      })
      
      // Trigger browser download
      const blob = new Blob([response.data])
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename || `generation-${Date.now()}.png`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      return blob
    },
    ...options,
  })
}
