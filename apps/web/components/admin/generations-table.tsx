"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { Search, Filter, SlidersHorizontal, Trash2, Star, Clock, Image as ImageIcon } from "lucide-react";
import { brandedImageUrl } from "@/lib/image-url";

interface Generation {
  id: string;
  originalPrompt: string;
  enhancedPrompt: string | null;
  mode: string;
  creditsUsed: number;
  qualityTierUsed: string | null;
  modelUsed: string | null;
  bucket: string | null;
  selectedOutputUrl: string | null;
  thumbnailUrl: string | null;
  userRating: number | null;
  userReason: string | null;
  generationTimeSeconds: number | null;
  overallScore: number | null;
  createdAt: string;
  user: {
    id: string;
    email: string;
    name: string | null;
  };
}

interface FilterOptions {
  users: Array<{ id: string; email: string; name: string | null }>;
  models: Array<{ value: string; count: number }>;
  buckets: Array<{ value: string; count: number }>;
  qualities: Array<{ value: string; count: number }>;
}

export default function GenerationsTable() {
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Pagination
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  // Filters
  const [search, setSearch] = useState("");
  const [qualityFilter, setQualityFilter] = useState("");
  const [modelFilter, setModelFilter] = useState("");
  const [userFilter, setUserFilter] = useState("");
  const [bucketFilter, setBucketFilter] = useState("");
  const [sortBy, setSortBy] = useState("createdAt");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [showFilters, setShowFilters] = useState(false);

  // Filter options
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    users: [],
    models: [],
    buckets: [],
    qualities: [],
  });

  // Selected generation for details modal
  const [selectedGen, setSelectedGen] = useState<Generation | null>(null);

  useEffect(() => {
    fetchGenerations();
  }, [page, search, qualityFilter, modelFilter, userFilter, bucketFilter, sortBy, sortOrder]);

  useEffect(() => {
    fetchFilterOptions();
  }, []);

  const fetchGenerations = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: "50",
        ...(search && { search }),
        ...(qualityFilter && { quality: qualityFilter }),
        ...(modelFilter && { model: modelFilter }),
        ...(userFilter && { userId: userFilter }),
        ...(bucketFilter && { bucket: bucketFilter }),
        sortBy,
        sortOrder,
      });

      const res = await fetch(`/api/admin/generations?${params}`);
      if (!res.ok) throw new Error("Failed to fetch generations");

      const data = await res.json();
      setGenerations(data.generations);
      setTotal(data.pagination.total);
      setTotalPages(data.pagination.totalPages);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchFilterOptions = async () => {
    try {
      const res = await fetch("/api/admin/generations/filters");
      if (!res.ok) throw new Error("Failed to fetch filter options");
      const data = await res.json();
      setFilterOptions(data);
    } catch (err: any) {
      console.error("Failed to fetch filter options:", err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this generation?")) return;

    try {
      const res = await fetch(`/api/admin/generations?generationId=${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete generation");
      fetchGenerations();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const resetFilters = () => {
    setSearch("");
    setQualityFilter("");
    setModelFilter("");
    setUserFilter("");
    setBucketFilter("");
    setSortBy("createdAt");
    setSortOrder("desc");
    setPage(1);
  };

  const renderStars = (rating: number | null) => {
    if (!rating) return <span className="text-zinc-600">No rating</span>;
    return (
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`w-4 h-4 ${
              star <= rating ? "fill-yellow-500 text-yellow-500" : "text-zinc-700"
            }`}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Search and Filters Bar */}
      <div className="flex items-center gap-3">
        {/* Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
          <input
            type="text"
            placeholder="Search prompts..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="w-full pl-10 pr-4 py-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-violet-600"
          />
        </div>

        {/* Filter Toggle */}
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`px-4 py-2 rounded-lg border transition-colors flex items-center gap-2 ${
            showFilters
              ? "bg-violet-600 border-violet-600 text-white"
              : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700"
          }`}
        >
          <SlidersHorizontal className="w-4 h-4" />
          Filters
        </button>

        {/* Reset Filters */}
        {(search || qualityFilter || modelFilter || userFilter || bucketFilter) && (
          <button
            onClick={resetFilters}
            className="px-4 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:border-zinc-700 transition-colors"
          >
            Reset
          </button>
        )}
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 p-4 bg-zinc-900 border border-zinc-800 rounded-lg">
          {/* Quality Filter */}
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Quality</label>
            <select
              value={qualityFilter}
              onChange={(e) => {
                setQualityFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-violet-600"
            >
              <option value="">All</option>
              {filterOptions.qualities.map((q) => (
                <option key={q.value} value={q.value}>
                  {q.value} ({q.count})
                </option>
              ))}
            </select>
          </div>

          {/* Model Filter */}
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Model</label>
            <select
              value={modelFilter}
              onChange={(e) => {
                setModelFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-violet-600"
            >
              <option value="">All</option>
              {filterOptions.models.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.value} ({m.count})
                </option>
              ))}
            </select>
          </div>

          {/* Bucket Filter */}
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Bucket</label>
            <select
              value={bucketFilter}
              onChange={(e) => {
                setBucketFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-violet-600"
            >
              <option value="">All</option>
              {filterOptions.buckets.map((b) => (
                <option key={b.value} value={b.value}>
                  {b.value} ({b.count})
                </option>
              ))}
            </select>
          </div>

          {/* User Filter */}
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">User</label>
            <select
              value={userFilter}
              onChange={(e) => {
                setUserFilter(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-violet-600"
            >
              <option value="">All</option>
              {filterOptions.users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}
                </option>
              ))}
            </select>
          </div>

          {/* Sort By */}
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Sort By</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-violet-600"
            >
              <option value="createdAt">Date</option>
              <option value="creditsUsed">Credits</option>
              <option value="userRating">Rating</option>
              <option value="generationTimeSeconds">Time</option>
            </select>
          </div>

          {/* Sort Order */}
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-2">Order</label>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}
              className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:border-violet-600"
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </div>
        </div>
      )}

      {/* Stats Bar */}
      <div className="flex items-center justify-between text-sm text-zinc-400">
        <div>
          Showing {generations.length > 0 ? (page - 1) * 50 + 1 : 0} -{" "}
          {Math.min(page * 50, total)} of {total} generations
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="text-center py-12 text-zinc-500">Loading generations...</div>
      )}

      {/* Table */}
      {!loading && generations.length === 0 && (
        <div className="text-center py-12 text-zinc-500">No generations found</div>
      )}

      {!loading && generations.length > 0 && (
        <div className="space-y-3">
          {generations.map((gen) => (
            <div
              key={gen.id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-colors"
            >
              <div className="flex gap-4">
                {/* Thumbnail */}
                <div className="shrink-0">
                  {gen.thumbnailUrl || gen.selectedOutputUrl ? (
                    <div className="relative w-24 h-24 rounded-lg overflow-hidden border border-zinc-700">
                      <Image
                        src={brandedImageUrl(gen.thumbnailUrl || gen.selectedOutputUrl || "")}
                        alt="Generation"
                        fill
                        className="object-cover"
                        unoptimized
                      />
                    </div>
                  ) : (
                    <div className="w-24 h-24 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                      <ImageIcon className="w-8 h-8 text-zinc-600" />
                    </div>
                  )}
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  {/* Header Row */}
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-zinc-400">
                          {gen.user.email}
                        </span>
                        {gen.bucket && (
                          <span className="px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-400 text-xs font-medium">
                            {gen.bucket}
                          </span>
                        )}
                        {gen.modelUsed && (
                          <span className="px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-400 text-xs font-medium">
                            {gen.modelUsed}
                          </span>
                        )}
                        {gen.qualityTierUsed && (
                          <span className="px-2 py-0.5 rounded-md bg-green-500/10 text-green-400 text-xs font-medium">
                            {gen.qualityTierUsed}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-white line-clamp-2">{gen.originalPrompt}</p>
                    </div>

                    {/* Actions */}
                    <button
                      onClick={() => handleDelete(gen.id)}
                      className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Metadata Row */}
                  <div className="flex items-center gap-4 text-xs text-zinc-500">
                    <div className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {gen.generationTimeSeconds
                        ? `${gen.generationTimeSeconds.toFixed(1)}s`
                        : "N/A"}
                    </div>
                    <div>Credits: {gen.creditsUsed}</div>
                    {gen.overallScore && (
                      <div>Score: {gen.overallScore.toFixed(1)}/10</div>
                    )}
                    <div>{new Date(gen.createdAt).toLocaleDateString()}</div>
                  </div>

                  {/* Rating & Feedback */}
                  {(gen.userRating || gen.userReason) && (
                    <div className="mt-3 p-3 bg-zinc-800/50 rounded-lg">
                      <div className="flex items-center gap-3 mb-2">
                        {renderStars(gen.userRating)}
                      </div>
                      {gen.userReason && (
                        <p className="text-sm text-zinc-400">{gen.userReason}</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-4 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:border-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <span className="px-4 py-2 text-zinc-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:border-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
