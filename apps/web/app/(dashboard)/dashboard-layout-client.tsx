"use client"

import { useState, useEffect, useRef } from "react"
import { usePathname, useRouter } from "next/navigation"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Sparkles,
  Image,
  Globe,
  Menu,
  X,
  LogOut,
  User,
  Home,
  Users,
  ChevronRight,
  Bell,
  SlidersHorizontal,
  Shield,
  Key,
  CreditCard,
  Receipt,
  Activity,
  Plus,
} from "lucide-react"

const navigation = [
  { name: "Home", href: "/dashboard", icon: Home },
  { name: "Create", href: "/generate", icon: Sparkles, highlight: true },
  { name: "Gallery", href: "/gallery", icon: Image },
  { name: "Identities", href: "/identity-vault", icon: Users },
  { name: "Explore", href: "/explore", icon: Globe },
]

const userMenuItems = [
  { name: "Profile", href: "/settings/profile", icon: User },
  { name: "Notifications", href: "/settings/notifications", icon: Bell },
  { name: "Generation Defaults", href: "/settings/generation-defaults", icon: SlidersHorizontal },
  { name: "Privacy & Consent", href: "/settings/privacy", icon: Shield },
  { name: "API Keys", href: "/settings/api-keys", icon: Key },
  { name: "Pricing", href: "/pricing", icon: CreditCard },
  { name: "Billing", href: "/settings/billing", icon: Receipt },
  { name: "Activity Log", href: "/settings/activity", icon: Activity },
]

function UserMenu() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [devUser, setDevUser] = useState<{ name: string; email: string } | null>(null)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const stored = localStorage.getItem("dev_user")
    if (stored) setDevUser(JSON.parse(stored))
  }, [])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleLogout = () => {
    document.cookie = "dev_session=; path=/; max-age=0"
    localStorage.removeItem("dev_user")
    router.push("/login")
  }

  return (
    <div ref={ref} className="relative">
      {/* User row - always visible */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-muted/50 transition-colors group"
      >
        <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center ring-1 ring-border/50 shrink-0">
          <User className="h-4 w-4 text-primary" />
        </div>
        <span className="text-sm font-medium text-foreground flex-1 text-left truncate">
          {devUser?.name || "User"}
        </span>
        <ChevronRight className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-90")} />
      </button>

      {/* Dropdown - opens upward */}
      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-card border border-border/50 rounded-xl shadow-xl overflow-hidden z-50">
          {userMenuItems.map((item) => {
            const Icon = item.icon
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
              >
                <Icon className="h-4 w-4 shrink-0" />
                {item.name}
              </Link>
            )
          })}
          <div className="border-t border-border/50">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
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

export default function DashboardLayoutClient({
  children,
}: {
  children: React.ReactNode
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pathname = usePathname()

  const currentPage = navigation.find(n => pathname.startsWith(n.href) && n.href !== "/dashboard")
    || navigation.find(n => n.href === "/dashboard")

  const pageTitle = currentPage?.name || "Dashboard"

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-60 bg-card border-r border-border/50 transform transition-transform duration-150 lg:translate-x-0 flex flex-col",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-border/50 shrink-0">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="h-7 w-7 rounded-lg bg-primary/20 flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
            </div>
            <div>
              <span className="font-semibold text-foreground tracking-tight text-sm">PhotoGenius</span>
              <span className="text-[10px] text-muted-foreground/60 ml-1">AI Studio</span>
            </div>
          </Link>
          <Button variant="ghost" size="icon" className="lg:hidden h-8 w-8" onClick={() => setSidebarOpen(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href)
            const Icon = item.icon

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all",
                  isActive
                    ? "bg-primary/10 text-primary border border-primary/20"
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground border border-transparent"
                )}
              >
                <Icon className={cn("h-4 w-4 shrink-0", isActive && "text-primary")} />
                <span>{item.name}</span>
                {item.highlight && isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary" />
                )}
              </Link>
            )
          })}
        </nav>

        {/* User menu at bottom */}
        <div className="p-2 border-t border-border/50 shrink-0">
          <UserMenu />
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-60">
        {/* Top header */}
        <header className="sticky top-0 z-40 bg-background border-b border-border/50">
          <div className="flex items-center justify-between h-14 px-4 lg:px-6">
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden h-8 w-8 -ml-1"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-4 w-4" />
            </Button>

            <div className="hidden lg:block">
              <p className="text-sm font-semibold text-foreground">{pageTitle}</p>
              <p className="text-xs text-muted-foreground">Create stunning AI-generated images</p>
            </div>

            <div className="flex items-center gap-3 ml-auto">
              <Link href="/generate">
                <Button size="sm" className="gap-1.5 rounded-lg bg-primary hover:bg-primary/90 text-white shadow-sm">
                  <Plus className="h-3.5 w-3.5" />
                  Create Image
                </Button>
              </Link>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6 min-h-[calc(100vh-3.5rem)]">
          {children}
        </main>
      </div>
    </div>
  )
}
