"use client"

import { Palette } from "lucide-react"
import { SettingsPageLayout } from "@/components/settings/settings-page-layout"
import { GenerationDefaults } from "@/components/settings/generation-defaults"

export default function GenerationDefaultsPage() {
  return (
    <SettingsPageLayout
      icon={Palette}
      title="Generation Defaults"
      description="Set default style, aspect ratio, and quality options for image generation."
    >
      <GenerationDefaults />
    </SettingsPageLayout>
  )
}
