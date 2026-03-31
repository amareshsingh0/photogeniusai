"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Facebook,
  Twitter,
  Linkedin,
  Instagram,
  Link2,
  CheckCircle,
} from "lucide-react"
import Image from "next/image"

interface ShareDialogProps {
  image: any
  onClose: () => void
}

export function ShareDialog({ image, onClose }: ShareDialogProps) {
  const [copied, setCopied] = useState(false)

  const shareUrl = `https://photogenius.ai/gallery/${image.id}`

  const handleCopyLink = () => {
    navigator.clipboard.writeText(shareUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const socialShares = [
    {
      name: "Twitter",
      icon: Twitter,
      url: `https://twitter.com/intent/tweet?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent("Check out my AI-generated avatar!")}`,
      color: "bg-primary/20",
      iconColor: "text-primary",
    },
    {
      name: "Facebook",
      icon: Facebook,
      url: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`,
      color: "bg-primary/20",
      iconColor: "text-primary",
    },
    {
      name: "LinkedIn",
      icon: Linkedin,
      url: `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`,
      color: "bg-primary/20",
      iconColor: "text-primary",
    },
    {
      name: "Instagram",
      icon: Instagram,
      url: "#",
      color: "bg-gradient-to-r from-primary/20 to-secondary/20",
      iconColor: "text-primary",
    },
  ]

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="glass-card">
        <DialogHeader>
          <DialogTitle>Share Image</DialogTitle>
          <DialogDescription>
            Share your AI-generated image with others
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Preview */}
          <div className="relative aspect-square rounded-lg overflow-hidden border border-border/50 max-w-xs mx-auto">
            <Image
              src={image.thumbnail}
              alt="Share preview"
              fill
              className="object-cover"
              sizes="320px"
            />
          </div>

          {/* Social Share Buttons */}
          <div className="grid grid-cols-4 gap-3">
            {socialShares.map((social) => {
              const Icon = social.icon
              return (
                <button
                  key={social.name}
                  onClick={() => window.open(social.url, "_blank")}
                  className="flex flex-col items-center space-y-2 p-3 rounded-lg border border-border/50 hover:bg-muted/30 transition-colors glass-card"
                >
                  <div
                    className={`h-10 w-10 rounded-full ${social.color} flex items-center justify-center`}
                  >
                    <Icon className={`h-5 w-5 ${social.iconColor}`} />
                  </div>
                  <span className="text-xs text-muted-foreground">{social.name}</span>
                </button>
              )
            })}
          </div>

          {/* Copy Link */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">
              Share Link
            </label>
            <div className="flex space-x-2">
              <Input value={shareUrl} readOnly className="flex-1" />
              <Button onClick={handleCopyLink} variant="outline">
                {copied ? (
                  <>
                    <CheckCircle className="mr-2 h-4 w-4 text-primary" />
                    Copied
                  </>
                ) : (
                  <>
                    <Link2 className="mr-2 h-4 w-4" />
                    Copy
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
