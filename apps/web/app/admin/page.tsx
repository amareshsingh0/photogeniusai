"use client";

import { useState, useEffect } from "react";
import {
  Users,
  Image as ImageIcon,
  Settings,
  BarChart3,
  Shield,
  RefreshCw,
  Search,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Edit,
  X,
  LogOut,
  Sliders,
  Cpu,
  DollarSign,
  Clock,
  Star,
} from "lucide-react";
import { cn } from "@/lib/utils";
import FeatureConfigPanel from "@/components/admin/feature-config-panel";
import ModelRatingsModal from "@/components/admin/model-ratings-modal";
import GenerationsTable from "@/components/admin/generations-table";

type Tab = "overview" | "users" | "generations" | "models" | "settings" | "config";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  credits: number;
  createdAt: string;
  _count: { generations: number };
}

interface Generation {
  id: string;
  prompt: string;
  quality: string;
  bucket: string;
  modelUsed: string;
  credits: number;
  createdAt: string;
  user: {
    email: string;
    name: string;
  };
}

interface Analytics {
  overview: {
    totalUsers: number;
    totalGenerations: number;
    activeUsers: number;
    totalCreditsUsed: number;
    avgGenerationsPerUser: string;
    dailyAverage: string;
  };
  generations: {
    today: number;
    week: number;
    month: number;
  };
  breakdown: {
    byTier: Array<{ tier: string; count: number }>;
    byBucket: Array<{ bucket: string; count: number }>;
  };
}

interface ModelConfig {
  id: string;
  modelId: string;
  provider: string;
  displayName: string;
  buckets: string[];
  isActive: boolean;
  isTestingEnabled: boolean;
  totalGenerations: number;
  avgRating: number | null;
  avgCost: number | null;
  avgLatency: number | null;
  costPerImage: number;
  createdAt: string;
  updatedAt: string;
}

