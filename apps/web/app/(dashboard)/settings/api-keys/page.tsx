"use client"

import { Key } from "lucide-react"
import { SettingsPageLayout } from "@/components/settings/settings-page-layout"
import { ApiKeysSettings } from "@/components/settings/api-keys-settings"

export default function ApiKeysPage() {
  return (
    <SettingsPageLayout
      icon={Key}
      title="API Keys"
      description="Create and manage API keys for programmatic access to PhotoGenius AI."
    >
      <ApiKeysSettings />
    </SettingsPageLayout>
  )
}
