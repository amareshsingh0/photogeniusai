"use client"

import { useState, useCallback } from "react"
import { useDropzone } from "react-dropzone"
import Image from "next/image"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Upload, X, AlertCircle, CheckCircle } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

interface UploadFormProps {
  onComplete: (photos: File[], name: string) => void
}

export function IdentityUploadForm({ onComplete }: UploadFormProps) {
  const [photos, setPhotos] = useState<File[]>([])
  const [identityName, setIdentityName] = useState("")
  const [errors, setErrors] = useState<string[]>([])
  const [validating, setValidating] = useState(false)

  const MIN_PHOTOS = 8
  const MAX_PHOTOS = 20
  const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setErrors([])
    
    // Filter valid files
    const validFiles = acceptedFiles.filter(file => {
      if (file.size > MAX_FILE_SIZE) {
        setErrors(prev => [...prev, `${file.name} is too large (max 10MB)`])
        return false
      }
      return true
    })

    // Add to photos
    setPhotos(prev => {
      const newPhotos = [...prev, ...validFiles]
      if (newPhotos.length > MAX_PHOTOS) {
        setErrors(prev => [...prev, `Maximum ${MAX_PHOTOS} photos allowed`])
        return newPhotos.slice(0, MAX_PHOTOS)
      }
      return newPhotos
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/webp': ['.webp'],
    },
    multiple: true,
  })

  const removePhoto = (index: number) => {
    setPhotos(prev => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    setErrors([])

    // Validation
    if (!identityName.trim()) {
      setErrors(["Please enter an identity name"])
      return
    }

    if (photos.length < MIN_PHOTOS) {
      setErrors([`Please upload at least ${MIN_PHOTOS} photos`])
      return
    }

    if (photos.length > MAX_PHOTOS) {
      setErrors([`Please upload maximum ${MAX_PHOTOS} photos`])
      return
    }

    // Validate photos via API
    setValidating(true)
    
    try {
      const { validatePhotos } = await import("@/lib/api")
      const result = await validatePhotos(photos)
      
      if (!result.valid) {
        setErrors(result.errors)
        setValidating(false)
        return
      }
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Validation failed"])
      setValidating(false)
      return
    }
    
    setValidating(false)

    // If validation passes
    onComplete(photos, identityName)
  }

  const canSubmit = photos.length >= MIN_PHOTOS && photos.length <= MAX_PHOTOS && identityName.trim()

  return (
    <div className="space-y-6">
      {/* Identity Name */}
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Identity Name</CardTitle>
        </CardHeader>
        <CardContent>
          <Label htmlFor="name">Name this identity</Label>
          <Input
            id="name"
            placeholder="e.g., Professional, Casual, Creative"
            value={identityName}
            onChange={(e) => setIdentityName(e.target.value)}
            className="mt-2 rounded-xl"
          />
          <p className="mt-2 text-sm text-muted-foreground">
            Choose a name to help you identify this collection
          </p>
        </CardContent>
      </Card>

      {/* Photo Upload */}
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle>Upload Photos ({photos.length}/{MAX_PHOTOS})</CardTitle>
          <p className="text-sm text-muted-foreground">
            Upload {MIN_PHOTOS}-{MAX_PHOTOS} photos of the same person
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Dropzone */}
          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-300",
              isDragActive
                ? "border-primary bg-primary/10 scale-[1.02]"
                : "border-border/50 hover:border-primary/50 hover:bg-muted/30"
            )}
          >
            <input {...getInputProps()} />
            <Upload className={cn(
              "mx-auto h-12 w-12 mb-4 transition-colors",
              isDragActive ? "text-primary" : "text-muted-foreground"
            )} />
            {isDragActive ? (
              <p className="text-primary font-medium">Drop photos here...</p>
            ) : (
              <>
                <p className="text-foreground font-medium mb-2">
                  Drag & drop photos here, or click to browse
                </p>
                <p className="text-sm text-muted-foreground">
                  JPG, PNG, or WebP, max 10MB each
                </p>
              </>
            )}
          </div>

          {/* Photo Grid */}
          {photos.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-4">
              {photos.map((photo, index) => (
                <div key={index} className="relative group">
                  <div className="aspect-square relative rounded-xl overflow-hidden border border-border/50 bg-muted">
                    <Image
                      src={URL.createObjectURL(photo)}
                      alt={`Photo ${index + 1}`}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      removePhoto(index)
                    }}
                    className="absolute -top-2 -right-2 bg-destructive text-destructive-foreground rounded-full p-1.5 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg z-10"
                  >
                    <X className="h-4 w-4" />
                  </button>
                  <div className="absolute bottom-0 left-0 right-0 bg-background/80 p-1 text-center">
                    <span className="text-xs text-muted-foreground">
                      {index + 1}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Requirements */}
          <div className="space-y-2 p-4 rounded-xl bg-muted/30">
            <RequirementItem
              met={photos.length >= MIN_PHOTOS}
              text={`At least ${MIN_PHOTOS} photos`}
            />
            <RequirementItem
              met={photos.length <= MAX_PHOTOS}
              text={`Maximum ${MAX_PHOTOS} photos`}
            />
            <RequirementItem
              met={identityName.trim().length > 0}
              text="Identity name provided"
            />
          </div>

          {/* Errors */}
          {errors.length > 0 && (
            <Alert variant="destructive" className="rounded-xl">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <ul className="list-disc list-inside space-y-1">
                  {errors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Validation Progress */}
          {validating && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">
                Validating photos...
              </p>
              <Progress value={66} className="h-2" />
            </div>
          )}

          {/* Submit Button */}
          <Button
            onClick={handleSubmit}
            disabled={!canSubmit || validating}
            className="w-full rounded-xl"
            size="lg"
          >
            {validating ? "Validating..." : "Continue to Consent"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

function RequirementItem({ met, text }: { met: boolean; text: string }) {
  return (
    <div className="flex items-center space-x-2 text-sm">
      {met ? (
        <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
      ) : (
        <div className="h-4 w-4 rounded-full border-2 border-muted-foreground/30 flex-shrink-0" />
      )}
      <span className={met ? "text-green-700 dark:text-green-400" : "text-muted-foreground"}>
        {text}
      </span>
    </div>
  )
}
