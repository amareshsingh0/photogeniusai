"use client"

import { useState, useEffect, useRef } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import {
  Sparkles,
  Image as ImageIcon,
  Users,
  ArrowRight,
  Zap,
  Clock,
} from "lucide-react"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

interface UserStats {
  credits: number
  generationsCount: number
  identitiesCount: number
}

interface Activity {
  type: "generation" | "identity"
  text: string
  time: string
  dateKey: string
}

const INSPIRATION_CARDS = [
  { id: "cyberpunk", label: "Cyberpunk", gradient: "from-cyan-500/30 to-violet-500/30" },
  { id: "studio", label: "Studio Portrait", gradient: "from-amber-500/30 to-orange-500/30" },
  { id: "fantasy", label: "Fantasy", gradient: "from-purple-500/30 to-pink-500/30" },
  { id: "architecture", label: "Architecture", gradient: "from-slate-500/30 to-blue-500/30" },
  { id: "anime", label: "Anime", gradient: "from-rose-500/30 to-fuchsia-500/30" },
]

const quickActions = [
  { title: "Create AI Photo", description: "Generate stunning AI portraits", href: "/generate", icon: Sparkles, cardClass: "action-card-create" },
  { title: "Add Identity", description: "Train AI on your face", href: "/identity-vault", icon: Users, cardClass: "action-card-identity" },
  { title: "View Gallery", description: "Browse your creations", href: "/gallery", icon: ImageIcon, cardClass: "action-card-gallery" },
]

