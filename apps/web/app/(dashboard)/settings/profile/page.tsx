"use client"

import { User } from "lucide-react"
import { SettingsPageLayout } from "@/components/settings/settings-page-layout"
import { ProfileSettings } from "@/components/settings/profile-settings"

export default function ProfilePage() {
  return (
    <SettingsPageLayout
      icon={User}
      title="Profile"
      description="Manage your profile, avatar, and account details."
    >
      <ProfileSettings />
    </SettingsPageLayout>
  )
}
