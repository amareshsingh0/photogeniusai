"use client"

import { useState, useEffect, useRef } from "react"
import { usePathname, useRouter } from "next/navigation"
import Link from "next/link"
import {
  Sparkles, Image, Globe, Menu, X, LogOut, User, Home, Users,
  ChevronDown, Bell, SlidersHorizontal, Shield, Key, CreditCard,
  Receipt, Activity, Plus, CalendarDays, Palette, Zap, Share2,
} from "lucide-react"

const navigation = [
  { name: "Home",       href: "/dashboard",      icon: Home },
  { name: "Create",     href: "/generate",        icon: Sparkles, accent: true },
  { name: "Gallery",    href: "/gallery",         icon: Image },
  { name: "Calendar",   href: "/calendar",        icon: CalendarDays },
  { name: "Batch",      href: "/batch",           icon: Zap },
  { name: "Identities", href: "/identity-vault",  icon: Users },
  { name: "Explore",    href: "/explore",         icon: Globe },
]

const userMenuItems = [
  { name: "Profile",             href: "/settings/profile",             icon: User },
  { name: "Brand Kit",           href: "/settings/brand-kit",           icon: Palette },
  { name: "Integrations",        href: "/settings/integrations",        icon: Share2 },
  { name: "Notifications",       href: "/settings/notifications",       icon: Bell },
  { name: "Generation Defaults", href: "/settings/generation-defaults", icon: SlidersHorizontal },
  { name: "Privacy & Consent",   href: "/settings/privacy",             icon: Shield },
  { name: "API Keys",            href: "/settings/api-keys",            icon: Key },
  { name: "Pricing",             href: "/pricing",                      icon: CreditCard },
  { name: "Billing",             href: "/settings/billing",             icon: Receipt },
  { name: "Activity Log",        href: "/settings/activity",            icon: Activity },
]

