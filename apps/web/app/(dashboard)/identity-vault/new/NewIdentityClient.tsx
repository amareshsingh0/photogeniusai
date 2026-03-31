"use client"

import { useState } from "react"
import { IdentityUploadForm } from "@/components/identities/upload-form"
import { ConsentDialog } from "@/components/identities/consent-dialog"
import { TrainingProgress } from "@/components/identities/training-progress"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { CheckCircle, Sparkles, AlertCircle } from "lucide-react"
import Link from "next/link"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { Alert, AlertDescription } from "@/components/ui/alert"

type Step = "upload" | "consent" | "training" | "complete"

export default function NewIdentityClient() {
  const [step, setStep] = useState<Step>("upload")
  const [uploadedPhotos, setUploadedPhotos] = useState<File[]>([])
  const [identityName, setIdentityName] = useState("")
  const [identityId, setIdentityId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  const handleUploadComplete = (photos: File[], name: string) => {
    setUploadedPhotos(photos)
    setIdentityName(name)
    setStep("consent")
  }

  const handleConsentAccepted = async () => {
    setError(null)
    setStep("training")
    // Start training process
    await startTraining()
  }

  const startTraining = async () => {
    try {
      setIsUploading(true)
      setError(null)
      
      // First, upload all photos and create identity
      const { uploadFile, createIdentity, startTraining: startTrainingAPI } = await import("@/lib/api")
      
      // Upload all photos with progress tracking
      const uploadPromises = uploadedPhotos.map((photo, index) => 
        uploadFile(photo).catch((err) => {
          throw new Error(`Failed to upload photo ${index + 1}: ${err.message}`)
        })
      )
      const uploadResults = await Promise.all(uploadPromises)
      const imageUrls = uploadResults.map((result) => result.url)

      // Create identity
      const identity = await createIdentity({
        name: identityName,
        imageUrls,
      })

      setIdentityId(identity.id)

      // Start training
      await startTrainingAPI(identity.id)
    } catch (error) {
      console.error("Failed to start training:", error)
      setError(error instanceof Error ? error.message : "Failed to start training")
      setStep("consent") // Go back to consent step so user can retry
    } finally {
      setIsUploading(false)
    }
  }

  const handleTrainingComplete = () => {
    setStep("complete")
  }

  const steps = [
    { id: "upload", label: "Upload", value: 1 },
    { id: "consent", label: "Consent", value: 2 },
    { id: "training", label: "Training", value: 3 },
    { id: "complete", label: "Complete", value: 4 },
  ] as const

  const currentStepIndex = steps.findIndex(s => s.id === step)

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="text-3xl font-bold">Create New Identity</h1>
        <p className="mt-2 text-muted-foreground">
          Upload 8-20 photos of yourself to create your AI identity
        </p>
      </motion.div>

      {/* Steps Indicator */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="flex items-center justify-center space-x-4 overflow-x-auto pb-4"
      >
        {steps.map((stepItem, index) => {
          const isActive = index === currentStepIndex
          const isCompleted = index < currentStepIndex

          return (
            <div key={stepItem.id} className="flex items-center">
              <div className="flex flex-col items-center min-w-[80px]">
                <div
                  className={cn(
                    "h-10 w-10 rounded-full flex items-center justify-center font-semibold transition-all",
                    isCompleted
                      ? "bg-green-500 text-white"
                      : isActive
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {isCompleted ? "✓" : stepItem.value}
                </div>
                <span className={cn(
                  "mt-2 text-sm font-medium whitespace-nowrap",
                  isActive ? "text-foreground" : "text-muted-foreground"
                )}>
                  {stepItem.label}
                </span>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={cn(
                    "h-1 w-16 mx-2 transition-colors",
                    isCompleted ? "bg-green-500" : "bg-muted"
                  )}
                />
              )}
            </div>
          )
        })}
      </motion.div>

      {/* Error Alert */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-4xl mx-auto"
        >
          <Alert variant="destructive" className="rounded-xl">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        </motion.div>
      )}

      {/* Content */}
      <motion.div
        key={step}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
      >
        {step === "upload" && (
          <IdentityUploadForm onComplete={handleUploadComplete} />
        )}

        {step === "consent" && (
          <ConsentDialog
            identityName={identityName}
            photoCount={uploadedPhotos.length}
            onAccept={handleConsentAccepted}
            onCancel={() => {
              setError(null)
              setStep("upload")
            }}
          />
        )}

        {step === "training" && (
          <>
            {isUploading && !identityId && (
              <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
                <CardContent className="p-8 text-center">
                  <div className="flex flex-col items-center gap-4">
                    <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                    <p className="text-muted-foreground">
                      Uploading photos and creating identity...
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
            {identityId && (
              <TrainingProgress
                identityId={identityId}
                onComplete={handleTrainingComplete}
              />
            )}
          </>
        )}

        {step === "complete" && (
          <Card className="border-green-500/50 bg-green-500/10 backdrop-blur-sm">
            <CardHeader>
              <div className="flex items-center gap-2">
                <CheckCircle className="h-6 w-6 text-green-600" />
                <CardTitle className="text-green-600">✓ Identity Created!</CardTitle>
              </div>
              <CardDescription>
                Your identity &quot;{identityName}&quot; is ready to use
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-muted-foreground">
                You can now use this identity to generate AI avatars.
              </p>
              <div className="flex flex-wrap gap-4">
                <Link href="/generate">
                  <Button className="rounded-xl">
                    <Sparkles className="h-4 w-4 mr-2" />
                    Generate Image
                  </Button>
                </Link>
                <Link href="/identity-vault">
                  <Button variant="outline" className="rounded-xl">
                    View Identities
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        )}
      </motion.div>
    </div>
  )
}
