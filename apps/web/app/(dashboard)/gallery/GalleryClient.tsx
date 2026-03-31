"use client";

import Link from "next/link";
import NextImage from "next/image";
import { motion } from "framer-motion";
import {
  FolderOpen,
  Plus,
  Download,
  Trash2,
  Star,
  Grid,
  List,
  Loader2,
  Expand,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GradientButton } from "@/components/ui/gradient-button";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  fetchGenerations,
  updateGeneration,
  deleteGeneration,
  type GenerationListItem,
} from "@/lib/api";
import { ImageDetailModal, type GenerationImage } from "@/components/gallery/image-detail-modal";

function formatDate(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = (now.getTime() - d.getTime()) / 60000;
  if (diff < 1) return "Just now";
  if (diff < 60) return `${Math.floor(diff)} min ago`;
  if (diff < 1440) return `${Math.floor(diff / 60)} hr ago`;
  return d.toLocaleDateString();
}

function toGenerationImage(g: GenerationListItem, url: string): GenerationImage {
  return {
    id: g.id,
    url,
    prompt: g.prompt,
    mode: g.mode,
    identity: g.identity,
    scores: g.scores,
    createdAt: g.createdAt,
    favorite: g.selectedUrl === url,
  };
}

export default function GalleryClient() {
  const [view, setView] = useState<"grid" | "list">("grid");
  const [selectedImage, setSelectedImage] = useState<GenerationImage | null>(null);
  const queryClient = useQueryClient();

  const { data: generations = [], isLoading } = useQuery({
    queryKey: ["generations"],
    queryFn: fetchGenerations,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteGeneration,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["generations"] }),
  });

  const starMutation = useMutation({
    mutationFn: ({ id, selectedUrl }: { id: string; selectedUrl: string }) =>
      updateGeneration(id, { selectedUrl }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["generations"] }),
  });

  const images: { id: string; url: string; mode: string; date: string; g: GenerationListItem }[] =
    generations.map((g) => {
      const url = g.selectedUrl ?? g.outputUrls[0] ?? "";
      return {
        id: g.id,
        url,
        mode: g.mode.charAt(0).toUpperCase() + g.mode.slice(1),
        date: formatDate(g.createdAt),
        g,
      };
    });

  return (
    <>
      <div className="max-w-6xl">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-xl bg-gradient-to-r from-accent to-purple-400">
                <FolderOpen className="w-6 h-6 text-primary-foreground" />
              </div>
              <h1 className="text-3xl font-bold">Gallery</h1>
            </div>
            <p className="text-muted-foreground">
              Your generated portraits. Click to view details, download, or manage.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1 p-1 rounded-lg bg-muted/50">
              <button
                onClick={() => setView("grid")}
                className={cn(
                  "p-2 rounded-md transition-colors",
                  view === "grid" ? "bg-background shadow-sm" : "hover:bg-muted"
                )}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setView("list")}
                className={cn(
                  "p-2 rounded-md transition-colors",
                  view === "list" ? "bg-background shadow-sm" : "hover:bg-muted"
                )}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
            <GradientButton asChild>
              <Link href="/generate">
                <Plus className="w-4 h-4" />
                New Portrait
              </Link>
            </GradientButton>
          </div>
        </motion.div>

        {/* Gallery Grid */}
        {isLoading ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card rounded-2xl border border-border/50 p-12 flex flex-col items-center justify-center gap-4"
          >
            <Loader2 className="w-12 h-12 text-primary animate-spin" />
            <p className="text-muted-foreground">Loading gallery...</p>
          </motion.div>
        ) : images.length > 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className={cn(
              "grid gap-4",
              view === "grid" ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3" : "grid-cols-1"
            )}
          >
            {images.map((image, index) => (
              <motion.div
                key={image.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                className="group relative glass-card rounded-2xl border border-border/50 overflow-hidden cursor-pointer"
                onClick={() => setSelectedImage(toGenerationImage(image.g, image.url))}
              >
                <div className={cn("relative", view === "grid" ? "aspect-square" : "aspect-video")}>
                  <NextImage
                    src={image.url}
                    alt={`Portrait ${image.id}`}
                    fill
                    className="object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />

                  {/* Hover overlay */}
                  <div className="absolute inset-0 flex items-end justify-between p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div>
                      <span className="inline-block px-2 py-1 rounded-full text-xs font-medium bg-primary/20 text-primary mb-1">
                        {image.mode}
                      </span>
                      <p className="text-xs text-muted-foreground">{image.date}</p>
                    </div>
                    <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                      {/* Expand to detail modal */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedImage(toGenerationImage(image.g, image.url));
                        }}
                        className="p-2 rounded-lg bg-background/80 hover:bg-background transition-colors"
                        title="View details"
                      >
                        <Expand className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          starMutation.mutate({ id: image.id, selectedUrl: image.url });
                        }}
                        className={cn(
                          "p-2 rounded-lg transition-colors",
                          image.g.selectedUrl === image.url
                            ? "bg-primary text-primary-foreground"
                            : "bg-background/80 hover:bg-background"
                        )}
                        title="Favourite"
                      >
                        <Star className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const a = document.createElement("a");
                          a.href = image.url;
                          a.download = `portrait-${image.id}.jpg`;
                          a.target = "_blank";
                          a.rel = "noopener";
                          a.click();
                        }}
                        className="p-2 rounded-lg bg-background/80 hover:bg-background transition-colors"
                        title="Download"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteMutation.mutate(image.id);
                        }}
                        disabled={deleteMutation.isPending}
                        className="p-2 rounded-lg bg-background/80 hover:bg-destructive/80 hover:text-destructive-foreground transition-colors disabled:opacity-50"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="glass-card rounded-2xl border border-border/50 p-12 text-center"
          >
            <FolderOpen className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">No portraits yet</h3>
            <p className="text-muted-foreground mb-6">
              Create your first AI portrait and it will appear here.
            </p>
            <GradientButton asChild>
              <Link href="/generate">
                <Plus className="w-4 h-4" />
                Create Your First Portrait
              </Link>
            </GradientButton>
          </motion.div>
        )}
      </div>

      {/* Image Detail Modal */}
      <ImageDetailModal
        image={selectedImage}
        isOpen={selectedImage !== null}
        onClose={() => setSelectedImage(null)}
        onDelete={(id) => {
          deleteMutation.mutate(id);
          setSelectedImage(null);
        }}
        onToggleFavorite={(id, url) => {
          starMutation.mutate({ id, selectedUrl: url });
        }}
      />
    </>
  );
}
