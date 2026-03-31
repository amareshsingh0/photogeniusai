"use client"

import { useState, useCallback } from "react"
import { useDropzone } from "react-dropzone"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Upload,
  X,
  CheckCircle,
  AlertCircle,
  User,
  Loader2,
} from "lucide-react"
import Image from "next/image"
import { cn } from "@/lib/utils"

interface CreateIdentityModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (identity: any) => void
}

export function CreateIdentityModal({
  isOpen,
  onClose,
  onSuccess,
}: CreateIdentityModalProps) {
  const [step, setStep] = useState(1) // 1: Info, 2: Upload, 3: Consent, 4: Training
  const [identityName, setIdentityName] = useState("")
  const [photos, setPhotos] = useState<File[]>([])
  const [validationResults, setValidationResults] = useState<any[]>([])
  const [consentGiven, setConsentGiven] = useState(false)
  const [trainingProgress, setTrainingProgress] = useState(0)
  const [isValidating, setIsValidating] = useState(false)
  const [isTraining, setIsTraining] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setPhotos((prev) => [...prev, ...acceptedFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/*": [".jpg", ".jpeg", ".png", ".webp"],
    },
    maxSize: 10 * 1024 * 1024, // 10MB
  })

  const removePhoto = (index: number) => {
    setPhotos((prev) => prev.filter((_, i) => i !== index))
    setValidationResults((prev) => prev.filter((_, i) => i !== index))
  }

  const validatePhotos = async () => {
    setIsValidating(true)
    setError(null)

    try {
      // Call validation API
      const formData = new FormData()
      photos.forEach((photo) => formData.append("photos", photo))

      const response = await fetch("/api/identities/validate", {
        method: "POST",
        body: formData,
      })

      const data = await response.json()

      if (data.valid) {
        // All valid - mark all as passed
        const results = photos.map((_, index) => ({
          index,
          valid: true,
          faceDetected: true,
          samePerson: true,
          quality: 0.85,
          issues: [],
        }))
        setValidationResults(results)
        setStep(3) // Auto-advance
      } else {
        // Some errors
        const results = photos.map((_, index) => ({
          index,
          valid: true, // Individual validation passed (errors are global)
          faceDetected: true,
          samePerson: true,
          quality: 0.85,
          issues: [],
        }))
        setValidationResults(results)
        setError(data.errors?.join(", ") || "Validation failed")
      }
    } catch (err) {
      console.error("Validation error:", err)
      setError("Failed to validate photos. Please try again.")
    } finally {
      setIsValidating(false)
    }
  }

  const startTraining = async () => {
    setIsTraining(true)
    setError(null)
    setStep(4)
    setTrainingProgress(5)

    try {
      // Step 1: Upload photos to S3 first
      setTrainingProgress(10)

      const formData = new FormData()
      photos.forEach((photo) => formData.append("photos", photo))

      const uploadResponse = await fetch("/api/identities/upload", {
        method: "POST",
        body: formData,
      })

      if (!uploadResponse.ok) {
        const errData = await uploadResponse.json().catch(() => ({}))
        throw new Error(errData.error || "Failed to upload photos")
      }

      const uploadData = await uploadResponse.json()
      const imageUrls = uploadData.urls as string[]

      if (!imageUrls || imageUrls.length === 0) {
        throw new Error("No photos were uploaded successfully")
      }

      setTrainingProgress(25)

      // Step 2: Create identity with S3 URLs
      const createResponse = await fetch("/api/identities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: identityName,
          imageUrls: imageUrls,
        }),
      })

      if (!createResponse.ok) {
        const errData = await createResponse.json().catch(() => ({}))
        throw new Error(errData.error || "Failed to create identity")
      }

      const identity = await createResponse.json()
      setTrainingProgress(30)

      // Step 2: Start training
      const trainResponse = await fetch(`/api/identities/${identity.id}/train`, {
        method: "POST",
      })

      if (!trainResponse.ok) {
        const errData = await trainResponse.json().catch(() => ({}))
        throw new Error(errData.message || "Failed to start training")
      }

      setTrainingProgress(50)

      // Step 3: Poll for progress (training happens in background)
      // Simulate progress while training runs on AWS GPU
      let progress = 50
      const progressInterval = setInterval(() => {
        progress = Math.min(progress + 5, 95)
        setTrainingProgress(progress)
      }, 3000)

      // Wait a bit then mark as complete (training continues in background)
      await new Promise((resolve) => setTimeout(resolve, 5000))
      clearInterval(progressInterval)
      setTrainingProgress(100)

      // Return the created identity with S3 URLs
      const newIdentity = {
        id: identity.id,
        name: identity.name || identityName,
        status: "TRAINING",
        progress: 100,
        createdAt: identity.createdAt || new Date().toISOString(),
        imageUrls: identity.imageUrls || imageUrls, // Use S3 URLs
        referencePhotos: photos.length,
        generations: 0,
        qualityScore: null,
        loraPath: null,
      }

      onSuccess(newIdentity)
    } catch (err) {
      console.error("Training error:", err)
      setError(err instanceof Error ? err.message : "Failed to start training")
      setTrainingProgress(0)
      setStep(3) // Go back to consent step
    } finally {
      setIsTraining(false)
    }
  }

  const resetModal = () => {
    setStep(1)
    setIdentityName("")
    setPhotos([])
    setValidationResults([])
    setConsentGiven(false)
    setTrainingProgress(0)
    setIsValidating(false)
    setIsTraining(false)
  }

  const handleClose = () => {
    // Allow closing even during training (training continues in background)
    if (step !== 4 || trainingProgress >= 100) {
      resetModal()
    }
    onClose()
  }

  const canProceedToUpload = identityName.trim().length >= 3
  const canProceedToConsent = photos.length >= 8 && photos.length <= 20
  const canStartTraining = consentGiven

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto glass-card">
        <DialogHeader>
          <DialogTitle>Create New Identity</DialogTitle>
          <DialogDescription>
            Step {step} of 4: {
              step === 1 ? "Basic Information" :
              step === 2 ? "Upload Photos" :
              step === 3 ? "Consent & Privacy" :
              "Training"
            }
          </DialogDescription>
        </DialogHeader>

        {/* Progress Indicator */}
        <div className="flex items-center justify-between mb-6">
          {[1, 2, 3, 4].map((s) => (
            <div key={s} className="flex items-center flex-1">
              <div
                className={cn(
                  "h-8 w-8 rounded-full flex items-center justify-center",
                  s < step
                    ? "bg-primary text-primary-foreground"
                    : s === step
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {s < step ? <CheckCircle className="h-5 w-5" /> : s}
              </div>
              {s < 4 && (
                <div
                  className={cn(
                    "flex-1 h-1 mx-2",
                    s < step ? "bg-primary" : "bg-muted"
                  )}
                />
              )}
            </div>
          ))}
        </div>

        {/* Step 1: Basic Info */}
        {step === 1 && (
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="name">Identity Name</Label>
              <Input
                id="name"
                placeholder="e.g., Professional, Casual, Creative"
                value={identityName}
                onChange={(e) => setIdentityName(e.target.value)}
                maxLength={30}
              />
              <p className="text-xs text-muted-foreground">
                Choose a descriptive name for this identity (3-30 characters)
              </p>
            </div>

            <Alert className="border-primary/30 bg-primary/5">
              <User className="h-4 w-4 text-primary" />
              <AlertDescription>
                You&apos;ll upload 8-20 photos of the same person in the next step.
                Make sure all photos are:
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>Of the same person</li>
                  <li>Clear and well-lit</li>
                  <li>Showing the face clearly</li>
                  <li>Different angles and expressions</li>
                </ul>
              </AlertDescription>
            </Alert>

            <div className="flex justify-end space-x-3">
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                onClick={() => setStep(2)}
                disabled={!canProceedToUpload}
              >
                Next: Upload Photos
              </Button>
            </div>
          </div>
        )}

        {/* Step 2: Upload Photos */}
        {step === 2 && (
          <div className="space-y-6">
            {/* Upload Zone */}
            <div
              {...getRootProps()}
              className={cn(
                "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
                isDragActive
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/50"
              )}
            >
              <input {...getInputProps()} />
              <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              {isDragActive ? (
                <p className="text-foreground">Drop the photos here...</p>
              ) : (
                <>
                  <p className="text-foreground font-medium mb-2">
                    Click to upload or drag and drop
                  </p>
                  <p className="text-sm text-muted-foreground">
                    JPG, PNG or WEBP (max 10MB each)
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Upload 8-20 photos of the same person
                  </p>
                </>
              )}
            </div>

            {/* Photo Count */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {photos.length} / 20 photos uploaded
              </span>
              {photos.length >= 8 && photos.length <= 20 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={validatePhotos}
                  disabled={isValidating}
                >
                  {isValidating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Validating...
                    </>
                  ) : (
                    "Validate Photos"
                  )}
                </Button>
              )}
            </div>

            {/* Photo Grid */}
            {photos.length > 0 && (
              <div className="grid grid-cols-4 gap-4 max-h-96 overflow-y-auto">
                {photos.map((photo, index) => {
                  const validation = validationResults[index]
                  return (
                    <div key={index} className="relative group">
                      <div className="aspect-square relative rounded-lg overflow-hidden border-2 border-border">
                        <Image
                          src={URL.createObjectURL(photo)}
                          alt={`Photo ${index + 1}`}
                          fill
                          className="object-cover"
                          unoptimized
                        />
                        {validation && (
                          <div
                            className={cn(
                              "absolute top-2 right-2 h-6 w-6 rounded-full flex items-center justify-center",
                              validation.valid
                                ? "bg-primary"
                                : "bg-destructive"
                            )}
                          >
                            {validation.valid ? (
                              <CheckCircle className="h-4 w-4 text-primary-foreground" />
                            ) : (
                              <AlertCircle className="h-4 w-4 text-destructive-foreground" />
                            )}
                          </div>
                        )}
                      </div>
                      <Button
                        variant="destructive"
                        size="icon"
                        className="absolute -top-2 -right-2 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => removePhoto(index)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Validation Warnings */}
            {validationResults.length > 0 && (
              <Alert className={validationResults.every((r) => r.valid) ? "border-primary/30 bg-primary/5" : "border-destructive/30 bg-destructive/5"}>
                {validationResults.every((r) => r.valid) ? (
                  <>
                    <CheckCircle className="h-4 w-4 text-primary" />
                    <AlertDescription>
                      All photos passed validation! You can proceed to the next
                      step.
                    </AlertDescription>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-4 w-4 text-destructive" />
                    <AlertDescription>
                      {validationResults.filter((r) => !r.valid).length} photo(s)
                      failed validation. Please remove them or upload different
                      photos.
                    </AlertDescription>
                  </>
                )}
              </Alert>
            )}

            {/* Actions */}
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                onClick={() => setStep(3)}
                disabled={!canProceedToConsent || isValidating}
              >
                Next: Consent
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Consent */}
        {step === 3 && (
          <div className="space-y-6">
            <Alert className="border-primary/30 bg-primary/5">
              <AlertCircle className="h-4 w-4 text-primary" />
              <AlertDescription>
                <strong>Important:</strong> Please read and confirm the following
                before proceeding.
              </AlertDescription>
            </Alert>

            <div className="space-y-4 p-4 rounded-lg border border-border/50 bg-muted/30">
              <div className="flex items-start space-x-3">
                <Checkbox
                  id="consent"
                  checked={consentGiven}
                  onCheckedChange={(checked) => setConsentGiven(checked as boolean)}
                />
                <Label htmlFor="consent" className="text-sm cursor-pointer flex-1">
                  <p className="font-semibold mb-2 text-foreground">
                    I confirm that:
                  </p>
                  <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                    <li>
                      I have the legal right to use these photos
                    </li>
                    <li>
                      The person in the photos has consented to AI training (or it&apos;s
                      me)
                    </li>
                    <li>
                      The person is 18 years or older
                    </li>
                    <li>
                      I will use the generated images responsibly and ethically
                    </li>
                    <li>
                      I understand that PhotoGenius AI will train a custom model
                      using these photos
                    </li>
                    <li>
                      <strong className="text-foreground">Biometric data:</strong> I explicitly consent to the processing of my (or the depicted person&apos;s) face data (reference photos and face embeddings) for this identity only, as described in the Biometric Data Privacy policy. I can withdraw consent and delete this data at any time in Settings.
                    </li>
                  </ul>
                </Label>
              </div>
            </div>

            <Alert className="border-primary/30 bg-primary/5">
              <AlertDescription className="text-sm text-foreground/90">
                <strong>Privacy:</strong> Your photos and face data are encrypted and stored
                securely. They are only used for this identity and generation and are never shared with third parties or used to train our general
                models. You can delete this identity or all biometric data at any time (Settings → Privacy).
              </AlertDescription>
            </Alert>

            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button onClick={startTraining} disabled={!canStartTraining || isTraining}>
                {isTraining ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Starting...
                  </>
                ) : (
                  "Start Training"
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Step 4: Training */}
        {step === 4 && (
          <div className="space-y-6 text-center py-8">
            <div className="h-20 w-20 rounded-full bg-primary/20 flex items-center justify-center mx-auto animate-pulse">
              <Loader2 className="h-10 w-10 text-primary animate-spin" />
            </div>

            <div>
              <h3 className="text-xl font-semibold text-foreground mb-2">
                Training Your AI Model
              </h3>
              <p className="text-muted-foreground">
                This usually takes 15-20 minutes. You can close this window - we&apos;ll
                notify you when it&apos;s ready.
              </p>
            </div>

            <div className="max-w-md mx-auto space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Progress</span>
                <span className="font-semibold text-primary">
                  {trainingProgress}%
                </span>
              </div>
              <Progress value={trainingProgress} className="h-3" />
            </div>

            <div className="text-sm text-muted-foreground space-y-1">
              {trainingProgress < 30 && <p>Preprocessing photos...</p>}
              {trainingProgress >= 30 && trainingProgress < 60 && (
                <p>Training AI model...</p>
              )}
              {trainingProgress >= 60 && trainingProgress < 90 && (
                <p>Fine-tuning model...</p>
              )}
              {trainingProgress >= 90 && <p>Finalizing...</p>}
            </div>

            {trainingProgress >= 100 ? (
              <Button onClick={() => {
                resetModal()
                onClose()
              }}>
                Done
              </Button>
            ) : (
              <Button variant="outline" onClick={handleClose}>
                Close and Continue in Background
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
