"use client"

import { Shield } from "lucide-react"
import { SettingsPageLayout } from "@/components/settings/settings-page-layout"
import { PrivacySettings } from "@/components/settings/privacy-settings"

export default function PrivacyPage() {
  return (
    <SettingsPageLayout
      icon={Shield}
      title="Privacy & Consent"
      description="Control your privacy settings, data consent, and how we use your information."
    >
      <PrivacySettings />
    </SettingsPageLayout>
  )
}
