"use client"

import { useState, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Upload, X, Image as ImageIcon, CheckCircle } from "lucide-react"
import Image from "next/image"
import { cn } from "@/lib/utils"

interface ImageUploadProps {
  onUpload: (files: File[]) => Promise<void>
  maxFiles?: number
  maxSizeMB?: number
  accept?: string
  multiple?: boolean
  className?: string
  disabled?: boolean
}

export function ImageUpload({
  onUpload,
  maxFiles = 10,
  maxSizeMB = 10,
  accept = "image/*",
  multiple = true,
  className,
  disabled = false,
}: ImageUploadProps) {
  const [files, setFiles] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [errors, setErrors] = useState<string[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): string | null => {
    if (file.size > maxSizeMB * 1024 * 1024) {
      return `File size exceeds ${maxSizeMB}MB limit`
    }
    if (!file.type.startsWith("image/")) {
      return "File must be an image"
    }
    return null
  }

  const handleFileSelect = useCallback(
    (selectedFiles: FileList | null) => {
      if (!selectedFiles) return

      const newFiles: File[] = []
      const newPreviews: string[] = []
      const newErrors: string[] = []

      Array.from(selectedFiles).forEach((file) => {
        const error = validateFile(file)
        if (error) {
          newErrors.push(`${file.name}: ${error}`)
          return
        }

        if (files.length + newFiles.length >= maxFiles) {
          newErrors.push(`Maximum ${maxFiles} files allowed`)
          return
        }

        newFiles.push(file)
        const preview = URL.createObjectURL(file)
        newPreviews.push(preview)
      })

      setErrors(newErrors)
      setFiles((prev) => [...prev, ...newFiles])
      setPreviews((prev) => [...prev, ...newPreviews])
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [files.length, maxFiles, maxSizeMB]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      if (disabled) return
      handleFileSelect(e.dataTransfer.files)
    },
    [disabled, handleFileSelect]
  )

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const removeFile = (index: number) => {
    setFiles((prev) => {
      const newFiles = [...prev]
      newFiles.splice(index, 1)
      return newFiles
    })
    setPreviews((prev) => {
      const newPreviews = [...prev]
      URL.revokeObjectURL(newPreviews[index])
      newPreviews.splice(index, 1)
      return newPreviews
    })
  }

  const handleUpload = async () => {
    if (files.length === 0) return

    setUploading(true)
    setProgress(0)
    setErrors([])

    try {
      // Simulate progress
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) {
            clearInterval(interval)
            return 90
          }
          return prev + 10
        })
      }, 200)

      await onUpload(files)
      setProgress(100)
      setTimeout(() => {
        setFiles([])
        previews.forEach((url) => URL.revokeObjectURL(url))
        setPreviews([])
        setProgress(0)
      }, 1000)
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Upload failed"])
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Drop Zone */}
      <Card
        className={cn(
          "glass-card border-2 border-dashed transition-colors",
          disabled
            ? "opacity-50 cursor-not-allowed"
            : "cursor-pointer hover:border-primary/50"
        )}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => !disabled && fileInputRef.current?.click()}
      >
        <CardContent className="py-12 text-center">
          <Upload className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">
            Drop images here or click to upload
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            {multiple ? `Up to ${maxFiles} files` : "Single file"} • Max {maxSizeMB}MB each
          </p>
          <Button variant="outline" disabled={disabled}>
            <ImageIcon className="mr-2 h-4 w-4" />
            Select Images
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept={accept}
            multiple={multiple}
            onChange={(e) => handleFileSelect(e.target.files)}
            className="hidden"
            disabled={disabled}
          />
        </CardContent>
      </Card>

      {/* Errors */}
      {errors.length > 0 && (
        <div className="space-y-1">
          {errors.map((error, index) => (
            <div
              key={index}
              className="text-sm text-destructive bg-destructive/10 p-2 rounded"
            >
              {error}
            </div>
          ))}
        </div>
      )}

      {/* Preview Grid */}
      {previews.length > 0 && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {previews.map((preview, index) => (
              <div
                key={index}
                className="relative aspect-square rounded-lg overflow-hidden border border-border/50 group"
              >
                <Image
                  src={preview}
                  alt={`Preview ${index + 1}`}
                  fill
                  className="object-cover"
                  unoptimized
                />
                {!uploading && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFile(index)
                    }}
                    className="absolute top-2 right-2 h-6 w-6 rounded-full bg-destructive flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="h-4 w-4 text-destructive-foreground" />
                  </button>
                )}
                {uploading && progress === 100 && (
                  <div className="absolute inset-0 bg-background/80 flex items-center justify-center">
                    <CheckCircle className="h-8 w-8 text-primary" />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Upload Progress */}
          {uploading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Uploading...</span>
                <span className="text-foreground font-medium">{progress}%</span>
              </div>
              <Progress value={progress} />
            </div>
          )}

          {/* Upload Button */}
          {!uploading && (
            <Button onClick={handleUpload} className="w-full" disabled={disabled}>
              Upload {files.length} {files.length === 1 ? "Image" : "Images"}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
