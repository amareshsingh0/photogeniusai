/**
 * API Hooks for Gallery
 * - useGalleryImages: Paginated gallery
 * - useImageDetail: Single image metadata
 * - useDeleteImage: Delete image
 * - useBulkActions: Bulk download/delete
 */

import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions, keepPreviousData } from "@tanstack/react-query"
import { apiClient, getErrorMessage, ApiResponse } from "../axios-client"
import { queryKeys, invalidateQueries } from "../react-query-config"

// Types
export interface GalleryImage {
  id: string
  url: string
  thumbnailUrl?: string
  prompt?: string
  mode?: string
  generationId?: string
  identityId?: string
  identityName?: string
  scores?: {
    face_match: number
    aesthetic: number
    technical: number
    total: number
  }
  metadata?: {
    width: number
    height: number
    size: number
    format: string
  }
  createdAt: string
  tags?: string[]
}

export interface GalleryListResponse {
  data: GalleryImage[]
  total: number
  page: number
  limit: number
  totalPages: number
}

export interface BulkActionRequest {
  imageIds: string[]
  action: "delete" | "download"
}

/**
 * Get paginated gallery images
 */
export function useGalleryImages(
  page: number = 1,
  limit: number = 20,
  filters?: { mode?: string; identityId?: string; search?: string },
  options?: Omit<UseQueryOptions<GalleryListResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.gallery.list(page, limit),
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append("page", page.toString())
      params.append("limit", limit.toString())
      if (filters?.mode) params.append("mode", filters.mode)
      if (filters?.identityId) params.append("identityId", filters.identityId)
      if (filters?.search) params.append("search", filters.search)

      const response = await apiClient.get<ApiResponse<GalleryListResponse>>(
        `/gallery?${params.toString()}`
      )
      return response.data.data || response.data
    },
    staleTime: 60 * 1000, // 1 minute
    placeholderData: keepPreviousData, // Keep previous data while fetching new page
    ...options,
  })
}

/**
 * Get single image detail
 */
export function useImageDetail(
  imageId: string | null,
  options?: Omit<UseQueryOptions<GalleryImage>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.gallery.detail(imageId!),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<GalleryImage>>(`/gallery/${imageId}`)
      return response.data.data || response.data
    },
    enabled: !!imageId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  })
}

/**
 * Delete single image
 */
export function useDeleteImage(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (imageId: string) => {
      await apiClient.delete(`/gallery/${imageId}`)
    },
    onSuccess: (_, imageId) => {
      // Optimistically remove from all gallery lists
      queryClient.setQueriesData<GalleryListResponse>(
        { queryKey: queryKeys.gallery.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            data: old.data.filter((img) => img.id !== imageId),
            total: old.total - 1,
          }
        }
      )
      queryClient.removeQueries({ queryKey: queryKeys.gallery.detail(imageId) })
      invalidateQueries.dashboard(queryClient)
    },
    ...options,
  })
}

/**
 * Bulk actions (delete/download)
 */
export function useBulkActions(
  options?: UseMutationOptions<{ deleted: number; downloaded: number }, Error, BulkActionRequest>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ imageIds, action }) => {
      const response = await apiClient.post<ApiResponse<{ deleted: number; downloaded: number }>>(
        `/gallery/bulk`,
        { imageIds, action }
      )
      return response.data.data || response.data
    },
    onSuccess: (data, variables) => {
      if (variables.action === "delete") {
        // Optimistically remove deleted images from lists
        queryClient.setQueriesData<GalleryListResponse>(
          { queryKey: queryKeys.gallery.lists() },
          (old) => {
            if (!old) return old
            return {
              ...old,
              data: old.data.filter((img) => !variables.imageIds.includes(img.id)),
              total: old.total - data.deleted,
            }
          }
        )
        // Remove individual queries
        variables.imageIds.forEach((id) => {
          queryClient.removeQueries({ queryKey: queryKeys.gallery.detail(id) })
        })
        invalidateQueries.dashboard(queryClient)
      }
    },
    ...options,
  })
}

/**
 * Download single image
 */
export function useDownloadImage(
  options?: UseMutationOptions<void, Error, { imageId: string; filename?: string }>
) {
  return useMutation({
    mutationFn: async ({ imageId, filename }) => {
      const response = await apiClient.get<Blob>(`/gallery/${imageId}/download`, {
        responseType: "blob",
      })
      
      // Trigger browser download
      const blob = new Blob([response.data])
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename || `image-${imageId}.png`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    },
    ...options,
  })
}
