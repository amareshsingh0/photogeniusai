/**
 * React Query Configuration with cache management, optimistic updates, and invalidation strategies
 */

import { QueryClient, DefaultOptions } from "@tanstack/react-query"

/**
 * Default query options
 */
const queryConfig: DefaultOptions = {
  queries: {
    staleTime: 60 * 1000, // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes (formerly cacheTime)
    retry: (failureCount, error: any) => {
      // Don't retry on 4xx errors
      if (error?.response?.status >= 400 && error?.response?.status < 500) {
        return false
      }
      // Retry up to 2 times for other errors
      return failureCount < 2
    },
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
    refetchOnMount: true,
  },
  mutations: {
    retry: false,
  },
}

/**
 * Create query client with default configuration
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: queryConfig,
  })
}

/**
 * Query keys factory for type-safe query keys
 */
export const queryKeys = {
  // Identities
  identities: {
    all: ["identities"] as const,
    lists: () => [...queryKeys.identities.all, "list"] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.identities.lists(), filters] as const,
    details: () => [...queryKeys.identities.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.identities.details(), id] as const,
    status: (id: string) => [...queryKeys.identities.detail(id), "status"] as const,
  },
  // Generations
  generations: {
    all: ["generations"] as const,
    lists: () => [...queryKeys.generations.all, "list"] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.generations.lists(), filters] as const,
    details: () => [...queryKeys.generations.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.generations.details(), id] as const,
    status: (id: string) => [...queryKeys.generations.detail(id), "status"] as const,
    history: () => [...queryKeys.generations.all, "history"] as const,
  },
  // Gallery
  gallery: {
    all: ["gallery"] as const,
    lists: () => [...queryKeys.gallery.all, "list"] as const,
    list: (page?: number, limit?: number) =>
      [...queryKeys.gallery.lists(), { page, limit }] as const,
    details: () => [...queryKeys.gallery.all, "detail"] as const,
    detail: (id: string) => [...queryKeys.gallery.details(), id] as const,
  },
  // Dashboard
  dashboard: {
    all: ["dashboard"] as const,
    stats: () => [...queryKeys.dashboard.all, "stats"] as const,
  },
  // User
  user: {
    all: ["user"] as const,
    session: () => [...queryKeys.user.all, "session"] as const,
    profile: () => [...queryKeys.user.all, "profile"] as const,
  },
} as const

/**
 * Invalidation helpers
 */
export const invalidateQueries = {
  identities: (queryClient: ReturnType<typeof createQueryClient>) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.identities.all })
  },
  generations: (queryClient: ReturnType<typeof createQueryClient>) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.generations.all })
  },
  gallery: (queryClient: ReturnType<typeof createQueryClient>) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.gallery.all })
  },
  dashboard: (queryClient: ReturnType<typeof createQueryClient>) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all })
  },
}