function UserMenu() {
  const router   = useRouter()
  const [open, setOpen] = useState(false)
  const [devUser, setDevUser] = useState<{ name: string; email: string } | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const stored = localStorage.getItem("dev_user")
    if (stored) setDevUser(JSON.parse(stored))
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const handleLogout = () => {
    document.cookie = "dev_session=; path=/; max-age=0"
    localStorage.removeItem("dev_user")
    router.push("/login")
  }

  const initials = devUser?.name
    ? devUser.name.split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase()
    : "U"

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors group"
      >
        {/* Avatar */}
        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shrink-0 text-xs font-bold text-white shadow-lg">
          {initials}
        </div>
        <div className="flex-1 text-left min-w-0">
          <p className="text-sm font-medium text-white truncate">{devUser?.name || "User"}</p>
          <p className="text-[10px] text-white/30 truncate">{devUser?.email || "Free plan"}</p>
        </div>
        <ChevronDown className={`h-3.5 w-3.5 text-white/30 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Dropdown — opens upward */}
      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-2 bg-[#13131f] border border-white/10 rounded-2xl shadow-2xl overflow-hidden z-50 py-1">
          {userMenuItems.map((item) => {
            const Icon = item.icon
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setOpen(false)}
                className="flex items-center gap-3 px-4 py-2 text-sm text-white/50 hover:bg-white/5 hover:text-white transition-colors"
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.name}
              </Link>
            )
          })}
          <div className="border-t border-white/8 mt-1 pt-1">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-400/80 hover:bg-red-500/10 hover:text-red-400 transition-colors"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              Log Out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function DashboardLayoutClient({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pathname = usePathname()

  return (
    <div className="min-h-screen" style={{ background: "#07070f" }}>

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ──────────────────────────────────────────────────────── */}
      <aside
        className={[
          "fixed inset-y-0 left-0 z-50 w-56 flex flex-col transform transition-transform duration-200 lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        ].join(" ")}
        style={{
          background: "linear-gradient(180deg, #0d0d1a 0%, #0a0a16 100%)",
          borderRight: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        {/* Logo */}
        <div className="flex items-center h-14 px-5 shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="h-7 w-7 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)" }}>
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <div className="leading-tight">
              <p className="text-sm font-bold text-white tracking-tight">PhotoGenius</p>
              <p className="text-[9px] text-white/30 tracking-wider uppercase">AI Studio</p>
            </div>
          </Link>
          <button className="lg:hidden ml-auto text-white/30 hover:text-white" onClick={() => setSidebarOpen(false)}>
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href)
            const Icon = item.icon

            if (item.accent) {
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-semibold text-white transition-all my-1"
                  style={{
                    background: isActive
                      ? "linear-gradient(135deg, rgba(124,58,237,0.35), rgba(79,70,229,0.35))"
                      : "linear-gradient(135deg, rgba(124,58,237,0.15), rgba(79,70,229,0.15))",
                    border: "1px solid rgba(124,58,237,0.35)",
                  }}
                >
                  <Icon className="h-4 w-4 shrink-0 text-purple-400" />
                  {item.name}
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-purple-400 opacity-70" />
                </Link>
              )
            }

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={[
                  "flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm font-medium transition-all",
                  isActive
                    ? "bg-white/8 text-white"
                    : "text-white/40 hover:bg-white/5 hover:text-white/80",
                ].join(" ")}
              >
                <Icon className={`h-4 w-4 shrink-0 ${isActive ? "text-purple-400" : ""}`} />
                {item.name}
                {isActive && <span className="ml-auto w-1 h-4 rounded-full bg-purple-500/60" />}
              </Link>
            )
          })}
        </nav>

        {/* Upgrade nudge */}
        <div className="mx-3 mb-3 p-3 rounded-xl" style={{ background: "rgba(124,58,237,0.08)", border: "1px solid rgba(124,58,237,0.15)" }}>
          <p className="text-xs font-semibold text-white/80">Free Plan</p>
          <p className="text-[10px] text-white/30 mt-0.5">10 / 50 images used</p>
          <div className="mt-2 h-1 rounded-full bg-white/5 overflow-hidden">
            <div className="h-full w-[20%] rounded-full" style={{ background: "linear-gradient(90deg, #7c3aed, #4f46e5)" }} />
          </div>
          <Link href="/pricing" className="mt-2 block text-[10px] text-purple-400 hover:text-purple-300 font-medium transition-colors">
            Upgrade to Pro →
          </Link>
        </div>

        {/* User */}
        <div className="px-2 pb-3 shrink-0" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="pt-3">
            <UserMenu />
          </div>
        </div>
      </aside>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <div className="lg:pl-56">
        {/* Top bar */}
        <header className="sticky top-0 z-40 flex items-center h-14 px-4 lg:px-6"
          style={{ background: "rgba(7,7,15,0.85)", backdropFilter: "blur(12px)", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <button
            className="lg:hidden mr-3 text-white/40 hover:text-white transition-colors"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Breadcrumb */}
          <div className="flex-1 hidden lg:block">
            <p className="text-sm font-semibold text-white/80">
              {navigation.find(n => n.href !== "/dashboard" && pathname.startsWith(n.href))?.name
                || navigation.find(n => n.href === "/dashboard" && pathname === "/dashboard")?.name
                || "Dashboard"}
            </p>
          </div>

          {/* CTA */}
          <div className="ml-auto">
            <Link
              href="/generate"
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-semibold text-white transition-all hover:opacity-90"
              style={{ background: "linear-gradient(135deg, #7c3aed, #4f46e5)", boxShadow: "0 0 20px rgba(124,58,237,0.3)" }}
            >
              <Plus className="h-3.5 w-3.5" />
              Create
            </Link>
          </div>
        </header>

        {/* Page */}
        <main className="p-4 lg:p-6 min-h-[calc(100vh-3.5rem)]">
          {children}
        </main>
      </div>
    </div>
  )
}
