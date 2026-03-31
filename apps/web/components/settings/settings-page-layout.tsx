"use client"

import { LucideIcon } from "lucide-react"

interface SettingsPageLayoutProps {
  icon: LucideIcon
  title: string
  description: string
  children: React.ReactNode
  iconGradient?: string
}

export function SettingsPageLayout({
  icon: Icon,
  title,
  description,
  children,
  iconGradient = "from-purple-500/20 to-indigo-500/20",
}: SettingsPageLayoutProps) {
  return (
    <div className="max-w-7xl mx-auto space-y-8 px-4 sm:px-6 lg:px-8">
      {/* Hero Section - Dashboard style */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-purple-500/10 via-transparent to-indigo-500/10 border border-white/[0.08] p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-purple-500/20 via-indigo-500/10 to-transparent rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-gradient-to-tr from-indigo-500/20 via-purple-500/10 to-transparent rounded-full blur-3xl" />
        <div className="relative flex items-start gap-6">
          <div className={`flex shrink-0 items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br ${iconGradient} border border-white/[0.08]`}>
            <Icon className="h-7 w-7 text-purple-400" strokeWidth={2} />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight mb-2">
              {title}
            </h1>
            <p className="text-sm sm:text-base text-zinc-400 max-w-2xl">
              {description}
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="space-y-6">
        {children}
      </div>
    </div>
  )
}
