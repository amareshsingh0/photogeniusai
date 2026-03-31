/**
 * API Hooks for Identity Management
 * - useIdentities: List all identities
 * - useCreateIdentity: Upload photos + create identity
 * - useIdentityStatus: Poll training status
 * - useDeleteIdentity: Delete identity
 */

import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from "@tanstack/react-query"
import { apiClient, getErrorMessage, ApiResponse } from "../axios-client"
import { queryKeys, invalidateQueries } from "../react-query-config"

// Types
export interface Identity {
  id: string
  name?: string
  imageUrls: string[]
  status: "PENDING" | "TRAINING" | "READY" | "FAILED"
  createdAt: string
  updatedAt?: string
  trainingProgress?: number
  trainingMessage?: string
}

export interface CreateIdentityRequest {
  name?: string
  imageUrls: string[]
}

export interface IdentityStatusResponse {
  id: string
  status: Identity["status"]
  progress?: number
  message?: string
}

/**
 * List all identities
 */
export function useIdentities(
  options?: Omit<UseQueryOptions<Identity[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.identities.lists(),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Identity[]>>("/identities")
      return response.data.data || response.data
    },
    staleTime: 30 * 1000, // 30 seconds
    ...options,
  })
}

/**
 * Get single identity by ID
 */
export function useIdentity(
  id: string | null,
  options?: Omit<UseQueryOptions<Identity>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.identities.detail(id!),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<Identity>>(`/identities/${id}`)
      return response.data.data || response.data
    },
    enabled: !!id,
    staleTime: 30 * 1000,
    ...options,
  })
}

/**
 * Create identity with photo uploads
 */
export function useCreateIdentity(
  options?: UseMutationOptions<Identity, Error, CreateIdentityRequest>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: CreateIdentityRequest) => {
      const response = await apiClient.post<ApiResponse<Identity>>("/identities", data)
      return response.data.data || response.data
    },
    onSuccess: () => {
      invalidateQueries.identities(queryClient)
      invalidateQueries.dashboard(queryClient)
    },
    onError: (error) => {
      console.error("Failed to create identity:", getErrorMessage(error))
    },
    ...options,
  })
}

/**
 * Poll identity training status
 */
export function useIdentityStatus(
  identityId: string | null,
  options?: Omit<UseQueryOptions<IdentityStatusResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: queryKeys.identities.status(identityId!),
    queryFn: async () => {
      const response = await apiClient.get<ApiResponse<IdentityStatusResponse>>(
        `/identities/${identityId}/status`
      )
      return response.data.data || response.data
    },
    enabled: !!identityId,
    refetchInterval: (query) => {
      // Stop polling if training is complete or failed
      const data = query.state.data
      if (data?.status === "READY" || data?.status === "FAILED") {
        return false
      }
      // Poll every 2 seconds while training
      return 2000
    },
    staleTime: 0, // Always consider stale for real-time updates
    ...options,
  })
}

/**
 * Start training for an identity
 */
export function useStartTraining(
  options?: UseMutationOptions<{ success: boolean; message: string }, Error, string>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (identityId: string) => {
      const response = await apiClient.post<ApiResponse<{ success: boolean; message: string }>>(
        `/identities/${identityId}/train`
      )
      return response.data.data || response.data
    },
    onSuccess: (_, identityId) => {
      // Invalidate identity status to start polling
      queryClient.invalidateQueries({ queryKey: queryKeys.identities.status(identityId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.identities.detail(identityId) })
      invalidateQueries.identities(queryClient)
    },
    ...options,
  })
}

/**
 * Delete identity
 */
export function useDeleteIdentity(
  options?: UseMutationOptions<void, Error, string>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (identityId: string) => {
      await apiClient.delete(`/identities/${identityId}`)
    },
    onSuccess: () => {
      invalidateQueries.identities(queryClient)
      invalidateQueries.dashboard(queryClient)
    },
    ...options,
  })
}

/**
 * Update identity (e.g., rename)
 */
export function useUpdateIdentity(
  options?: UseMutationOptions<Identity, Error, { id: string; data: Partial<Identity> }>
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, data }) => {
      const response = await apiClient.patch<ApiResponse<Identity>>(`/identities/${id}`, data)
      return response.data.data || response.data
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.identities.detail(variables.id) })
      invalidateQueries.identities(queryClient)
    },
    ...options,
  })
}
