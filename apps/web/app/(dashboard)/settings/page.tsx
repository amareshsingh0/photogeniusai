"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Settings as SettingsIcon,
  User,
  Bell,
  Palette,
  Shield,
  Key,
  CreditCard,
  Activity,
} from "lucide-react"
import { ProfileSettings } from "@/components/settings/profile-settings"
import { NotificationSettings } from "@/components/settings/notification-settings"
import { GenerationDefaults } from "@/components/settings/generation-defaults"
import { PrivacySettings } from "@/components/settings/privacy-settings"
import { ApiKeysSettings } from "@/components/settings/api-keys-settings"
import { BillingSettings } from "@/components/settings/billing-settings"
import { ActivityLog } from "@/components/settings/activity-log"

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("profile")

  const tabs = [
    {
      id: "profile",
      label: "Profile",
      icon: User,
      component: ProfileSettings,
    },
    {
      id: "notifications",
      label: "Notifications",
      icon: Bell,
      component: NotificationSettings,
    },
    {
      id: "generation",
      label: "Generation Defaults",
      icon: Palette,
      component: GenerationDefaults,
    },
    {
      id: "privacy",
      label: "Privacy & Consent",
      icon: Shield,
      component: PrivacySettings,
    },
    {
      id: "api-keys",
      label: "API Keys",
      icon: Key,
      component: ApiKeysSettings,
    },
    {
      id: "billing",
      label: "Billing",
      icon: CreditCard,
      component: BillingSettings,
    },
    {
      id: "activity",
      label: "Activity Log",
      icon: Activity,
      component: ActivityLog,
    },
  ]

  return (
    <div className="max-w-6xl mx-auto space-y-4 sm:space-y-6 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center space-x-2 sm:space-x-3">
          <SettingsIcon className="h-6 w-6 sm:h-8 sm:w-8 text-primary" />
          <span>Settings</span>
        </h1>
        <p className="mt-2 text-sm sm:text-base text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-2 w-full overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <TabsTrigger
                key={tab.id}
                value={tab.id}
                className="flex items-center justify-center space-x-1 sm:space-x-2 text-xs sm:text-sm px-2 sm:px-4"
              >
                <Icon className="h-3 w-3 sm:h-4 sm:w-4" />
                <span className="hidden sm:inline">{tab.label}</span>
                <span className="sm:hidden">{tab.label.split(' ')[0]}</span>
              </TabsTrigger>
            )
          })}
        </TabsList>

        {tabs.map((tab) => {
          const Component = tab.component
          return (
            <TabsContent key={tab.id} value={tab.id} className="mt-6">
              <Component />
            </TabsContent>
          )
        })}
      </Tabs>
    </div>
  )
}
