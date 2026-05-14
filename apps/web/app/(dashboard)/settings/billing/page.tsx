"use client"

import { BillingSettings } from "@/components/settings/billing-settings"

export default function BillingPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Billing</h1>
        <p className="mt-1 text-sm text-white/50">Manage your subscription, payment methods, and billing history.</p>
      </div>
      <BillingSettings />
    </div>
  )
}
