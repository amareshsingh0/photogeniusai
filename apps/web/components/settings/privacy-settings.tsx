"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Shield, CheckCircle, ExternalLink, Trash2, Loader2 } from "lucide-react"
import Link from "next/link"
import { useToast } from "@/components/ui/use-toast"

export function PrivacySettings() {
  const [erasing, setErasing] = useState(false)
  const { toast } = useToast()

  const handleEraseBiometric = async () => {
    if (!confirm("Permanently erase all your identity (biometric) data? This cannot be undone.")) return
    setErasing(true)
    try {
      const res = await fetch("/api/identities/erasure", { method: "POST" })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        toast({ title: "Biometric data erased", description: data.message })
        window.location.href = "/identity-vault"
      } else {
        toast({ title: "Error", description: data.error || "Failed to erase", variant: "destructive" })
      }
    } catch {
      toast({ title: "Error", description: "Request failed", variant: "destructive" })
    } finally {
      setErasing(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Consent Status */}
      <Card className="glass-card border-primary/30 bg-primary/10">
        <CardContent className="pt-6">
          <div className="flex items-center space-x-3">
            <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center">
              <CheckCircle className="h-6 w-6 text-primary" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-foreground">
                Consent Verified
              </h3>
              <p className="text-sm text-muted-foreground">
                You have provided consent for all uploaded identities
              </p>
            </div>
            <Badge className="bg-primary border-primary/30">Active</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Data Privacy */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Data Privacy</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 rounded-lg bg-primary/10 border border-primary/30">
            <div className="flex items-start space-x-3">
              <Shield className="h-5 w-5 text-primary mt-0.5" />
              <div>
                <h4 className="font-semibold text-foreground mb-1">
                  Your Data is Protected
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• All photos are encrypted in transit and at rest</li>
                  <li>• Face embeddings are anonymized</li>
                  <li>• We never share your data with third parties</li>
                  <li>• You can delete your data at any time</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <Link href="/settings/data-request">
              <Button variant="outline" className="w-full justify-between">
                <span className="text-foreground">Data subject request (access / export / delete)</span>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </Button>
            </Link>

            <Button
              variant="outline"
              className="w-full justify-between text-destructive hover:text-destructive"
              onClick={handleEraseBiometric}
              disabled={erasing}
            >
              <span>{erasing ? "Erasing…" : "Delete my biometric data (all identities)"}</span>
              {erasing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            </Button>

            <Button variant="outline" className="w-full justify-between" asChild>
              <a href="/legal/privacy" target="_blank" rel="noopener noreferrer">
                <span className="text-foreground">View Privacy Policy</span>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </a>
            </Button>

            <Button variant="outline" className="w-full justify-between" asChild>
              <a href="/legal/terms" target="_blank" rel="noopener noreferrer">
                <span className="text-foreground">View Terms of Service</span>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Consent Management */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Consent Management</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            You can review and manage consent for each identity in your vault.
          </p>

          <Link href="/identity-vault">
            <Button variant="outline" className="w-full">
              View Identity Vault
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
