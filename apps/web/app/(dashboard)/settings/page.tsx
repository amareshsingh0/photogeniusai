"use client"

import Link from "next/link"
import {
  Bell,
  Palette,
  Shield,
  CreditCard,
  Activity,
  Sliders,
  Plug,
  User,
  ChevronRight,
} from "lucide-react"

const SECTIONS = [
  { href: "/account", icon: User, title: "Account", desc: "Profile, plan, API keys, security & notifications." },
  { href: "/settings/notifications", icon: Bell, title: "Notifications", desc: "Email and push notification preferences." },
  { href: "/settings/generation-defaults", icon: Palette, title: "Generation Defaults", desc: "Default style, aspect ratio and quality." },
  { href: "/settings/brand-kit", icon: Sliders, title: "Brand Kit", desc: "Colors, fonts, tone and logo for every generation." },
  { href: "/settings/integrations", icon: Plug, title: "Integrations", desc: "Connect Instagram and LinkedIn." },
  { href: "/settings/privacy", icon: Shield, title: "Privacy & Consent", desc: "Data consent and privacy controls." },
  { href: "/settings/billing", icon: CreditCard, title: "Billing", desc: "Subscription, payment methods and history." },
  { href: "/settings/activity", icon: Activity, title: "Activity Log", desc: "Account activity and security events." },
]

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Settings</h1>
        <p className="mt-1 text-sm text-white/50">Manage your account settings and preferences.</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {SECTIONS.map((s) => {
          const Icon = s.icon
          return (
            <Link
              key={s.href}
              href={s.href}
              className="glass-panel group flex items-start gap-3 rounded-2xl p-4 transition hover:-translate-y-0.5"
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/5 text-white/70">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-display text-lg tracking-tight">{s.title}</h3>
                  <ChevronRight className="h-4 w-4 text-white/30 transition group-hover:text-white/60" />
                </div>
                <p className="mt-0.5 text-sm text-white/50">{s.desc}</p>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
