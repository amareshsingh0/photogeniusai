"use client"

import { Bell } from "lucide-react"
import { SettingsPageLayout } from "@/components/settings/settings-page-layout"
import { NotificationSettings } from "@/components/settings/notification-settings"

export default function NotificationsPage() {
  return (
    <SettingsPageLayout
      icon={Bell}
      title="Notifications"
      description="Configure how and when you receive email and push notifications."
    >
      <NotificationSettings />
    </SettingsPageLayout>
  )
}
