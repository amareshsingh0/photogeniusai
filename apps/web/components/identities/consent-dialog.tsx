"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Shield, AlertTriangle } from "lucide-react"

interface ConsentDialogProps {
  identityName: string
  photoCount: number
  onAccept: () => void
  onCancel: () => void
}

export function ConsentDialog({
  identityName,
  photoCount,
  onAccept,
  onCancel,
}: ConsentDialogProps) {
  const [consents, setConsents] = useState({
    ownership: false,
    age: false,
    terms: false,
    privacy: false,
  })

  const allConsented = Object.values(consents).every(v => v)

  const handleConsent = (key: keyof typeof consents) => {
    setConsents(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-center space-x-2">
          <Shield className="h-6 w-6 text-primary" />
          <CardTitle>Consent & Legal Agreement</CardTitle>
        </div>
        <CardDescription>
          Please read and accept the following terms to continue
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Warning */}
        <Alert className="rounded-xl border-orange-500/50 bg-orange-500/10">
          <AlertTriangle className="h-4 w-4 text-orange-500" />
          <AlertDescription className="text-orange-900 dark:text-orange-200">
            You are creating an AI identity with {photoCount} photos for &quot;{identityName}&quot;.
            This process is irreversible once training begins.
          </AlertDescription>
        </Alert>

        {/* Consent Items */}
        <div className="space-y-4">
          <ConsentItem
            checked={consents.ownership}
            onCheckedChange={() => handleConsent("ownership")}
            title="Photo Ownership"
            description="I confirm that I own the rights to all uploaded photos or have explicit permission to use them for AI training."
          />

          <ConsentItem
            checked={consents.age}
            onCheckedChange={() => handleConsent("age")}
            title="Age Verification"
            description="I confirm that all individuals in the photos are 18 years of age or older."
          />

          <ConsentItem
            checked={consents.terms}
            onCheckedChange={() => handleConsent("terms")}
            title="Terms of Service"
            description="I have read and agree to the Terms of Service and Acceptable Use Policy."
          />

          <ConsentItem
            checked={consents.privacy}
            onCheckedChange={() => handleConsent("privacy")}
            title="Privacy Policy"
            description="I understand how my data will be processed according to the Privacy Policy."
          />
        </div>

        {/* Additional Info */}
        <div className="rounded-xl bg-muted/50 p-4 space-y-2">
          <h4 className="font-semibold text-sm text-foreground">What happens next?</h4>
          <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
            <li>Your photos will be processed to train a custom AI model</li>
            <li>Training takes approximately 15-20 minutes</li>
            <li>You&apos;ll be notified when your identity is ready</li>
            <li>Photos are encrypted and stored securely</li>
          </ul>
        </div>
      </CardContent>

      <CardFooter className="flex space-x-4">
        <Button
          variant="outline"
          onClick={onCancel}
          className="flex-1 rounded-xl"
        >
          Cancel
        </Button>
        <Button
          onClick={onAccept}
          disabled={!allConsented}
          className="flex-1 rounded-xl"
        >
          Accept & Start Training
        </Button>
      </CardFooter>
    </Card>
  )
}

function ConsentItem({
  checked,
  onCheckedChange,
  title,
  description,
}: {
  checked: boolean
  onCheckedChange: () => void
  title: string
  description: string
}) {
  return (
    <div 
      className="flex items-start space-x-3 p-4 rounded-xl border border-border/50 hover:bg-muted/30 transition-colors cursor-pointer"
      onClick={onCheckedChange}
    >
      <Checkbox
        checked={checked}
        onCheckedChange={onCheckedChange}
        className="mt-1"
      />
      <div className="flex-1">
        <h4 className="font-medium text-foreground">{title}</h4>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
    </div>
  )
}