export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Settings-tab restart banner. Toggles no longer auto-restart; we mark
  // pending=true on each save so the banner appears, then admin clicks
  // Restart once to apply the whole batch.
  const [settingsRestartPending, setSettingsRestartPending] = useState(false);
  const [settingsRestarting, setSettingsRestarting] = useState(false);

  // Users state
  const [users, setUsers] = useState<User[]>([]);
  const [usersPage, setUsersPage] = useState(1);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersSearch, setUsersSearch] = useState("");

  // Generations state
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [generationsPage, setGenerationsPage] = useState(1);
  const [generationsTotal, setGenerationsTotal] = useState(0);

  // Analytics state
  const [analytics, setAnalytics] = useState<Analytics | null>(null);

  // Settings state
  const [settings, setSettings] = useState<any>(null);

  // Models state
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsFilter, setModelsFilter] = useState<"all" | "active" | "inactive">("all");
  const [viewingRatingsModel, setViewingRatingsModel] = useState<{ id: string; name: string } | null>(null);

  // Edit user modal
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ name: "", email: "", role: "", credits: 0 });

  // Logout function
  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      window.location.href = "/login";
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

  // Fetch data based on active tab
  useEffect(() => {
    if (activeTab === "overview") {
      fetchAnalytics();
    } else if (activeTab === "users") {
      fetchUsers();
    } else if (activeTab === "generations") {
      fetchGenerations();
    } else if (activeTab === "models") {
      fetchModels();
    } else if (activeTab === "settings") {
      fetchSettings();
    }
  }, [activeTab, usersPage, usersSearch, generationsPage]);

  const fetchAnalytics = async () => {
    setLoading(true);
    setError("");
    try {
      // Use Next.js API route (not Python API)
      const res = await fetch("/api/admin/analytics", {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to fetch analytics");
      const data = await res.json();
      setAnalytics(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        page: usersPage.toString(),
        limit: "50",
        ...(usersSearch && { search: usersSearch }),
      });
      const res = await fetch(`/api/admin/users?${params}`);
      if (!res.ok) throw new Error("Failed to fetch users");
      const data = await res.json();
      setUsers(data.users);
      setUsersTotal(data.pagination.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchGenerations = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        page: generationsPage.toString(),
        limit: "50",
      });
      const res = await fetch(`/api/admin/generations?${params}`);
      if (!res.ok) throw new Error("Failed to fetch generations");
      const data = await res.json();
      setGenerations(data.generations);
      setGenerationsTotal(data.pagination.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchSettings = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/admin/settings");
      if (!res.ok) throw new Error("Failed to fetch settings");
      const data = await res.json();
      setSettings(data.settings);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateUser = async () => {
    if (!editingUser) return;

    try {
      const res = await fetch("/api/admin/users", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: editingUser.id,
          updates: editForm,
        }),
      });

      if (!res.ok) throw new Error("Failed to update user");

      setEditingUser(null);
      fetchUsers();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!confirm("Are you sure you want to delete this user?")) return;

    try {
      const res = await fetch(`/api/admin/users?userId=${userId}`, {
        method: "DELETE",
      });

      if (!res.ok) throw new Error("Failed to delete user");

      fetchUsers();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteGeneration = async (generationId: string) => {
    if (!confirm("Are you sure you want to delete this generation?")) return;

    try {
      const res = await fetch(`/api/admin/generations?generationId=${generationId}`, {
        method: "DELETE",
      });

      if (!res.ok) throw new Error("Failed to delete generation");

      fetchGenerations();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleToggleSetting = async (category: string, key: string, currentValue: boolean) => {
    // Setting toggles write to .env and require a process restart to take
    // effect. Auto-restarting on every toggle caused a restart storm during
    // admin sessions (each toggle = 12s downtime). Toggles now save silently
    // and mark `settingsRestartPending=true`; the banner at the top of the
    // Settings tab surfaces a "Restart now" button so admin applies all
    // queued changes in one restart.
    try {
      const res = await fetch("/api/admin/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category,
          key,
          value: currentValue ? "false" : "true",
        }),
      });

      if (!res.ok) throw new Error("Failed to update setting");
      setSettingsRestartPending(true);
      await fetchSettings();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const restartAPIFromSettings = async () => {
    if (!confirm("Restart the API to apply queued setting changes? ~12s downtime.")) {
      return;
    }
    try {
      setSettingsRestarting(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/config/restart`, { method: "POST" });
      if (!res.ok) throw new Error(`Restart failed: ${await res.text()}`);
      setSettingsRestartPending(false);
      // Give PM2 a few seconds to come back before refreshing
      setTimeout(() => fetchSettings(), 4000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSettingsRestarting(false);
    }
  };

  const fetchModels = async (background = false) => {
    if (!background) setModelsLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/models`);
      if (!res.ok) throw new Error("Failed to fetch models");
      const data = await res.json();
      setModels(data.models);
    } catch (err: any) {
      setError(err.message);
    } finally {
      if (!background) setModelsLoading(false);
    }
  };

  const handleToggleModel = async (modelId: string, field: "isActive" | "isTestingEnabled", currentValue: boolean) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/models/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          modelId,
          [field]: !currentValue,
        }),
      });

      if (!res.ok) throw new Error("Failed to update model");

      // Optimistic update — flip the toggle immediately, refresh in background
      setModels(prev => prev.map(m =>
        m.modelId === modelId ? { ...m, [field]: !currentValue } : m
      ));
      fetchModels(true);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const tabs = [
    { id: "overview" as Tab, label: "Overview", icon: BarChart3 },
    { id: "users" as Tab, label: "Users", icon: Users },
    { id: "generations" as Tab, label: "Generations", icon: ImageIcon },
    { id: "models" as Tab, label: "Models", icon: Cpu },
    { id: "config" as Tab, label: "Feature Config", icon: Sliders },
    { id: "settings" as Tab, label: "Settings", icon: Settings },
  ];

  const filteredModels = models.filter((m) =>
    modelsFilter === "all" ? true : modelsFilter === "active" ? m.isActive : !m.isActive
  );

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-7xl px-4 py-8 pb-24">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 text-white/60" />
            <div>
              <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Admin Dashboard</h1>
              <p className="mt-1 text-sm text-white/50">Full system control & analytics.</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-sm text-red-200 hover:bg-red-500/15 transition"
          >
            <LogOut className="h-3.5 w-3.5" /> Logout
          </button>
        </div>

        {/* Tab strip */}
        <div className="mt-6 flex flex-wrap gap-1.5">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] transition",
                  activeTab === tab.id ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="mt-6 space-y-6">
          {error && (
            <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>
          )}

          {/* Overview Tab */}
          {activeTab === "overview" && analytics && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <StatCard label="TOTAL USERS" value={analytics.overview.totalUsers} />
                <StatCard label="TOTAL GENERATIONS" value={analytics.overview.totalGenerations} />
                <StatCard label="ACTIVE USERS (7D)" value={analytics.overview.activeUsers} />
                <StatCard label="CREDITS USED" value={analytics.overview.totalCreditsUsed} />
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <StatCard label="TODAY" value={analytics.generations.today} />
                <StatCard label="THIS WEEK" value={analytics.generations.week} />
                <StatCard label="THIS MONTH" value={analytics.generations.month} />
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="glass-panel rounded-2xl p-5">
                  <p className="kerned text-white/40 mb-4">BY QUALITY TIER</p>
                  <div className="space-y-3">
                    {analytics.breakdown.byTier.map((item) => (
                      <div key={item.tier} className="flex items-center justify-between text-sm">
                        <span className="capitalize text-white/70">{item.tier}</span>
                        <span className="font-mono text-[11px] text-white/85">{item.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="glass-panel rounded-2xl p-5">
                  <p className="kerned text-white/40 mb-4">BY BUCKET</p>
                  <div className="space-y-3">
                    {analytics.breakdown.byBucket.slice(0, 5).map((item) => (
                      <div key={item.bucket} className="flex items-center justify-between text-sm">
                        <span className="capitalize text-white/70">{item.bucket}</span>
                        <span className="font-mono text-[11px] text-white/85">{item.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Users Tab */}
          {activeTab === "users" && (
            <div className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                  <input
                    type="text"
                    placeholder="Search by email or name…"
                    value={usersSearch}
                    onChange={(e) => {
                      setUsersSearch(e.target.value);
                      setUsersPage(1);
                    }}
                    className="w-full rounded-lg border border-white/10 bg-black/20 py-2 pl-10 pr-3 text-sm outline-none focus:border-white/30"
                  />
                </div>
                <button onClick={fetchUsers} className="rounded-xl border border-white/10 bg-white/5 p-2 hover:bg-white/10 transition">
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>

              <div className="glass-panel overflow-hidden rounded-2xl p-0">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr>
                        <th className="kerned text-white/40 text-left py-2 px-4">User</th>
                        <th className="kerned text-white/40 text-left py-2 px-4">Role</th>
                        <th className="kerned text-white/40 text-left py-2 px-4">Credits</th>
                        <th className="kerned text-white/40 text-left py-2 px-4">Generations</th>
                        <th className="kerned text-white/40 text-left py-2 px-4">Joined</th>
                        <th className="kerned text-white/40 text-left py-2 px-4">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((user) => (
                        <tr key={user.id} className="border-b border-white/5">
                          <td className="py-3 px-4 text-sm">
                            <div className="text-white/85">{user.name}</div>
                            <div className="font-mono text-[10px] text-white/60">{user.email}</div>
                          </td>
                          <td className="py-3 px-4 text-sm">
                            <span className={cn(
                              "rounded-full px-2 py-0.5 text-[10px]",
                              user.role === "ADMIN" || user.role === "SUPER_ADMIN" ? "bg-red-500/15 text-red-200" : "bg-white/5 text-white/70"
                            )}>
                              {user.role || "USER"}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-sm font-mono text-[11px] text-white/85">{user.credits}</td>
                          <td className="py-3 px-4 text-sm font-mono text-[11px] text-white/60">{user._count.generations}</td>
                          <td className="py-3 px-4 text-sm font-mono text-[11px] text-white/60">{new Date(user.createdAt).toLocaleDateString()}</td>
                          <td className="py-3 px-4 text-sm">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => {
                                  setEditingUser(user);
                                  setEditForm({
                                    name: user.name,
                                    email: user.email,
                                    role: user.role || "USER",
                                    credits: user.credits,
                                  });
                                }}
                                className="rounded-lg border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition"
                              >
                                <Edit className="h-3.5 w-3.5" />
                              </button>
                              <button
                                onClick={() => handleDeleteUser(user.id)}
                                className="rounded-lg border border-red-500/30 bg-red-500/10 p-1.5 text-red-200 hover:bg-red-500/15 transition"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center justify-between border-t border-white/5 px-4 py-3">
                  <div className="text-sm text-white/50">Showing {users.length} of {usersTotal} users</div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setUsersPage((p) => Math.max(1, p - 1))}
                      disabled={usersPage === 1}
                      className="rounded-lg border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition disabled:opacity-40"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    <span className="text-sm text-white/70">Page {usersPage}</span>
                    <button
                      onClick={() => setUsersPage((p) => p + 1)}
                      disabled={users.length < 50}
                      className="rounded-lg border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition disabled:opacity-40"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Generations Tab */}
          {activeTab === "generations" && (
            <div className="space-y-6">
              <h2 className="font-display text-2xl tracking-tight">All Generations</h2>
              <div className="glass-panel rounded-2xl p-5">
                <GenerationsTable />
              </div>
            </div>
          )}

          {/* Models Tab */}
          {activeTab === "models" && (
            <div className="space-y-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="font-display text-2xl tracking-tight">Model Registry</h2>
                  <p className="mt-1 text-sm text-white/50">Manage AI models for image generation.</p>
                </div>
                <button
                  onClick={() => fetchModels()}
                  disabled={modelsLoading}
                  className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition disabled:opacity-50"
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", modelsLoading && "animate-spin")} /> Refresh
                </button>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {(["all", "active", "inactive"] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setModelsFilter(filter)}
                    className={cn(
                      "rounded-full px-2.5 py-1 text-[11px] capitalize transition",
                      modelsFilter === filter ? "bg-white text-black" : "bg-white/5 text-white/70 hover:bg-white/10"
                    )}
                  >
                    {filter} ({filter === "all" ? models.length : filter === "active" ? models.filter(m => m.isActive).length : models.filter(m => !m.isActive).length})
                  </button>
                ))}
              </div>

              {modelsLoading ? (
                <div className="flex h-64 items-center justify-center">
                  <RefreshCw className="h-8 w-8 animate-spin text-white/40" />
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  {filteredModels.map((model) => (
                    <div key={model.id} className="glass-panel rounded-2xl p-5 transition hover:-translate-y-0.5">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="mb-2 flex items-center gap-2">
                            <h3 className="font-display text-lg tracking-tight">{model.displayName}</h3>
                            <span className={cn("h-2 w-2 rounded-full", model.isActive ? "bg-emerald-500/80" : "bg-white/40")} />
                          </div>
                          <div className="flex items-center gap-2 text-sm">
                            <span className="rounded-full bg-white/5 px-2 py-0.5 font-mono text-[10px] text-white/70">{model.provider}</span>
                            <span className="text-white/30">·</span>
                            <span className="font-mono text-[10px] text-white/60">{model.modelId}</span>
                          </div>
                        </div>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {model.buckets.map((bucket) => (
                          <span key={bucket} className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-white/60">{bucket}</span>
                        ))}
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-2">
                        <div className="hairline rounded-xl p-3">
                          <div className="mb-1 flex items-center gap-1.5 text-[10px] text-white/40"><DollarSign className="h-3 w-3" /> Cost/Image</div>
                          <div className="font-mono text-sm text-white/85">${model.costPerImage.toFixed(3)}</div>
                        </div>
                        <div className="hairline rounded-xl p-3">
                          <div className="mb-1 flex items-center gap-1.5 text-[10px] text-white/40"><ImageIcon className="h-3 w-3" /> Generations</div>
                          <div className="font-mono text-sm text-white/85">{model.totalGenerations}</div>
                        </div>
                        <div className="hairline rounded-xl p-3">
                          <div className="mb-1 flex items-center gap-1.5 text-[10px] text-white/40"><Star className="h-3 w-3" /> Avg Rating</div>
                          <div className="font-mono text-sm text-white/85">{model.avgRating ? model.avgRating.toFixed(2) : "N/A"}</div>
                        </div>
                        <div className="hairline rounded-xl p-3">
                          <div className="mb-1 flex items-center gap-1.5 text-[10px] text-white/40"><Clock className="h-3 w-3" /> Avg Latency</div>
                          <div className="font-mono text-sm text-white/85">{model.avgLatency ? `${model.avgLatency.toFixed(1)}s` : "N/A"}</div>
                        </div>
                      </div>

                      <div className="mt-4 space-y-3 border-t border-white/5 pt-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-sm text-white/85">Active for production</div>
                            <div className="text-xs text-white/50">{model.isActive ? "Available for generation" : "Disabled"}</div>
                          </div>
                          <Switch on={model.isActive} onClick={() => handleToggleModel(model.modelId, "isActive", model.isActive)} />
                        </div>
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-sm text-white/85">Testing mode</div>
                            <div className="text-xs text-white/50">{model.isTestingEnabled ? "Enabled for parallel testing" : "Not in testing"}</div>
                          </div>
                          <Switch on={model.isTestingEnabled} onClick={() => handleToggleModel(model.modelId, "isTestingEnabled", model.isTestingEnabled)} />
                        </div>
                        <button
                          onClick={() => setViewingRatingsModel({ id: model.modelId, name: model.displayName })}
                          className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-sm hover:bg-white/10 transition"
                        >
                          <Star className="h-3.5 w-3.5" /> View ratings{model.avgRating ? ` (${model.avgRating.toFixed(1)} avg)` : ""}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!modelsLoading && filteredModels.length === 0 && (
                <div className="glass-panel rounded-2xl p-12 text-center text-sm text-white/50">
                  No {modelsFilter !== "all" && modelsFilter} models found
                </div>
              )}
            </div>
          )}

          {/* Feature Config Tab */}
          {activeTab === "config" && (
            <div className="glass-panel rounded-2xl p-5">
              <FeatureConfigPanel />
            </div>
          )}

          {/* Settings Tab */}
          {activeTab === "settings" && settings && (
            <div className="space-y-6">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <h2 className="font-display text-2xl tracking-tight">System Settings</h2>
                {settingsRestartPending && (
                  <button
                    onClick={restartAPIFromSettings}
                    disabled={settingsRestarting}
                    className="rounded-lg border border-amber-400/40 bg-amber-500/15 px-4 py-2 text-sm text-amber-100 hover:bg-amber-500/25 disabled:opacity-50"
                  >
                    {settingsRestarting ? "Restarting…" : "⚠️ Pending changes — Restart API"}
                  </button>
                )}
              </div>

              <div className="glass-panel rounded-2xl p-5">
                <p className="kerned text-white/40 mb-4">GENERATION BACKEND</p>
                <div className="space-y-1">
                  <SettingToggle label="Use Ideogram v3" description="Typography & poster generation" enabled={settings.generation.useIdeogram} onToggle={() => handleToggleSetting("generation", "useIdeogram", settings.generation.useIdeogram)} />
                  <SettingToggle label="Use Gemini Engine" description="Prompt engineering with Gemini 2.5 Flash" enabled={settings.generation.useGeminiEngine} onToggle={() => handleToggleSetting("generation", "useGeminiEngine", settings.generation.useGeminiEngine)} />
                  <SettingToggle label="Use BFL API" description="Flux 2 Max official ($0.060)" enabled={settings.generation.useBfl} onToggle={() => handleToggleSetting("generation", "useBfl", settings.generation.useBfl)} />
                  <SettingToggle label="Use KIE API" description="Flux 2 Pro cheapest ($0.025)" enabled={settings.generation.useKie} onToggle={() => handleToggleSetting("generation", "useKie", settings.generation.useKie)} />
                  <SettingToggle label="Use Pixazo API" description="Flux Schnell cheapest ($0.0012)" enabled={settings.generation.usePixazo} onToggle={() => handleToggleSetting("generation", "usePixazo", settings.generation.usePixazo)} />
                </div>
              </div>

              <div className="glass-panel rounded-2xl p-5">
                <p className="kerned text-white/40 mb-4">QUALITY CRITIC</p>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div>
                    <p className="kerned text-white/40 mb-2">GLOBAL THRESHOLD</p>
                    <input type="number" value={settings.quality.threshold} readOnly className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm text-white/85 outline-none" />
                  </div>
                  <div>
                    <p className="kerned text-white/40 mb-2">DIMENSION FLOOR</p>
                    <input type="number" value={settings.quality.dimensionFloor} readOnly className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm text-white/85 outline-none" />
                  </div>
                  <div>
                    <p className="kerned text-white/40 mb-2">MAX IMAGES</p>
                    <input type="number" value={settings.quality.maxImages} readOnly className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm text-white/85 outline-none" />
                  </div>
                </div>
              </div>

              <div className="glass-panel rounded-2xl p-5">
                <p className="kerned text-white/40 mb-4">API KEYS STATUS</p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <KeyStatus label="Gemini" configured={settings.providers.hasGeminiKey} />
                  <KeyStatus label="FAL" configured={settings.providers.hasFalKey} />
                  <KeyStatus label="Together" configured={settings.providers.hasTogetherKey} />
                  <KeyStatus label="BFL" configured={settings.providers.hasBflKey} />
                  <KeyStatus label="KIE" configured={settings.providers.hasKieKey} />
                  <KeyStatus label="Pixazo" configured={settings.providers.hasPixazoKey} />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Edit User Modal */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
          <div className="glass-panel w-full max-w-md rounded-2xl p-6" style={{ boxShadow: "var(--shadow-float)" }}>
            <div className="mb-6 flex items-center justify-between">
              <h3 className="font-display text-lg tracking-tight">Edit user</h3>
              <button onClick={() => setEditingUser(null)} className="rounded-xl border border-white/10 bg-white/5 p-1.5 hover:bg-white/10 transition">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <p className="kerned text-white/40 mb-2">NAME</p>
                <input type="text" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
              </div>
              <div>
                <p className="kerned text-white/40 mb-2">EMAIL</p>
                <input type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
              </div>
              <div>
                <p className="kerned text-white/40 mb-2">ROLE</p>
                <select value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })} className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30">
                  <option value="USER">USER</option>
                  <option value="ADMIN">ADMIN</option>
                  <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                </select>
              </div>
              <div>
                <p className="kerned text-white/40 mb-2">CREDITS</p>
                <input type="number" value={editForm.credits} onChange={(e) => setEditForm({ ...editForm, credits: parseInt(e.target.value) })} className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30" />
              </div>
            </div>

            <div className="mt-6 flex gap-3">
              <button onClick={() => setEditingUser(null)} className="flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm hover:bg-white/10 transition">Cancel</button>
              <button onClick={handleUpdateUser} className="flex-1 rounded-xl px-4 py-2 text-sm font-medium text-black transition" style={{ background: "var(--gradient-aurora)" }}>Save changes</button>
            </div>
          </div>
        </div>
      )}

      {/* Model Ratings Modal */}
      {viewingRatingsModel && (
        <ModelRatingsModal
          isOpen={true}
          onClose={() => setViewingRatingsModel(null)}
          modelId={viewingRatingsModel.id}
          modelName={viewingRatingsModel.name}
        />
      )}
    </div>
  );
}

// Helper Components
function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="glass-panel rounded-2xl p-4">
      <p className="kerned text-white/40 mb-2">{label}</p>
      <p className="font-mono text-3xl text-aurora">{value}</p>
    </div>
  );
}

function Switch({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={cn("relative h-5 w-9 rounded-full transition", on ? "bg-white/80" : "bg-white/10")}>
      <span className={cn("absolute top-0.5 h-4 w-4 rounded-full transition", on ? "left-0.5 translate-x-4 bg-black" : "left-0.5 bg-white")} />
    </button>
  );
}

function SettingToggle({ label, description, enabled, onToggle }: { label: string; description: string; enabled: boolean; onToggle: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 py-3 last:border-0">
      <div>
        <div className="text-sm text-white/85">{label}</div>
        <div className="text-xs text-white/50">{description}</div>
      </div>
      <Switch on={enabled} onClick={onToggle} />
    </div>
  );
}

function KeyStatus({ label, configured }: { label: string; configured: boolean }) {
  return (
    <div className="hairline flex items-center justify-between rounded-xl p-3">
      <span className="text-sm text-white/85">{label}</span>
      <span className="inline-flex items-center gap-1.5 text-xs text-white/60">
        <span className={cn("h-2 w-2 rounded-full", configured ? "bg-emerald-500/80" : "bg-red-500/80")} />
        {configured ? "Configured" : "Missing"}
      </span>
    </div>
  );
}
