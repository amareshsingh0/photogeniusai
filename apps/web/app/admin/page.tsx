"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
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
  CheckCircle,
  XCircle,
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
    try {
      // Update setting
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

      // Auto-restart API to apply changes
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const restartRes = await fetch(`${apiUrl}/api/v1/admin/config/restart`, {
        method: "POST",
      });

      if (!restartRes.ok) {
        console.warn("Failed to auto-restart API:", await restartRes.text());
      }

      // Refresh settings after restart
      setTimeout(() => {
        fetchSettings();
      }, 3000);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const fetchModels = async () => {
    setModelsLoading(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/models`);
      if (!res.ok) throw new Error("Failed to fetch models");
      const data = await res.json();
      setModels(data.models);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setModelsLoading(false);
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

      // Refresh models list
      fetchModels();
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

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-900/50">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-600 to-orange-600 flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">Admin Dashboard</h1>
                <p className="text-sm text-zinc-500">Full system control & analytics</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>

          {/* Tabs */}
          <div className="flex gap-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all",
                    activeTab === tab.id
                      ? "bg-violet-600 text-white"
                      : "bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800 hover:text-white"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400">
            {error}
          </div>
        )}

        {/* Overview Tab */}
        {activeTab === "overview" && analytics && (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                label="Total Users"
                value={analytics.overview.totalUsers}
                icon={Users}
                color="blue"
              />
              <StatCard
                label="Total Generations"
                value={analytics.overview.totalGenerations}
                icon={ImageIcon}
                color="violet"
              />
              <StatCard
                label="Active Users (7d)"
                value={analytics.overview.activeUsers}
                icon={Users}
                color="green"
              />
              <StatCard
                label="Credits Used"
                value={analytics.overview.totalCreditsUsed}
                icon={BarChart3}
                color="orange"
              />
            </div>

            {/* Generation Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatCard
                label="Today"
                value={analytics.generations.today}
                icon={ImageIcon}
                color="violet"
                small
              />
              <StatCard
                label="This Week"
                value={analytics.generations.week}
                icon={ImageIcon}
                color="violet"
                small
              />
              <StatCard
                label="This Month"
                value={analytics.generations.month}
                icon={ImageIcon}
                color="violet"
                small
              />
            </div>

            {/* Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
                <h3 className="text-lg font-semibold mb-4">By Quality Tier</h3>
                <div className="space-y-3">
                  {analytics.breakdown.byTier.map((item) => (
                    <div key={item.tier} className="flex items-center justify-between">
                      <span className="text-zinc-400 capitalize">{item.tier}</span>
                      <span className="font-semibold">{item.count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
                <h3 className="text-lg font-semibold mb-4">By Bucket</h3>
                <div className="space-y-3">
                  {analytics.breakdown.byBucket.slice(0, 5).map((item) => (
                    <div key={item.bucket} className="flex items-center justify-between">
                      <span className="text-zinc-400 capitalize">{item.bucket}</span>
                      <span className="font-semibold">{item.count}</span>
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
            {/* Search */}
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <input
                  type="text"
                  placeholder="Search by email or name..."
                  value={usersSearch}
                  onChange={(e) => {
                    setUsersSearch(e.target.value);
                    setUsersPage(1);
                  }}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-white placeholder:text-zinc-500 focus:outline-none focus:border-violet-600"
                />
              </div>
              <button
                onClick={fetchUsers}
                className="p-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            {/* Users Table */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-zinc-800 bg-zinc-900">
                      <th className="px-6 py-4 text-left text-xs font-semibold text-zinc-400 uppercase">
                        User
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-zinc-400 uppercase">
                        Role
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-zinc-400 uppercase">
                        Credits
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-zinc-400 uppercase">
                        Generations
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-zinc-400 uppercase">
                        Joined
                      </th>
                      <th className="px-6 py-4 text-right text-xs font-semibold text-zinc-400 uppercase">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                        <td className="px-6 py-4">
                          <div>
                            <div className="font-medium">{user.name}</div>
                            <div className="text-sm text-zinc-500">{user.email}</div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={cn(
                              "px-2 py-1 rounded-md text-xs font-medium",
                              user.role === "ADMIN" || user.role === "SUPER_ADMIN"
                                ? "bg-red-500/10 text-red-400"
                                : "bg-zinc-700 text-zinc-300"
                            )}
                          >
                            {user.role || "USER"}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-medium">{user.credits}</td>
                        <td className="px-6 py-4 text-zinc-400">{user._count.generations}</td>
                        <td className="px-6 py-4 text-sm text-zinc-500">
                          {new Date(user.createdAt).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center justify-end gap-2">
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
                              className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 transition-colors"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteUser(user.id)}
                              className="p-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex items-center justify-between px-6 py-4 border-t border-zinc-800">
                <div className="text-sm text-zinc-500">
                  Showing {users.length} of {usersTotal} users
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setUsersPage((p) => Math.max(1, p - 1))}
                    disabled={usersPage === 1}
                    className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-sm">Page {usersPage}</span>
                  <button
                    onClick={() => setUsersPage((p) => p + 1)}
                    disabled={users.length < 50}
                    className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Generations Tab */}
        {activeTab === "generations" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">All Generations</h2>
            </div>
            <GenerationsTable />
          </div>
        )}

        {/* Models Tab */}
        {activeTab === "models" && (
          <div className="max-w-7xl mx-auto px-6 py-8">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-2xl font-bold">Model Registry</h2>
                <p className="text-zinc-400 mt-1">Manage AI models for image generation</p>
              </div>
              <button
                onClick={fetchModels}
                disabled={modelsLoading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition-colors disabled:opacity-50"
              >
                <RefreshCw className={cn("w-4 h-4", modelsLoading && "animate-spin")} />
                Refresh
              </button>
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-2 mb-6">
              {(["all", "active", "inactive"] as const).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setModelsFilter(filter)}
                  className={cn(
                    "px-4 py-2 rounded-lg font-medium transition-colors capitalize",
                    modelsFilter === filter
                      ? "bg-violet-600 text-white"
                      : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                  )}
                >
                  {filter} ({filter === "all" ? models.length : filter === "active" ? models.filter(m => m.isActive).length : models.filter(m => !m.isActive).length})
                </button>
              ))}
            </div>

            {/* Models Grid */}
            {modelsLoading ? (
              <div className="flex items-center justify-center h-64">
                <RefreshCw className="w-8 h-8 animate-spin text-violet-500" />
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {models
                  .filter((m) =>
                    modelsFilter === "all" ? true :
                    modelsFilter === "active" ? m.isActive :
                    !m.isActive
                  )
                  .map((model) => (
                    <div
                      key={model.id}
                      className={cn(
                        "bg-zinc-900/50 border rounded-xl p-6 transition-all",
                        model.isActive ? "border-green-500/30 hover:border-green-500/50" : "border-zinc-800 hover:border-zinc-700"
                      )}
                    >
                      {/* Header */}
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h3 className="text-lg font-semibold">{model.displayName}</h3>
                            {model.isActive ? (
                              <CheckCircle className="w-5 h-5 text-green-500" />
                            ) : (
                              <XCircle className="w-5 h-5 text-zinc-600" />
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-sm">
                            <span className="px-2 py-1 rounded-md bg-zinc-800 text-zinc-400 font-mono">
                              {model.provider}
                            </span>
                            <span className="text-zinc-500">•</span>
                            <span className="text-zinc-400">{model.modelId}</span>
                          </div>
                        </div>
                      </div>

                      {/* Buckets */}
                      <div className="flex flex-wrap gap-2 mb-4">
                        {model.buckets.map((bucket) => (
                          <span
                            key={bucket}
                            className="px-2 py-1 rounded-md bg-violet-500/10 text-violet-400 text-xs font-medium"
                          >
                            {bucket}
                          </span>
                        ))}
                      </div>

                      {/* Stats Grid */}
                      <div className="grid grid-cols-2 gap-3 mb-4">
                        <div className="bg-zinc-800/50 rounded-lg p-3">
                          <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                            <DollarSign className="w-3 h-3" />
                            Cost/Image
                          </div>
                          <div className="text-lg font-semibold">${model.costPerImage.toFixed(3)}</div>
                        </div>
                        <div className="bg-zinc-800/50 rounded-lg p-3">
                          <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                            <ImageIcon className="w-3 h-3" />
                            Generations
                          </div>
                          <div className="text-lg font-semibold">{model.totalGenerations}</div>
                        </div>
                        <div className="bg-zinc-800/50 rounded-lg p-3">
                          <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                            <Star className="w-3 h-3" />
                            Avg Rating
                          </div>
                          <div className="text-lg font-semibold">
                            {model.avgRating ? model.avgRating.toFixed(2) : "N/A"}
                          </div>
                        </div>
                        <div className="bg-zinc-800/50 rounded-lg p-3">
                          <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                            <Clock className="w-3 h-3" />
                            Avg Latency
                          </div>
                          <div className="text-lg font-semibold">
                            {model.avgLatency ? `${model.avgLatency.toFixed(1)}s` : "N/A"}
                          </div>
                        </div>
                      </div>

                      {/* Toggle Switches */}
                      <div className="space-y-3 pt-4 border-t border-zinc-800">
                        {/* Active Toggle */}
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-medium text-sm">Active for Production</div>
                            <div className="text-xs text-zinc-500">
                              {model.isActive ? "Available for generation" : "Disabled"}
                            </div>
                          </div>
                          <button
                            onClick={() => handleToggleModel(model.modelId, "isActive", model.isActive)}
                            className={cn(
                              "relative w-14 h-8 rounded-full transition-colors",
                              model.isActive ? "bg-green-500" : "bg-zinc-700"
                            )}
                          >
                            <div
                              className={cn(
                                "absolute top-1 w-6 h-6 bg-white rounded-full transition-transform",
                                model.isActive ? "right-1" : "left-1"
                              )}
                            />
                          </button>
                        </div>

                        {/* Testing Toggle */}
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-medium text-sm">Testing Mode</div>
                            <div className="text-xs text-zinc-500">
                              {model.isTestingEnabled ? "Enabled for parallel testing" : "Not in testing"}
                            </div>
                          </div>
                          <button
                            onClick={() => handleToggleModel(model.modelId, "isTestingEnabled", model.isTestingEnabled)}
                            className={cn(
                              "relative w-14 h-8 rounded-full transition-colors",
                              model.isTestingEnabled ? "bg-violet-500" : "bg-zinc-700"
                            )}
                          >
                            <div
                              className={cn(
                                "absolute top-1 w-6 h-6 bg-white rounded-full transition-transform",
                                model.isTestingEnabled ? "right-1" : "left-1"
                              )}
                            />
                          </button>
                        </div>

                        {/* View Ratings Button */}
                        <button
                          onClick={() => setViewingRatingsModel({ id: model.modelId, name: model.displayName })}
                          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 transition-colors text-sm font-medium"
                        >
                          <Star className="w-4 h-4" />
                          View Ratings
                          {model.avgRating && ` (${model.avgRating.toFixed(1)} avg)`}
                        </button>
                      </div>
                    </div>
                  ))}
              </div>
            )}

            {/* Empty State */}
            {!modelsLoading && models.filter((m) =>
              modelsFilter === "all" ? true :
              modelsFilter === "active" ? m.isActive :
              !m.isActive
            ).length === 0 && (
              <div className="text-center py-16 text-zinc-500">
                No {modelsFilter !== "all" && modelsFilter} models found
              </div>
            )}
          </div>
        )}

        {/* Feature Config Tab */}
        {activeTab === "config" && (
          <FeatureConfigPanel />
        )}

        {/* Settings Tab */}
        {activeTab === "settings" && settings && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">System Settings</h2>

            {/* Generation Settings */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">Generation Backend</h3>
              <div className="space-y-3">
                <SettingToggle
                  label="Use Ideogram v3"
                  description="Typography & poster generation"
                  enabled={settings.generation.useIdeogram}
                  onToggle={() =>
                    handleToggleSetting("generation", "useIdeogram", settings.generation.useIdeogram)
                  }
                />
                <SettingToggle
                  label="Use Gemini Engine"
                  description="Prompt engineering with Gemini 2.5 Flash"
                  enabled={settings.generation.useGeminiEngine}
                  onToggle={() =>
                    handleToggleSetting(
                      "generation",
                      "useGeminiEngine",
                      settings.generation.useGeminiEngine
                    )
                  }
                />
                <SettingToggle
                  label="Use BFL API"
                  description="Flux 2 Max official ($0.060)"
                  enabled={settings.generation.useBfl}
                  onToggle={() =>
                    handleToggleSetting("generation", "useBfl", settings.generation.useBfl)
                  }
                />
                <SettingToggle
                  label="Use KIE API"
                  description="Flux 2 Pro cheapest ($0.025)"
                  enabled={settings.generation.useKie}
                  onToggle={() =>
                    handleToggleSetting("generation", "useKie", settings.generation.useKie)
                  }
                />
                <SettingToggle
                  label="Use Pixazo API"
                  description="Flux Schnell cheapest ($0.0012)"
                  enabled={settings.generation.usePixazo}
                  onToggle={() =>
                    handleToggleSetting("generation", "usePixazo", settings.generation.usePixazo)
                  }
                />
              </div>
            </div>

            {/* BEAST Architecture */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">BEAST Architecture</h3>
              <div className="space-y-3">
                <SettingToggle
                  label="Master Strategist"
                  description="Consolidate 3 agents → 1 (58% faster, 60% token savings)"
                  enabled={settings.beast.useMasterStrategist}
                  onToggle={() =>
                    handleToggleSetting(
                      "beast",
                      "useMasterStrategist",
                      settings.beast.useMasterStrategist
                    )
                  }
                />
                <SettingToggle
                  label="Deterministic Layout"
                  description="Python + OpenCV layout engine (100% reliability)"
                  enabled={settings.beast.useDeterministicLayout}
                  onToggle={() =>
                    handleToggleSetting(
                      "beast",
                      "useDeterministicLayout",
                      settings.beast.useDeterministicLayout
                    )
                  }
                />
                <SettingToggle
                  label="Hybrid Quality Critic"
                  description="VLM + Python validation (95% accuracy)"
                  enabled={settings.beast.useHybridQualityCritic}
                  onToggle={() =>
                    handleToggleSetting(
                      "beast",
                      "useHybridQualityCritic",
                      settings.beast.useHybridQualityCritic
                    )
                  }
                />
              </div>
            </div>

            {/* Quality Settings */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">Quality Critic</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-2">
                    Global Threshold
                  </label>
                  <input
                    type="number"
                    value={settings.quality.threshold}
                    readOnly
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-2">
                    Dimension Floor
                  </label>
                  <input
                    type="number"
                    value={settings.quality.dimensionFloor}
                    readOnly
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-2">
                    Max Images
                  </label>
                  <input
                    type="number"
                    value={settings.quality.maxImages}
                    readOnly
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-2">
                    Beast Gates Min
                  </label>
                  <input
                    type="number"
                    value={settings.quality.beastGatesMin}
                    readOnly
                    className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white"
                  />
                </div>
              </div>
            </div>

            {/* API Keys Status */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-4">API Keys Status</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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

      {/* Edit User Modal */}
      {editingUser && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-md"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold">Edit User</h3>
              <button
                onClick={() => setEditingUser(null)}
                className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Name</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white focus:outline-none focus:border-violet-600"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Email</label>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white focus:outline-none focus:border-violet-600"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Role</label>
                <select
                  value={editForm.role}
                  onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}
                  className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white focus:outline-none focus:border-violet-600"
                >
                  <option value="USER">USER</option>
                  <option value="ADMIN">ADMIN</option>
                  <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-2">Credits</label>
                <input
                  type="number"
                  value={editForm.credits}
                  onChange={(e) => setEditForm({ ...editForm, credits: parseInt(e.target.value) })}
                  className="w-full px-4 py-2.5 rounded-lg bg-zinc-800 border border-zinc-700 text-white focus:outline-none focus:border-violet-600"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setEditingUser(null)}
                className="flex-1 px-4 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateUser}
                className="flex-1 px-4 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 font-medium transition-colors"
              >
                Save Changes
              </button>
            </div>
          </motion.div>
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
function StatCard({
  label,
  value,
  icon: Icon,
  color,
  small = false,
}: {
  label: string;
  value: number | string;
  icon: any;
  color: string;
  small?: boolean;
}) {
  const colorClasses = {
    blue: "from-blue-600 to-cyan-600",
    violet: "from-violet-600 to-indigo-600",
    green: "from-green-600 to-emerald-600",
    orange: "from-orange-600 to-red-600",
  };

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-3">
        <div
          className={cn(
            "w-10 h-10 rounded-lg bg-gradient-to-br flex items-center justify-center",
            colorClasses[color as keyof typeof colorClasses]
          )}
        >
          <Icon className="w-5 h-5 text-white" />
        </div>
        <span className="text-sm font-medium text-zinc-400">{label}</span>
      </div>
      <div className={cn("font-bold", small ? "text-2xl" : "text-3xl")}>{value}</div>
    </div>
  );
}

function SettingToggle({
  label,
  description,
  enabled,
  onToggle,
}: {
  label: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <div className="font-medium">{label}</div>
        <div className="text-sm text-zinc-500">{description}</div>
      </div>
      <button
        onClick={onToggle}
        className={cn(
          "relative w-12 h-6 rounded-full transition-colors",
          enabled ? "bg-violet-600" : "bg-zinc-700"
        )}
      >
        <div
          className={cn(
            "absolute top-1 w-4 h-4 rounded-full bg-white transition-transform",
            enabled ? "translate-x-7" : "translate-x-1"
          )}
        />
      </button>
    </div>
  );
}

function KeyStatus({ label, configured }: { label: string; configured: boolean }) {
  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50">
      <span className="text-sm font-medium">{label}</span>
      <span
        className={cn(
          "px-2 py-1 rounded-md text-xs font-medium",
          configured ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"
        )}
      >
        {configured ? "✓" : "✗"}
      </span>
    </div>
  );
}
