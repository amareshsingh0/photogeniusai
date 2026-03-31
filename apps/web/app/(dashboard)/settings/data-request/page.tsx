"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Shield, Download, Trash2, FileText, Loader2 } from "lucide-react"
import { useToast } from "@/components/ui/use-toast"

type RequestType = "access" | "export" | "erasure"

export default function DataRequestPage() {
  const [requestType, setRequestType] = useState<RequestType>("export")
  const [submitting, setSubmitting] = useState(false)
  const [exportedId, setExportedId] = useState<string | null>(null)
  const { toast } = useToast()

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      if (requestType === "erasure") {
        const res = await fetch("/api/identities/erasure", { method: "POST" })
        const data = await res.json().catch(() => ({}))
        if (res.ok) {
          toast({ title: "Request completed", description: data.message })
          setRequestType("export")
        } else {
          toast({ title: "Error", description: data.error || "Request failed", variant: "destructive" })
        }
        return
      }

      if (requestType === "access" || requestType === "export") {
        const listRes = await fetch("/api/identities")
        if (!listRes.ok) {
          toast({ title: "Error", description: "Could not load identities", variant: "destructive" })
          return
        }
        const identities = await listRes.json()
        if (!identities?.length) {
          toast({ title: "No data", description: "You have no identities to export." })
          return
        }
        const id = identities[0].id
        const exportRes = await fetch(`/api/identities/${id}/export`)
        if (!exportRes.ok) {
          toast({ title: "Error", description: "Export failed", variant: "destructive" })
          return
        }
        const blob = await exportRes.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `identity-export-${id}.json`
        a.click()
        URL.revokeObjectURL(url)
        setExportedId(id)
        toast({ title: "Export downloaded", description: "First identity export downloaded. Export others from Identity Vault → identity → Export." })
      }
    } catch {
      toast({ title: "Error", description: "Request failed", variant: "destructive" })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="container max-w-2xl py-8">
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-foreground">
            <Shield className="h-5 w-5" />
            Data subject request
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            GDPR / CCPA: request access to your data, export it (portability), or request erasure of your biometric (identity) data.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-3">
            <Label>Request type</Label>
            <RadioGroup value={requestType} onValueChange={(v) => setRequestType(v as RequestType)} className="space-y-2">
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="access" id="access" />
                <Label htmlFor="access" className="font-normal flex items-center gap-2">
                  <FileText className="h-4 w-4" /> Right to access – see what we hold
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="export" id="export" />
                <Label htmlFor="export" className="font-normal flex items-center gap-2">
                  <Download className="h-4 w-4" /> Right to portability – download my identity data
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="erasure" id="erasure" />
                <Label htmlFor="erasure" className="font-normal flex items-center gap-2">
                  <Trash2 className="h-4 w-4" /> Right to erasure – delete all my biometric data
                </Label>
              </div>
            </RadioGroup>
          </div>

          {requestType === "erasure" && (
            <p className="text-sm text-amber-600 dark:text-amber-500">
              This will permanently delete all identities (reference photos, face embeddings, LoRA files). This cannot be undone.
            </p>
          )}

          <Button onClick={handleSubmit} disabled={submitting} className="w-full">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : "Submit request"}
          </Button>

          <p className="text-xs text-muted-foreground">
            For full account deletion or other requests, contact privacy@photogenius.ai.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
