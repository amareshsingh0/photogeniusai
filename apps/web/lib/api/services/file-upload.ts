/**
 * File Upload Service
 * - Multipart form data handling
 * - Progress tracking
 * - S3 pre-signed URLs
 * - Image compression
 * - Validation
 */

import { apiClient, ApiResponse } from "../axios-client"
import axios, { AxiosProgressEvent } from "axios"

// Types
export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}

export interface UploadOptions {
  onProgress?: (progress: UploadProgress) => void
  compress?: boolean
  maxSize?: number // in bytes
  allowedTypes?: string[]
}

export interface UploadResponse {
  url: string
  key: string
  size: number
  contentType: string
}

export interface PreSignedUrlResponse {
  url: string
  key: string
  fields: Record<string, string>
}

/**
 * Compress image before upload
 */
async function compressImage(file: File, quality: number = 0.8): Promise<File> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement("canvas")
        const MAX_WIDTH = 2048
        const MAX_HEIGHT = 2048

        let width = img.width
        let height = img.height

        // Calculate new dimensions
        if (width > height) {
          if (width > MAX_WIDTH) {
            height = (height * MAX_WIDTH) / width
            width = MAX_WIDTH
          }
        } else {
          if (height > MAX_HEIGHT) {
            width = (width * MAX_HEIGHT) / height
            height = MAX_HEIGHT
          }
        }

        canvas.width = width
        canvas.height = height

        const ctx = canvas.getContext("2d")
        if (!ctx) {
          reject(new Error("Failed to get canvas context"))
          return
        }

        ctx.drawImage(img, 0, 0, width, height)

        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error("Failed to compress image"))
              return
            }
            const compressedFile = new File([blob], file.name, {
              type: file.type,
              lastModified: Date.now(),
            })
            resolve(compressedFile)
          },
          file.type,
          quality
        )
      }
      img.onerror = reject
      img.src = e.target?.result as string
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * Validate file before upload
 */
function validateFile(file: File, options: UploadOptions): { valid: boolean; error?: string } {
  // Check file size
  if (options.maxSize && file.size > options.maxSize) {
    return {
      valid: false,
      error: `File size exceeds maximum allowed size of ${options.maxSize / 1024 / 1024}MB`,
    }
  }

  // Check file type
  if (options.allowedTypes && !options.allowedTypes.includes(file.type)) {
    return {
      valid: false,
      error: `File type ${file.type} is not allowed. Allowed types: ${options.allowedTypes.join(", ")}`,
    }
  }

  // Check if it's an image
  if (!file.type.startsWith("image/")) {
    return {
      valid: false,
      error: "File must be an image",
    }
  }

  return { valid: true }
}

/**
 * Get pre-signed URL for direct S3 upload
 */
export async function getPreSignedUrl(
  filename: string,
  contentType: string
): Promise<PreSignedUrlResponse> {
  const response = await apiClient.post<ApiResponse<PreSignedUrlResponse>>("/upload/presigned", {
    filename,
    contentType,
  })
  return response.data.data || response.data
}

/**
 * Upload file directly to S3 using pre-signed URL
 */
export async function uploadToS3(
  file: File,
  preSignedData: PreSignedUrlResponse,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadResponse> {
  const formData = new FormData()
  
  // Add S3 fields
  Object.entries(preSignedData.fields).forEach(([key, value]) => {
    formData.append(key, value)
  })
  
  // Add file last
  formData.append("file", file)

  const response = await axios.post(preSignedData.url, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    onUploadProgress: (progressEvent: AxiosProgressEvent) => {
      if (onProgress && progressEvent.total) {
        onProgress({
          loaded: progressEvent.loaded,
          total: progressEvent.total,
          percentage: Math.round((progressEvent.loaded / progressEvent.total) * 100),
        })
      }
    },
  })

  return {
    url: `${preSignedData.url}/${preSignedData.key}`,
    key: preSignedData.key,
    size: file.size,
    contentType: file.type,
  }
}

/**
 * Upload file via API endpoint (with progress tracking)
 */
export async function uploadFile(
  file: File,
  options: UploadOptions = {}
): Promise<UploadResponse> {
  // Validate file
  const validation = validateFile(file, options)
  if (!validation.valid) {
    throw new Error(validation.error)
  }

  // Compress if requested
  let fileToUpload = file
  if (options.compress && file.type.startsWith("image/")) {
    try {
      fileToUpload = await compressImage(file)
    } catch (error) {
      console.warn("Failed to compress image, uploading original:", error)
    }
  }

  // Create form data
  const formData = new FormData()
  formData.append("file", fileToUpload)
  if (options.compress) {
    formData.append("compress", "true")
  }

  // Upload with progress tracking
  const response = await apiClient.post<ApiResponse<UploadResponse>>("/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
    onUploadProgress: (progressEvent: AxiosProgressEvent) => {
      if (options.onProgress && progressEvent.total) {
        options.onProgress({
          loaded: progressEvent.loaded,
          total: progressEvent.total,
          percentage: Math.round((progressEvent.loaded / progressEvent.total) * 100),
        })
      }
    },
  })

  return response.data.data || response.data
}

/**
 * Upload multiple files
 */
export async function uploadFiles(
  files: File[],
  options: UploadOptions = {}
): Promise<UploadResponse[]> {
  const uploadPromises = files.map((file) => uploadFile(file, options))
  return Promise.all(uploadPromises)
}

/**
 * Validate photos before upload (server-side validation)
 */
export async function validatePhotos(photos: File[]): Promise<{
  valid: boolean
  errors: string[]
  photoCount: number
}> {
  const formData = new FormData()
  photos.forEach((photo) => {
    formData.append("photos", photo)
  })

  const response = await apiClient.post<ApiResponse<{
    valid: boolean
    errors: string[]
    photoCount: number
  }>>("/identities/validate", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  })

  return response.data.data || response.data
}
