"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { useToast } from "@/components/ui/use-toast"

const DEFAULT_GEN_SETTINGS = {
  defaultMode: "REALISM",
  defaultIdentity: "auto",
  qualityPreference: [80],
  autoSaveToGallery: true,
  autoDownload: false,
  watermark: false,
}

export function GenerationDefaults() {
  const { toast } = useToast()
  const [settings, setSettings] = useState(DEFAULT_GEN_SETTINGS)

  useEffect(() => {
    try {
      const stored = localStorage.getItem("generation_defaults")
      if (stored) setSettings(JSON.parse(stored))
    } catch {}
  }, [])

  const handleSave = () => {
    try {
      localStorage.setItem("generation_defaults", JSON.stringify(settings))
    } catch {}
    toast({
      title: "Defaults saved",
      description: "Your generation defaults have been updated.",
    })
  }

  return (
    <div className="space-y-6">
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Generation Defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Default Mode */}
          <div className="space-y-2">
            <Label className="text-foreground">Default Generation Mode</Label>
            <Select
              value={settings.defaultMode}
              onValueChange={(value) =>
                setSettings({ ...settings, defaultMode: value })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="REALISM">Realism Mode</SelectItem>
                <SelectItem value="CREATIVE">Creative Mode</SelectItem>
                <SelectItem value="ROMANTIC">Romantic Mode</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              This mode will be pre-selected when you start a new generation
            </p>
          </div>

          {/* Default Identity */}
          <div className="space-y-2">
            <Label className="text-foreground">Default Identity</Label>
            <Select
              value={settings.defaultIdentity}
              onValueChange={(value) =>
                setSettings({ ...settings, defaultIdentity: value })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Auto-select last used</SelectItem>
                <SelectItem value="professional">Professional</SelectItem>
                <SelectItem value="casual">Casual</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Quality Preference */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-foreground">Minimum Quality Score</Label>
              <span className="text-sm font-medium text-primary">
                {settings.qualityPreference[0]}%
              </span>
            </div>
            <Slider
              value={settings.qualityPreference}
              onValueChange={(value) =>
                setSettings({ ...settings, qualityPreference: value })
              }
              min={60}
              max={95}
              step={5}
            />
            <p className="text-sm text-muted-foreground">
              Only show images above this quality threshold
            </p>
          </div>

          {/* Auto Save */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Auto-save to Gallery</Label>
              <p className="text-sm text-muted-foreground">
                Automatically save generated images to your gallery
              </p>
            </div>
            <Switch
              checked={settings.autoSaveToGallery}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, autoSaveToGallery: checked })
              }
            />
          </div>

          {/* Auto Download */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Auto-download</Label>
              <p className="text-sm text-muted-foreground">
                Automatically download generated images
              </p>
            </div>
            <Switch
              checked={settings.autoDownload}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, autoDownload: checked })
              }
            />
          </div>

          {/* Watermark */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-foreground">Add Watermark</Label>
              <p className="text-sm text-muted-foreground">
                Add PhotoGenius watermark to downloads (Pro only)
              </p>
            </div>
            <Switch
              checked={settings.watermark}
              onCheckedChange={(checked) =>
                setSettings({ ...settings, watermark: checked })
              }
              disabled
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave}>Save Defaults</Button>
      </div>
    </div>
  )
}
