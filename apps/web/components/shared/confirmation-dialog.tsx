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
import { AlertTriangle, CheckCircle, Info } from "lucide-react"
import { cn } from "@/lib/utils"

interface ConfirmationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: "default" | "destructive" | "info"
  onConfirm: () => void
  onCancel?: () => void
}

export function ConfirmationDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  const handleCancel = () => {
    onCancel?.()
    onOpenChange(false)
  }

  const handleConfirm = () => {
    onConfirm()
    onOpenChange(false)
  }

  const getIcon = () => {
    switch (variant) {
      case "destructive":
        return <AlertTriangle className="h-5 w-5 text-destructive" />
      case "info":
        return <Info className="h-5 w-5 text-primary" />
      default:
        return <CheckCircle className="h-5 w-5 text-primary" />
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="glass-card">
        <AlertDialogHeader>
          <div className="flex items-center space-x-2">
            <div
              className={cn(
                "h-10 w-10 rounded-full flex items-center justify-center",
                variant === "destructive"
                  ? "bg-destructive/20"
                  : variant === "info"
                  ? "bg-primary/20"
                  : "bg-primary/20"
              )}
            >
              {getIcon()}
            </div>
            <AlertDialogTitle className="text-foreground">{title}</AlertDialogTitle>
          </div>
          <AlertDialogDescription className="text-muted-foreground">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancel}>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            className={cn(
              variant === "destructive" && "bg-destructive hover:bg-destructive/90"
            )}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
