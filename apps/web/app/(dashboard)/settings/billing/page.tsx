"use client"

import { CreditCard } from "lucide-react"
import { SettingsPageLayout } from "@/components/settings/settings-page-layout"
import { BillingSettings } from "@/components/settings/billing-settings"

export default function BillingPage() {
  return (
    <SettingsPageLayout
      icon={CreditCard}
      title="Billing"
      description="Manage your subscription, payment methods, and billing history."
    >
      <BillingSettings />
    </SettingsPageLayout>
  )
}
