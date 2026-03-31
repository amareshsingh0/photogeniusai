"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { CheckCircle, Loader2, Sparkles, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { useTrainingUpdates } from "@/lib/socket"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface TrainingProgressProps {
  identityId: string
  onComplete: () => void
}

const TRAINING_STEPS = [
  { id: 1, name: "Uploading photos", progress: 5 },
  { id: 2, name: "Validating images", progress: 15 },
  { id: 3, name: "Detecting faces", progress: 25 },
  { id: 4, name: "Preprocessing", progress: 35 },
  { id: 5, name: "Generating captions", progress: 50 },
  { id: 6, name: "Training model", progress: 80 },
  { id: 7, name: "Extracting embeddings", progress: 90 },
  { id: 8, name: "Finalizing", progress: 100 },
]

export function TrainingProgress({ identityId, onComplete }: TrainingProgressProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [progress, setProgress] = useState(0)
  const [currentMessage, setCurrentMessage] = useState("Starting training...")
  const [error, setError] = useState<string | null>(null)

  // Use WebSocket for real-time updates
  const { connected } = useTrainingUpdates(identityId, (data) => {
    setProgress(data.progress)
    setCurrentMessage(data.message || "Training in progress...")
    
    // Map progress to step
    const stepIndex = TRAINING_STEPS.findIndex(
      (step) => data.progress <= step.progress
    )
    if (stepIndex >= 0) {
      setCurrentStep(stepIndex + 1)
    }

    // Check if complete
    if (data.progress >= 100) {
      setTimeout(() => {
        onComplete()
      }, 1000)
    }
  })

  // Fallback: Poll for progress if WebSocket not connected
  useEffect(() => {
    if (connected) return // WebSocket is handling updates

    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/identities/${identityId}`, {
          cache: "no-store",
        })
        if (response.ok) {
          const identity = await response.json()
          if (identity.trainingProgress !== undefined) {
            setProgress(identity.trainingProgress)
            
            // Map progress to step
            const stepIndex = TRAINING_STEPS.findIndex(
              (step) => identity.trainingProgress <= step.progress
            )
            if (stepIndex >= 0) {
              setCurrentStep(stepIndex + 1)
            }

            if (identity.trainingStatus === "COMPLETED") {
              clearInterval(pollInterval)
              onComplete()
            } else if (identity.trainingStatus === "FAILED") {
              clearInterval(pollInterval)
              setError(identity.trainingError || "Training failed")
            }
          }
        }
      } catch (err) {
        console.error("Failed to poll training progress:", err)
      }
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(pollInterval)
  }, [connected, identityId, onComplete])

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" />
          <CardTitle>Training Your Identity</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground">
          This will take approximately 15-20 minutes
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="font-medium text-foreground">Overall Progress</span>
            <span className="text-muted-foreground">{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-3 rounded-full" />
        </div>

        {/* Steps */}
        <div className="space-y-3">
          {TRAINING_STEPS.map((step, index) => {
            const isCompleted = index < currentStep
            const isActive = index === currentStep - 1
            const isPending = index >= currentStep

            return (
              <div
                key={step.id}
                className={cn(
                  "flex items-center space-x-3 p-3 rounded-xl transition-all",
                  isActive && "bg-primary/10 border border-primary/20"
                )}
              >
                {isCompleted ? (
                  <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" />
                ) : isActive ? (
                  <Loader2 className="h-5 w-5 text-primary animate-spin flex-shrink-0" />
                ) : (
                  <div className="h-5 w-5 rounded-full border-2 border-muted-foreground/30 flex-shrink-0" />
                )}
                <span
                  className={cn(
                    "text-sm",
                    isCompleted
                      ? "text-muted-foreground line-through"
                      : isActive
                      ? "text-primary font-medium"
                      : "text-muted-foreground"
                  )}
                >
                  {step.name}
                </span>
              </div>
            )
          })}
        </div>

        {/* Error */}
        {error && (
          <Alert variant="destructive" className="rounded-xl">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Info */}
        <div className="rounded-xl bg-primary/10 border border-primary/20 p-4 text-sm">
          <p className="font-medium mb-1 text-primary">💡 Tip</p>
          <p className="text-muted-foreground">
            {connected 
              ? "Real-time updates enabled. You can close this page and come back later."
              : "Polling for updates. You can close this page and come back later."}
          </p>
          {currentMessage && (
            <p className="text-xs text-muted-foreground mt-2 italic">
              {currentMessage}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
