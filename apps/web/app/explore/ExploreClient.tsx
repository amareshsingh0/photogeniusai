"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import {
  Heart,
  MessageCircle,
  Share2,
  Flag,
  Loader2,
  X,
  Send,
  Compass,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export type GalleryItem = {
  id: string;
  prompt: string;
  mode: string;
  url: string | null;
  thumbnailUrl?: string | null;
  category?: string | null;
  style?: string | null;
  likesCount: number;
  commentsCount: number;
  publishedAt: string | null;
  user: {
    id: string;
    name: string;
    profileImageUrl?: string | null;
  } | null;
};

type Comment = {
  id: string;
  body: string;
  createdAt: string;
  user: { id: string; name: string; profileImageUrl?: string } | null;
};

const FILTER_PILLS: { id: string; label: string; emoji: string; sort?: "recent" | "trending"; style?: string }[] = [
  { id: "trending", label: "Trending", emoji: "🔥", sort: "trending" },
  { id: "new", label: "New", emoji: "✨", sort: "recent" },
  { id: "realistic", label: "Realistic", emoji: "📸", style: "Realistic" },
  { id: "cinematic", label: "Cinematic", emoji: "🎬", style: "Cinematic" },
  { id: "portrait", label: "Portrait", emoji: "🧬", style: "Portrait" },
  { id: "scene", label: "Scene", emoji: "🌆", style: "Scene" },
];

