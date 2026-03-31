/**
 * Enhanced Axios API Client with interceptors, authentication, error handling, and retry logic
 */

import axios, {
  AxiosInstance,
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
  AxiosResponse,
} from "axios"
// Auth is handled by Clerk middleware/cookies automatically

// Retry configuration
const MAX_RETRIES = 3
const RETRY_DELAY = 1000 // 1 second

// Base URL configuration
const getBaseURL = (): string => {
  if (typeof window !== "undefined") {
    // Client-side: use relative URLs or env variable
    return process.env.NEXT_PUBLIC_API_URL || "/api"
  }
  // Server-side: use full URL or default
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"
}

/**
 * Create axios instance with default configuration
 */
export const apiClient: AxiosInstance = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
})

/**
 * Request transformer - adds auth token and transforms request data
 */
const requestTransformer = async (config: InternalAxiosRequestConfig) => {
  // Add Clerk JWT token for client-side requests
  if (typeof window !== "undefined") {
    try {
      // Clerk token is automatically added via middleware, but we can also add it here
      // For client-side, Clerk handles auth via cookies/headers automatically
      const token = await getClerkToken()
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    } catch (error) {
      console.warn("Failed to get auth token:", error)
    }
  }

  // Add request ID for tracking
  config.headers["X-Request-ID"] = generateRequestId()

  // Transform request data if needed
  if (config.data && typeof config.data === "object") {
    // Remove undefined values
    config.data = removeUndefinedValues(config.data)
  }

  return config
}

/**
 * Response transformer - handles response data transformation
 */
const responseTransformer = (response: AxiosResponse) => {
  // Extract data from response wrapper if needed
  if (response.data && typeof response.data === "object" && "data" in response.data) {
    return {
      ...response,
      data: response.data.data,
    }
  }
  return response
}

/**
 * Error handler with retry logic
 */
const errorHandler = async (error: AxiosError) => {
  const config = error.config as InternalAxiosRequestConfig & { _retry?: boolean; _retryCount?: number }

  // Don't retry if already retried max times
  if (config._retryCount && config._retryCount >= MAX_RETRIES) {
    return Promise.reject(error)
  }

  // Retry on network errors or 5xx errors
  const shouldRetry =
    !error.response || // Network error
    (error.response.status >= 500 && error.response.status < 600) || // Server error
    error.response.status === 429 // Rate limit

  if (shouldRetry && !config._retry) {
    config._retry = true
    config._retryCount = (config._retryCount || 0) + 1

    // Exponential backoff
    const delay = RETRY_DELAY * Math.pow(2, config._retryCount - 1)
    await sleep(delay)

    return apiClient(config)
  }

  // Handle specific error cases
  if (error.response) {
    switch (error.response.status) {
      case 401:
        // Unauthorized - redirect to login
        if (typeof window !== "undefined") {
          window.location.href = "/login"
        }
        break
      case 403:
        // Forbidden
        console.error("Access forbidden")
        break
      case 404:
        // Not found
        console.error("Resource not found")
        break
      case 429:
        // Rate limited
        console.error("Rate limit exceeded")
        break
      case 500:
      case 502:
      case 503:
      case 504:
        // Server errors
        console.error("Server error:", error.response.status)
        break
    }
  }

  return Promise.reject(error)
}

// Setup interceptors
apiClient.interceptors.request.use(requestTransformer, (error) => Promise.reject(error))
apiClient.interceptors.response.use(responseTransformer, errorHandler)

/**
 * Helper functions
 */

async function getClerkToken(): Promise<string | null> {
  if (typeof window === "undefined") return null

  try {
    // Clerk automatically handles tokens via cookies/headers
    // For explicit token access, we'd need to use Clerk's client-side API
    // This is handled by middleware in Next.js
    return null
  } catch {
    return null
  }
}

function generateRequestId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

function removeUndefinedValues(obj: Record<string, any>): Record<string, any> {
  return Object.fromEntries(
    Object.entries(obj).filter(([_, value]) => value !== undefined)
  )
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * API Error types
 */
export interface ApiError {
  message: string
  code?: string
  errors?: Record<string, string[]>
  statusCode?: number
}

/**
 * Extract error message from axios error
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const apiError = error.response?.data as ApiError
    if (apiError?.message) {
      return apiError.message
    }
    if (error.response?.status) {
      return `Request failed with status ${error.response.status}`
    }
    if (error.message) {
      return error.message
    }
  }
  if (error instanceof Error) {
    return error.message
  }
  return "An unexpected error occurred"
}

/**
 * Extract API error details
 */
export function getApiError(error: unknown): ApiError | null {
  if (axios.isAxiosError(error)) {
    const apiError = error.response?.data as ApiError
    if (apiError) {
      return {
        ...apiError,
        statusCode: error.response?.status,
      }
    }
  }
  return null
}

/**
 * Type-safe API response wrapper
 */
export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
  meta?: {
    page?: number
    limit?: number
    total?: number
  }
}

export default apiClient
