"use client"

import { NotificationSettings } from "@/components/settings/notification-settings"

export default function NotificationsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Notifications</h1>
        <p className="mt-1 text-sm text-white/50">Configure how and when you receive email and push notifications.</p>
      </div>
      <NotificationSettings />
    </div>
  )
}