function useCountUp(value: number, enabled: boolean, duration = 800) {
  const [display, setDisplay] = useState(0)
  const prevRef = useRef(0)
  useEffect(() => {
    if (!enabled) return
    const start = prevRef.current
    const end = value
    if (end === start) return
    const startTime = performance.now()
    const tick = (now: number) => {
      const t = Math.min((now - startTime) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 2)
      setDisplay(Math.round(start + (end - start) * eased))
      if (t < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
    prevRef.current = end
  }, [value, enabled, duration])
  return display
}

function getTimeGreeting() {
  const h = new Date().getHours()
  if (h < 12) return "Good Morning"
  if (h < 17) return "Good Afternoon"
  return "Good Evening"
}

function formatTimeAgo(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)
  if (diffMins < 1) return "Just now"
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function groupActivityByDay(activity: Activity[]): { label: string; items: Activity[] }[] {
  const today = new Date().toDateString()
  const yesterday = new Date(Date.now() - 864e5).toDateString()
  const byDay = new Map<string, Activity[]>()
  activity.forEach((a) => {
    const key = a.dateKey
    if (!byDay.has(key)) byDay.set(key, [])
    byDay.get(key)!.push(a)
  })
  const groups: { label: string; items: Activity[] }[] = []
  if (byDay.has(today)) groups.push({ label: "Today", items: byDay.get(today)! })
  if (byDay.has(yesterday)) groups.push({ label: "Yesterday", items: byDay.get(yesterday)! })
  byDay.forEach((items, key) => {
    if (key !== today && key !== yesterday) groups.push({ label: new Date(key).toLocaleDateString(), items })
  })
  return groups
}

function DashboardContent({ firstName: firstNameProp }: { firstName: string }) {
  const [firstName, setFirstName] = useState(firstNameProp || "there")
  const [stats, setStats] = useState<UserStats | null>(null)
  const [activity, setActivity] = useState<Activity[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [celebratedFirst, setCelebratedFirst] = useState(false)
  const prevGenerationsRef = useRef<number | null>(null)
  const { toast } = useToast()

  const creditsDisplay = useCountUp(stats?.credits ?? 0, !isLoading)
  const generatedDisplay = useCountUp(stats?.generationsCount ?? 0, !isLoading)
  const identitiesDisplay = useCountUp(stats?.identitiesCount ?? 0, !isLoading)

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("dev_user") ?? "{}")
      if (stored?.name) setFirstName(stored.name.split(" ")[0])
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    async function fetchData() {
      try {
        const statsRes = await fetch("/api/user/stats")
        if (statsRes.ok) {
          const statsData = await statsRes.json()
          setStats(statsData)
        }
        const gensRes = await fetch("/api/generations")
        if (gensRes.ok) {
          const gensData = await gensRes.json()
          const list = Array.isArray(gensData) ? gensData : []
          const recentActivity: Activity[] = list.slice(0, 8).map((gen: { prompt?: string; mode?: string; createdAt?: string }) => {
            const d = new Date(gen.createdAt || Date.now())
            return {
              type: "generation" as const,
              text: `${(gen.mode || "Image").replace(/^./, (c) => c.toUpperCase())} generated`,
              time: formatTimeAgo(d),
              dateKey: d.toDateString(),
            }
          })
          setActivity(recentActivity)
        }
      } catch (error) {
        console.error("Failed to fetch dashboard data:", error)
      } finally {
        setIsLoading(false)
      }
    }
    fetchData()
  }, [])

  // Phase 7: First creation celebration
  useEffect(() => {
    if (isLoading || stats == null) return
    const count = stats.generationsCount
    if (prevGenerationsRef.current === 0 && count >= 1 && !celebratedFirst) {
      setCelebratedFirst(true)
      toast({ title: "✦ Your first creation!", description: "You’re on your way." })
    }
    prevGenerationsRef.current = count
  }, [isLoading, stats, celebratedFirst, toast])

  const activityGroups = groupActivityByDay(activity)

  return (
    <div className="dashboard-studio min-h-full">
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {/* Phase 5: Greeting — left welcome, right time, subtitle, shimmer */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="relative"
        >
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(79,140,255,0.04),transparent)] pointer-events-none rounded-xl" />
          <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <h1 className="dashboard-welcome text-foreground">
              {firstName ? (
                <>Welcome back, <span className="gradient-text">{firstName}</span> ✦</>
              ) : (
                "Welcome back ✦"
              )}
            </h1>
            <p className="dashboard-body text-sm sm:text-base">✦ {getTimeGreeting()}</p>
          </div>
          <p className="dashboard-body text-sm mt-1">Create something extraordinary today</p>
          <div className="greeting-shimmer mt-4 rounded-full" />
        </motion.div>

        {/* Phase 2: Stats cards — amber / blue / purple, count-up, CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05 }}
          className="grid grid-cols-3 gap-4"
        >
          <Link href="/pricing" className="stat-card-amber rounded-2xl border block btn-press">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-2 rounded-xl bg-amber-500/20">
                <Zap className="h-5 w-5 text-amber-400" />
              </div>
            </div>
            {isLoading ? (
              <div className="h-9 w-16 bg-white/10 rounded animate-pulse" />
            ) : (
              <p className={cn("dashboard-stat-num count-up", (stats?.credits ?? 0) === 0 && "zero")}>
                {creditsDisplay}
              </p>
            )}
            <p className="dashboard-body text-xs mt-0.5">Credits Remaining</p>
            <p className="text-xs text-amber-400/90 mt-3 font-medium">Buy Credits →</p>
          </Link>

          <Link
            href="/gallery"
            className={cn(
              "stat-card-blue rounded-2xl border block btn-press",
              celebratedFirst && (stats?.generationsCount ?? 0) >= 1 && "pulse-celebrate"
            )}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="p-2 rounded-xl bg-blue-500/20">
                <ImageIcon className="h-5 w-5 text-blue-400" />
              </div>
            </div>
            {isLoading ? (
              <div className="h-9 w-16 bg-white/10 rounded animate-pulse" />
            ) : (
              <p className={cn("dashboard-stat-num count-up", (stats?.generationsCount ?? 0) === 0 && "zero")}>
                {generatedDisplay}
              </p>
            )}
            <p className="dashboard-body text-xs mt-0.5">Generated All time</p>
            <p className="text-xs text-blue-400/90 mt-3 font-medium">View All →</p>
          </Link>

          <Link href="/identity-vault" className="stat-card-purple rounded-2xl border block btn-press">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-2 rounded-xl bg-purple-500/20">
                <Users className="h-5 w-5 text-purple-400" />
              </div>
            </div>
            {isLoading ? (
              <div className="h-9 w-16 bg-white/10 rounded animate-pulse" />
            ) : (
              <p className={cn("dashboard-stat-num count-up", (stats?.identitiesCount ?? 0) === 0 && "zero")}>
                {identitiesDisplay}
              </p>
            )}
            <p className="dashboard-body text-xs mt-0.5">Identities Active</p>
            <p className="text-xs text-purple-400/90 mt-3 font-medium">Add New →</p>
          </Link>
        </motion.div>

        {/* Phase 3: Inspiration strip — CTA banner replaced */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08 }}
        >
          <p className="text-sm font-semibold text-foreground mb-3">✦ Get Inspired</p>
          <div className="overflow-x-auto no-scrollbar flex gap-4 pb-2">
            {INSPIRATION_CARDS.map((card) => (
              <Link
                key={card.id}
                href={`/generate?style=${card.id}`}
                className="shrink-0 w-32 sm:w-36 rounded-xl overflow-hidden border border-white/10 bg-white/[0.03] hover:bg-white/[0.06] hover:border-white/20 transition-all group"
              >
                <div className={cn("h-24 bg-gradient-to-br", card.gradient)} />
                <p className="p-2.5 text-xs font-medium text-foreground group-hover:text-primary transition-colors truncate">
                  {card.label}
                </p>
              </Link>
            ))}
            <Link
              href="/generate"
              className="shrink-0 w-32 sm:w-36 rounded-xl border border-dashed border-white/20 flex items-center justify-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:border-primary/40 transition-all"
            >
              More <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </motion.div>

        {/* Phase 4: Quick action cards — gradients, big icon, hover */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-6"
        >
          {quickActions.map((action) => {
            const Icon = action.icon
            return (
              <Link key={action.title} href={action.href}>
                <motion.div
                  whileHover={{ y: -4 }}
                  className={cn(
                    "group rounded-2xl p-6 transition-all duration-200 h-full flex flex-col items-center text-center border",
                    action.cardClass
                  )}
                >
                  <div className="w-14 h-14 rounded-2xl bg-white/10 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                    <Icon className="h-7 w-7 text-white" />
                  </div>
                  <h3 className="font-semibold text-foreground mb-1">{action.title}</h3>
                  <p className="dashboard-body text-xs mb-3">{action.description}</p>
                  <span className="inline-flex items-center gap-1 text-sm font-medium text-white/90 group-hover:gap-2 transition-[gap]">
                    Go <ArrowRight className="h-4 w-4" />
                  </span>
                </motion.div>
              </Link>
            )
          })}
        </motion.div>

        {/* Phase 6: Your Creative Journey — empty state or timeline */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="space-y-4"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Your Creative Journey</h2>
            <Link href="/gallery">
              <Button variant="ghost" size="sm" className="text-xs text-muted-foreground hover:text-foreground h-8">
                View all
                <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-14 rounded-xl bg-white/5 animate-pulse" />
              ))}
            </div>
          ) : activity.length === 0 ? (
            <div className="text-center py-12 rounded-2xl border border-white/[0.06] bg-white/[0.02]">
              <p className="text-foreground font-medium mb-2">✦ Your canvas awaits</p>
              <div className="flex flex-wrap justify-center gap-2 mb-4">
                {["Realistic", "Cinematic", "Anime"].map((s) => (
                  <span
                    key={s}
                    className="px-3 py-1.5 rounded-full text-xs border border-white/10 bg-white/5 text-muted-foreground"
                  >
                    {s}
                  </span>
                ))}
              </div>
              <p className="dashboard-body text-xs mb-5">See what 10,000+ creators made today</p>
              <Link href="/generate">
                <Button className="rounded-xl bg-gradient-to-r from-primary/90 to-purple-500/90 text-white hover:opacity-95">
                  <Sparkles className="mr-2 h-4 w-4" />
                  Create Your First Image
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-6">
              {activityGroups.map((group) => (
                <div key={group.label}>
                  <p className="text-xs font-medium text-muted-foreground mb-2">{group.label}</p>
                  <div className="space-y-1">
                    {group.items.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 p-3 rounded-xl border border-white/[0.06] bg-white/[0.02]"
                      >
                        <div className="p-2 rounded-lg bg-white/5">
                          {item.type === "generation" ? (
                            <Sparkles className="h-4 w-4 text-primary" />
                          ) : (
                            <Users className="h-4 w-4 text-purple-400" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-foreground truncate">✦ {item.text}</p>
                        </div>
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap">
                          <Clock className="h-3.5 w-3.5" />
                          {item.time}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  return <DashboardContent firstName="" />
}
