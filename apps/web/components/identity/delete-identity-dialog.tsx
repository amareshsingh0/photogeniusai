"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"
import { AlertTriangle, Loader2 } from "lucide-react"

interface DeleteIdentityDialogProps {
  identity: { id: string; name: string; imageUrls?: string[]; referencePhotos?: number; generations?: number } | null
  isOpen: boolean
  onClose: () => void
  onDelete: (hardErase: boolean) => void
  isDeleting?: boolean
}

export function DeleteIdentityDialog({
  identity,
  isOpen,
  onClose,
  onDelete,
  isDeleting = false,
}: DeleteIdentityDialogProps) {
  const [hardErase, setHardErase] = useState(false)
  const photoCount = identity?.referencePhotos ?? (identity?.imageUrls?.length ?? 0)
  const genCount = identity?.generations ?? 0
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="glass-card max-w-md">
        <DialogHeader>
          <DialogTitle>Delete identity?</DialogTitle>
          <DialogDescription>
            This will remove the identity from your vault. Past generations using it will remain, but you won&apos;t be able to use this identity again.
          </DialogDescription>
        </DialogHeader>

        <Alert variant="destructive" className="border-destructive/50 bg-destructive/10">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Deleting &ldquo;<strong>{identity?.name ?? "Untitled"}</strong>&rdquo; will remove:
            <ul className="list-disc list-inside mt-2 space-y-1 text-sm">
              <li>{photoCount} reference photos from this identity</li>
              <li>Trained AI model (LoRA) for this identity</li>
              {genCount > 0 && <li>Link to {genCount} past generation(s) (images stay)</li>}
            </ul>
          </AlertDescription>
        </Alert>

        <div className="flex items-start space-x-2">
          <Checkbox
            id="hard-erase"
            checked={hardErase}
            onCheckedChange={(c) => setHardErase(!!c)}
          />
          <label htmlFor="hard-erase" className="text-sm text-muted-foreground cursor-pointer">
            Permanently erase biometric data (GDPR full erasure). Reference photos and face data will be removed from our systems; S3 cleanup may run asynchronously.
          </label>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => onDelete(hardErase)} disabled={isDeleting}>
            {isDeleting ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Deleting…</> : "Delete identity"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
