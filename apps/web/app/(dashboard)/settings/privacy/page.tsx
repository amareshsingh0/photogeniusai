"use client"

import { PrivacySettings } from "@/components/settings/privacy-settings"

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Privacy & Consent</h1>
        <p className="mt-1 text-sm text-white/50">Control your privacy settings, data consent, and how we use your information.</p>
      </div>
      <PrivacySettings />
    </div>
  )
}
