"use client"

import { ActivityLog } from "@/components/settings/activity-log"

export default function ActivityPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Activity Log</h1>
        <p className="mt-1 text-sm text-white/50">View your account activity, generations, and security events.</p>
      </div>
      <ActivityLog />
    </div>
  )
}
