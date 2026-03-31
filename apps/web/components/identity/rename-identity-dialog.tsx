"use client"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface RenameIdentityDialogProps {
  identity: any
  isOpen: boolean
  onClose: () => void
  onRename: (newName: string) => void
}

export function RenameIdentityDialog({
  identity,
  isOpen,
  onClose,
  onRename,
}: RenameIdentityDialogProps) {
  const [newName, setNewName] = useState(identity.name)

  useEffect(() => {
    if (isOpen) {
      setNewName(identity.name)
    }
  }, [isOpen, identity.name])

  const handleRename = () => {
    if (newName.trim().length >= 3) {
      onRename(newName.trim())
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="glass-card">
        <DialogHeader>
          <DialogTitle>Rename Identity</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="new-name">New Name</Label>
            <Input
              id="new-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Enter new name"
              maxLength={30}
              onKeyDown={(e) => {
                if (e.key === "Enter" && newName.trim().length >= 3 && newName !== identity.name) {
                  handleRename()
                }
              }}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleRename}
            disabled={newName.trim().length < 3 || newName === identity.name}
          >
            Rename
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