export default function ExploreClient({
  initialItems,
  initialNextCursor,
  activityToday = 0,
  showFeaturedLabel = false,
}: {
  initialItems: GalleryItem[];
  initialNextCursor: string | null;
  activityToday?: number;
  showFeaturedLabel?: boolean;
}) {
  const [items, setItems] = useState<GalleryItem[]>(initialItems);
  const [nextCursor, setNextCursor] = useState<string | null>(initialNextCursor);
  const [loadingMore, setLoadingMore] = useState(false);
  const [sort, setSort] = useState<"recent" | "trending">("recent");
  const [styleFilter, setStyleFilter] = useState<string>("");
  const [liked, setLiked] = useState<Record<string, boolean>>({});
  const [likeCounts, setLikeCounts] = useState<Record<string, number>>(
    Object.fromEntries(initialItems.map((i) => [i.id, i.likesCount]))
  );
  const [selected, setSelected] = useState<GalleryItem | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState("OTHER");
  const [reportDesc, setReportDesc] = useState("");
  const [activityDisplay, setActivityDisplay] = useState(activityToday);

  useEffect(() => {
    setActivityDisplay(activityToday);
  }, [activityToday]);

  // Fetch activity for header (e.g. after filter or on mount)
  useEffect(() => {
    let cancelled = false;
    fetch("/api/gallery/explore-activity")
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled && typeof data.todayCount === "number") setActivityDisplay(data.todayCount);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const params = new URLSearchParams({
        sort,
        limit: "24",
        cursor: nextCursor,
      });
      if (styleFilter) params.set("style", styleFilter);
      const res = await fetch(`/api/gallery?${params}`);
      const data = await res.json();
      if (data.items?.length) {
        setItems((prev) => [...prev, ...data.items]);
        setLikeCounts((prev) => ({
          ...prev,
          ...Object.fromEntries(data.items.map((i: GalleryItem) => [i.id, i.likesCount])),
        }));
      }
      setNextCursor(data.nextCursor ?? null);
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, loadingMore, sort, styleFilter]);

  const applyPillClick = (pill: (typeof FILTER_PILLS)[number]) => {
    if (pill.sort) {
      setSort(pill.sort);
      setStyleFilter("");
      if (!showFeaturedLabel) {
        setLoadingMore(true);
        const params = new URLSearchParams({ sort: pill.sort, limit: "24" });
        fetch(`/api/gallery?${params}`)
          .then((r) => r.json())
          .then((data) => {
            setItems(data.items ?? []);
            setNextCursor(data.nextCursor ?? null);
            setLikeCounts(
              Object.fromEntries((data.items ?? []).map((i: GalleryItem) => [i.id, i.likesCount]))
            );
          })
          .finally(() => setLoadingMore(false));
      }
    } else if (pill.style) {
      const next = styleFilter === pill.style ? "" : pill.style;
      setStyleFilter(next);
      if (!showFeaturedLabel) {
        setLoadingMore(true);
        const params = new URLSearchParams({ sort, limit: "24" });
        if (next) params.set("style", next);
        fetch(`/api/gallery?${params}`)
          .then((r) => r.json())
          .then((data) => {
            setItems(data.items ?? []);
            setNextCursor(data.nextCursor ?? null);
            setLikeCounts(
              Object.fromEntries((data.items ?? []).map((i: GalleryItem) => [i.id, i.likesCount]))
            );
          })
          .finally(() => setLoadingMore(false));
      }
    }
  };

  const filteredItems = useMemo(() => {
    if (showFeaturedLabel) {
      let list = [...initialItems];
      if (styleFilter) list = list.filter((i) => (i.style ?? i.category) === styleFilter);
      if (sort === "trending") list = [...list].sort((a, b) => b.likesCount - a.likesCount);
      return list;
    }
    return items;
  }, [showFeaturedLabel, initialItems, items, styleFilter, sort]);

  const toggleLike = useCallback(async (id: string) => {
    if (id.startsWith("seed-")) return;
    try {
      const res = await fetch(`/api/gallery/${id}/like`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setLiked((prev) => ({ ...prev, [id]: data.liked }));
        setLikeCounts((prev) => ({
          ...prev,
          [id]: (prev[id] ?? 0) + (data.liked ? 1 : -1),
        }));
        if (selected?.id === id) {
          setSelected((s) =>
            s ? { ...s, likesCount: (s.likesCount ?? 0) + (data.liked ? 1 : -1) } : null
          );
        }
      }
    } catch {
      // ignore
    }
  }, [selected?.id]);

  const openDetail = useCallback(async (item: GalleryItem) => {
    setSelected(item);
    setComments([]);
    if (item.id.startsWith("seed-")) {
      setCommentsLoading(false);
      return;
    }
    setCommentsLoading(true);
    try {
      const res = await fetch(`/api/gallery/${item.id}/comments?limit=50`);
      const data = await res.json();
      setComments(data.comments ?? []);
    } finally {
      setCommentsLoading(false);
    }
  }, []);

  const submitComment = useCallback(async () => {
    if (!selected || !newComment.trim() || selected.id.startsWith("seed-")) return;
    try {
      const res = await fetch(`/api/gallery/${selected.id}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: newComment.trim() }),
      });
      const data = await res.json();
      if (res.ok && data.comment) {
        setComments((prev) => [...prev, data.comment]);
        setNewComment("");
        setSelected((s) =>
          s ? { ...s, commentsCount: (s.commentsCount ?? 0) + 1 } : null
        );
      }
    } catch {
      // ignore
    }
  }, [selected, newComment]);

  const submitReport = useCallback(async () => {
    if (!selected || selected.id.startsWith("seed-")) return;
    try {
      await fetch("/api/gallery/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          generationId: selected.id,
          reason: reportReason,
          description: reportDesc || undefined,
        }),
      });
      setReportOpen(false);
      setSelected(null);
    } catch {
      // ignore
    }
  }, [selected, reportReason, reportDesc]);

  const share = useCallback((item: GalleryItem) => {
    const url = typeof window !== "undefined" ? `${window.location.origin}/explore?highlight=${item.id}` : "";
    if (navigator.share) {
      navigator.share({
        title: "PhotoGenius AI",
        text: item.prompt?.slice(0, 100) ?? "",
        url,
      }).catch(() => {});
    } else {
      navigator.clipboard?.writeText(url).catch(() => {});
    }
  }, []);

  const remixUrl = (item: GalleryItem) =>
    `/generate?prompt=${encodeURIComponent(item.prompt || "")}`;

  const activityText =
    activityDisplay > 0
      ? `${activityDisplay.toLocaleString()} creations today`
      : "Community gallery";

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6"
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
            <span className="inline-flex p-2 rounded-xl bg-primary/10">
              <Compass className="h-6 w-6 text-primary" />
            </span>
            <span className="gradient-text">Explore</span>
            <span className="text-muted-foreground font-normal text-base sm:text-lg ml-1">
              ✦ {activityText}
            </span>
          </h1>
          {showFeaturedLabel && (
            <p className="text-sm text-muted-foreground mt-1">
              ✨ Featured Creations — From the Studio
            </p>
          )}
          {!showFeaturedLabel && (
            <p className="text-sm text-muted-foreground mt-1">
              Inspiration → Curiosity → Creation
            </p>
          )}
        </div>
        <Link href="/login" className="shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="rounded-xl border-white/15 bg-white/[0.04] hover:bg-white/[0.08] text-foreground"
          >
            Publish your work
          </Button>
        </Link>
      </motion.div>

      {/* Filter pills — instant apply, horizontal scroll */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-6 scrollbar-hide">
        {FILTER_PILLS.map((pill) => {
          const isSortActive = pill.sort ? sort === pill.sort : false;
          const isStyleActive = pill.style ? styleFilter === pill.style : false;
          const isActive = isSortActive || isStyleActive;
          return (
            <button
              key={pill.id}
              type="button"
              onClick={() => applyPillClick(pill)}
              className={cn(
                "shrink-0 px-4 py-2 rounded-full text-sm font-medium border transition-all whitespace-nowrap",
                "border-white/[0.08] bg-white/[0.04] hover:bg-white/[0.08] text-muted-foreground hover:text-foreground",
                isActive && "explore-pill-active text-foreground"
              )}
            >
              {pill.emoji} {pill.label}
            </button>
          );
        })}
      </div>

      {filteredItems.length === 0 && !loadingMore ? (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="explore-empty-state text-center py-20 rounded-2xl border border-white/[0.06] bg-white/[0.02]"
        >
          <p className="text-lg font-medium text-foreground mb-1">
            ✨ The community gallery is warming up
          </p>
          <p className="text-muted-foreground mb-6">Be among the first creators here.</p>
          <Link href="/generate">
            <Button className="rounded-xl bg-primary text-white px-6">
              <Sparkles className="h-4 w-4 mr-2" />
              Create Something
            </Button>
          </Link>
        </motion.div>
      ) : (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="explore-masonry"
          >
            {filteredItems.map((item, idx) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: Math.min(idx * 0.02, 0.2) }}
                className="explore-card group relative rounded-2xl overflow-hidden glass-card border border-white/[0.06] hover:border-white/15 cursor-pointer break-inside-avoid mb-4"
                onClick={() => openDetail(item)}
              >
                <div className="aspect-square relative overflow-hidden">
                  {item.url ? (
                    <Image
                      src={item.url}
                      alt={item.prompt || "Gallery image"}
                      fill
                      className="object-cover transition-transform duration-200 group-hover:scale-[1.03]"
                      unoptimized
                      sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
                    />
                  ) : (
                    <div className="w-full h-full bg-muted flex items-center justify-center">
                      <span className="text-muted-foreground text-sm">No image</span>
                    </div>
                  )}
                  {/* Hover overlay — creator, prompt, Remix, likes, style */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex flex-col justify-end p-4">
                    <p className="text-white/90 text-xs font-medium">
                      👤 {item.user?.name ?? "Creator"}
                    </p>
                    <p className="text-white/90 text-xs line-clamp-2 mt-0.5">{item.prompt}</p>
                    <div className="flex items-center gap-2 mt-3 flex-wrap">
                      <Link
                        href={remixUrl(item)}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/90 hover:bg-primary text-white text-xs font-medium"
                      >
                        <Sparkles className="h-3.5 w-3.5" />
                        Remix Prompt
                      </Link>
                      <span className="flex items-center gap-1 text-white/90 text-xs">
                        <Heart className="h-3.5 w-3.5" />
                        {likeCounts[item.id] ?? item.likesCount}
                      </span>
                      {(item.style || item.category) && (
                        <span className="text-white/70 text-xs">
                          🔁 {item.style || item.category}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>

          {nextCursor && !showFeaturedLabel && (
            <div className="flex justify-center mt-8">
              <Button
                variant="outline"
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-xl glass-card border-white/[0.06]"
              >
                {loadingMore ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Load more"
                )}
              </Button>
            </div>
          )}
        </>
      )}

      {selected && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => !reportOpen && setSelected(null)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25 }}
            className="relative max-w-4xl w-full glass-card rounded-2xl overflow-hidden max-h-[90vh] flex flex-col border border-white/10 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-3 right-3 z-10 bg-black/50 hover:bg-black/70 text-white"
              onClick={() => { setReportOpen(false); setSelected(null); }}
            >
              <X className="h-5 w-5" />
            </Button>

            <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
              <div className="relative w-full md:w-1/2 aspect-square bg-black shrink-0">
                {selected.url ? (
                  <Image
                    src={selected.url}
                    alt={selected.prompt || "Gallery image"}
                    fill
                    className="object-contain"
                    unoptimized
                  />
                ) : null}
              </div>
              <div className="p-4 md:p-6 flex flex-col flex-1 overflow-hidden">
                <p className="text-sm text-muted-foreground mb-2">{selected.prompt}</p>
                <div className="flex items-center gap-2 mb-4 flex-wrap">
                  <Link
                    href={remixUrl(selected)}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-primary/90 hover:bg-primary text-white text-sm font-medium"
                  >
                    <Sparkles className="h-4 w-4" />
                    Remix Prompt
                  </Link>
                  <button
                    className="flex items-center gap-1 text-sm"
                    onClick={() => toggleLike(selected.id)}
                  >
                    <Heart
                      className={cn(
                        "h-4 w-4",
                        liked[selected.id] && "fill-red-500 text-red-500"
                      )}
                    />
                    {likeCounts[selected.id] ?? selected.likesCount}
                  </button>
                  <span className="flex items-center gap-1 text-sm text-muted-foreground">
                    <MessageCircle className="h-4 w-4" />
                    {selected.commentsCount}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => share(selected)}
                  >
                    <Share2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground"
                    onClick={() => setReportOpen(true)}
                  >
                    <Flag className="h-4 w-4" />
                  </Button>
                </div>

                <div className="flex-1 overflow-y-auto border-t border-white/[0.08] pt-4">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Comments</p>
                  {commentsLoading ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <ul className="space-y-2 mb-4">
                      {comments.map((c) => (
                        <li key={c.id} className="text-sm">
                          <span className="font-medium">{c.user?.name ?? "Anonymous"}</span>
                          <span className="text-muted-foreground"> — {c.body}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="flex gap-2">
                    <Input
                      placeholder="Add a comment..."
                      value={newComment}
                      onChange={(e) => setNewComment(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && submitComment()}
                    />
                    <Button size="sm" onClick={submitComment}>
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}

      {reportOpen && selected && (
        <div className="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-card rounded-2xl p-6 max-w-sm w-full border border-white/10"
          >
            <h3 className="font-semibold mb-2">Report this image</h3>
            <select
              value={reportReason}
              onChange={(e) => setReportReason(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm mb-2"
            >
              <option value="NSFW">NSFW</option>
              <option value="HATE">Hate</option>
              <option value="VIOLENCE">Violence</option>
              <option value="CELEBRITY">Celebrity</option>
              <option value="COPYRIGHT">Copyright</option>
              <option value="OTHER">Other</option>
            </select>
            <textarea
              placeholder="Optional details"
              value={reportDesc}
              onChange={(e) => setReportDesc(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm min-h-[80px] mb-4"
              maxLength={500}
            />
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setReportOpen(false)} className="rounded-xl">
                Cancel
              </Button>
              <Button onClick={submitReport} className="rounded-xl btn-premium text-white">Submit report</Button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
