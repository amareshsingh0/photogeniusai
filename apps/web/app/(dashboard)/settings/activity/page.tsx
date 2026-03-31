"use client"

import { Activity } from "lucide-react"
import { SettingsPageLayout } from "@/components/settings/settings-page-layout"
import { ActivityLog } from "@/components/settings/activity-log"

export default function ActivityPage() {
  return (
    <SettingsPageLayout
      icon={Activity}
      title="Activity Log"
      description="View your account activity, generations, and security events."
    >
      <ActivityLog />
    </SettingsPageLayout>
  )
}
