"use client"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { AlertTriangle } from "lucide-react"

interface DeleteConfirmDialogProps {
  count: number
  onConfirm: () => void
  onCancel: () => void
}

export function DeleteConfirmDialog({
  count,
  onConfirm,
  onCancel,
}: DeleteConfirmDialogProps) {
  return (
    <AlertDialog open={true} onOpenChange={onCancel}>
      <AlertDialogContent className="glass-card">
        <AlertDialogHeader>
          <div className="flex items-center space-x-2">
            <div className="h-10 w-10 rounded-full bg-destructive/20 flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <AlertDialogTitle className="text-foreground">
              Delete {count === 1 ? "Image" : `${count} Images`}?
            </AlertDialogTitle>
          </div>
          <AlertDialogDescription className="text-muted-foreground">
            This action cannot be undone. {count === 1 ? "This image" : "These images"} will be
            permanently deleted from your gallery.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-destructive hover:bg-destructive/90"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
