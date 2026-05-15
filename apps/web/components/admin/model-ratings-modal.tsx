"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Star, Clock, Download } from "lucide-react";
import Image from "next/image";
import { cn } from "@/lib/utils";
import { brandedImageUrl } from "@/lib/image-url";

interface Rating {
  rating: number;
  reason: string | null;
  generation_time_seconds: number | null;
  prompt: string;
  bucket: string | null;
  image_url: string;
  created_at: string;
}

interface ModelRatingsData {
  model_id: string;
  total_ratings: number;
  ratings: Rating[];
}

interface ModelRatingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  modelId: string;
  modelName: string;
}

export default function ModelRatingsModal({
  isOpen,
  onClose,
  modelId,
  modelName,
}: ModelRatingsModalProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ModelRatingsData | null>(null);
  const [error, setError] = useState("");
  const [ratingFilter, setRatingFilter] = useState<number | "all">("all");

  useEffect(() => {
    if (isOpen && modelId) {
      fetchRatings();
    }
  }, [isOpen, modelId]);

  const fetchRatings = async () => {
    setLoading(true);
    setError("");
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/admin/models/${modelId}/ratings`);
      if (!res.ok) throw new Error("Failed to fetch ratings");
      const ratingsData = await res.json();
      setData(ratingsData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredRatings = data?.ratings.filter((r) =>
    ratingFilter === "all" ? true : r.rating === ratingFilter
  ) || [];

  const exportToCSV = () => {
    if (!data || data.ratings.length === 0) return;

    const headers = ["Rating", "Reason", "Generation Time (s)", "Prompt", "Bucket", "Image URL", "Created At"];
    const rows = data.ratings.map((r) => [
      r.rating,
      r.reason || "",
      r.generation_time_seconds || "",
      r.prompt.replace(/"/g, '""'), // Escape quotes
      r.bucket || "",
      r.image_url,
      new Date(r.created_at).toISOString(),
    ]);

    const csvContent = [
      headers.join(","),
      ...rows.map((row) => row.map((cell) => `"${cell}"`).join(",")),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${modelId}_ratings_${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-4xl max-h-[90vh] bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl z-50 overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-zinc-800">
              <div>
                <h3 className="text-xl font-bold text-white">Ratings for {modelName}</h3>
                <p className="text-sm text-zinc-400 mt-1">
                  {data ? `${data.total_ratings} total ratings` : "Loading..."}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {data && data.ratings.length > 0 && (
                  <button
                    onClick={exportToCSV}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition-colors text-sm"
                  >
                    <Download className="w-4 h-4" />
                    Export CSV
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg hover:bg-zinc-800 transition-colors text-zinc-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Filter Tabs */}
            {data && data.ratings.length > 0 && (
              <div className="flex gap-2 px-6 py-4 border-b border-zinc-800 overflow-x-auto">
                {(["all", 5, 4, 3, 2, 1] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setRatingFilter(filter)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg font-medium transition-colors whitespace-nowrap text-sm",
                      ratingFilter === filter
                        ? "bg-violet-600 text-white"
                        : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                    )}
                  >
                    {filter === "all" ? "All" : `${filter} ⭐`}
                    {" "}
                    ({filter === "all"
                      ? data.ratings.length
                      : data.ratings.filter((r) => r.rating === filter).length})
                  </button>
                ))}
              </div>
            )}

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {loading && (
                <div className="flex items-center justify-center h-64 text-zinc-400">
                  Loading ratings...
                </div>
              )}

              {error && (
                <div className="flex items-center justify-center h-64">
                  <div className="text-center">
                    <p className="text-red-400 font-medium mb-2">Error loading ratings</p>
                    <p className="text-sm text-zinc-500">{error}</p>
                  </div>
                </div>
              )}

              {!loading && !error && data && filteredRatings.length === 0 && (
                <div className="flex items-center justify-center h-64 text-zinc-500">
                  No ratings found
                  {ratingFilter !== "all" && ` with ${ratingFilter} stars`}
                </div>
              )}

              {!loading && !error && filteredRatings.length > 0 && (
                <div className="space-y-4">
                  {filteredRatings.map((rating, index) => (
                    <div
                      key={index}
                      className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-4 hover:border-zinc-600 transition-colors"
                    >
                      {/* Rating Header */}
                      <div className="flex items-start gap-4 mb-3">
                        {/* Image Thumbnail */}
                        <div className="relative w-24 h-24 rounded-lg overflow-hidden border border-zinc-700 shrink-0">
                          <Image
                            src={brandedImageUrl(rating.image_url)}
                            alt="Generated"
                            fill
                            className="object-cover"
                            unoptimized
                          />
                        </div>

                        {/* Rating Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            {/* Stars */}
                            <div className="flex items-center gap-1">
                              {[1, 2, 3, 4, 5].map((star) => (
                                <Star
                                  key={star}
                                  className={cn(
                                    "w-4 h-4",
                                    star <= rating.rating
                                      ? "fill-yellow-500 text-yellow-500"
                                      : "text-zinc-600"
                                  )}
                                />
                              ))}
                            </div>

                            {/* Generation Time */}
                            {rating.generation_time_seconds && (
                              <div className="flex items-center gap-1 text-xs text-zinc-400">
                                <Clock className="w-3 h-3" />
                                {rating.generation_time_seconds.toFixed(1)}s
                              </div>
                            )}

                            {/* Bucket */}
                            {rating.bucket && (
                              <span className="px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-400 text-xs font-medium">
                                {rating.bucket}
                              </span>
                            )}

                            {/* Date */}
                            <span className="text-xs text-zinc-500 ml-auto shrink-0">
                              {new Date(rating.created_at).toLocaleDateString()}
                            </span>
                          </div>

                          {/* Prompt */}
                          <p className="text-sm text-zinc-400 mb-2 line-clamp-2">
                            {rating.prompt}
                          </p>

                          {/* Reason */}
                          {rating.reason && (
                            <div className="bg-zinc-900/50 rounded-lg p-3 mt-2">
                              <p className="text-xs text-zinc-500 mb-1 font-medium">User feedback:</p>
                              <p className="text-sm text-zinc-300">{rating.reason}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
