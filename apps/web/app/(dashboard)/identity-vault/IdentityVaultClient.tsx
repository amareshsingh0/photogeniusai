"use client";

import { useState, useCallback, useRef } from "react";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";
import {
  UserCircle,
  Upload,
  Plus,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Trash2,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GradientButton } from "@/components/ui/gradient-button";
import { cn } from "@/lib/utils";
import {
  fetchSession,
  fetchIdentities,
  uploadFile,
  createIdentity,
  type IdentityListItem,
} from "@/lib/api";

interface UploadedImage {
  id: string;
  file: File;
  preview: string;
  status: "uploading" | "ready" | "error";
}

export default function IdentityVaultClient() {
  const [dragging, setDragging] = useState(false);
  const [images, setImages] = useState<UploadedImage[]>([]);
  const [identityName, setIdentityName] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const { data: session } = useQuery({
    queryKey: ["session"],
    queryFn: fetchSession,
  });
  const { data: identities = [] } = useQuery({
    queryKey: ["identities"],
    queryFn: fetchIdentities,
    enabled: !!session?.userId,
  });

  const createMutation = useMutation({
    mutationFn: createIdentity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["identities"] });
      setImages([]);
      setIdentityName("");
      setSaveError(null);
    },
    onError: (err) => setSaveError(err instanceof Error ? err.message : "Save failed"),
  });

  const handleFiles = useCallback((files: FileList | File[]) => {
    const imageFiles = Array.from(files).filter((f) => f.type.startsWith("image/"));
    
    const newImages: UploadedImage[] = imageFiles.map((file) => ({
      id: Math.random().toString(36).substr(2, 9),
      file,
      preview: URL.createObjectURL(file),
      status: "ready" as const,
    }));
    
    setImages((prev) => [...prev, ...newImages]);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const onDragLeave = useCallback(() => setDragging(false), []);

  const removeImage = useCallback((id: string) => {
    setImages((prev) => {
      const img = prev.find((i) => i.id === id);
      if (img) URL.revokeObjectURL(img.preview);
      return prev.filter((i) => i.id !== id);
    });
  }, []);

  const handleSaveIdentity = useCallback(async () => {
    setSaveError(null);
    if (!session?.userId) {
      setSaveError("Sign in to save identities.");
      return;
    }
    if (images.length < 5) return;
    const urls: string[] = [];
    for (const img of images) {
      if (img.status !== "ready") continue;
      try {
        const { url } = await uploadFile(img.file);
        urls.push(url);
      } catch (e) {
        setSaveError(e instanceof Error ? e.message : "Upload failed");
        return;
      }
    }
    createMutation.mutate({ name: identityName.trim() || undefined, imageUrls: urls });
  }, [session?.userId, images, identityName, createMutation]);

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-xl bg-gradient-to-r from-secondary to-pink-400">
            <UserCircle className="w-6 h-6 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-bold">Identity Vault</h1>
        </div>
        <p className="text-muted-foreground">
          Upload reference photos to create face-consistent AI portraits. 
          We recommend 5-20 clear photos for best results.
        </p>
      </motion.div>

      {/* Info Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="glass-card rounded-2xl border border-primary/20 bg-primary/5 p-6 mb-6"
      >
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-primary mt-0.5" />
          <div>
            <h3 className="font-semibold mb-1">How Identity Vault Works</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Upload 5-20 clear photos of yourself</li>
              <li>• Our AI trains a personalized model (~5 minutes)</li>
              <li>• Generate face-consistent portraits in any style</li>
              <li>• Your data is encrypted and never shared</li>
            </ul>
          </div>
        </div>
      </motion.div>

      {/* Identity Name */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
        className="mb-6"
      >
        <label className="block text-sm font-medium mb-2">Identity Name</label>
        <input
          type="text"
          value={identityName}
          onChange={(e) => setIdentityName(e.target.value)}
          placeholder="e.g., My Professional Look"
          className="w-full max-w-md h-12 px-4 rounded-xl bg-muted/50 border border-border/50 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-colors"
        />
      </motion.div>

      {/* Upload Zone */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="mb-6"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
          className="hidden"
        />
        
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "glass-card rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all duration-300",
            dragging 
              ? "border-primary bg-primary/10 scale-[1.02]" 
              : "border-border/50 hover:border-primary/50 hover:bg-muted/30"
          )}
        >
          <div className={cn(
            "w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center transition-colors",
            dragging ? "bg-primary/20" : "bg-muted"
          )}>
            <Upload className={cn("w-8 h-8", dragging ? "text-primary" : "text-muted-foreground")} />
          </div>
          <h3 className="font-semibold mb-2">
            {dragging ? "Drop your photos here" : "Upload Reference Photos"}
          </h3>
          <p className="text-sm text-muted-foreground mb-4">
            Drag & drop photos here, or click to browse
          </p>
          <p className="text-xs text-muted-foreground">
            Supports JPG, PNG, WebP • Max 10MB per image • 5-20 photos recommended
          </p>
        </div>
      </motion.div>

      {/* Uploaded Images */}
      <AnimatePresence>
        {images.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="mb-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">{images.length} photo{images.length !== 1 && "s"} selected</h3>
              <button
                onClick={() => setImages([])}
                className="text-sm text-muted-foreground hover:text-destructive transition-colors"
              >
                Clear all
              </button>
            </div>
            
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-3">
              {images.map((img, index) => (
                <motion.div
                  key={img.id}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ duration: 0.2, delay: index * 0.05 }}
                  className="relative group aspect-square rounded-xl overflow-hidden bg-muted"
                >
                  <Image
                    src={img.preview}
                    alt={`Reference ${index + 1}`}
                    fill
                    className="object-cover"
                  />
                  <div className="absolute inset-0 bg-background/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeImage(img.id);
                      }}
                      className="p-2 rounded-lg bg-destructive text-destructive-foreground"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  {img.status === "ready" && (
                    <div className="absolute top-2 right-2 p-1 rounded-full bg-primary text-primary-foreground">
                      <CheckCircle2 className="w-3 h-3" />
                    </div>
                  )}
                </motion.div>
              ))}
              
              {/* Add More Button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="aspect-square rounded-xl border-2 border-dashed border-border/50 hover:border-primary/50 hover:bg-muted/30 transition-colors flex flex-col items-center justify-center gap-1"
              >
                <Plus className="w-6 h-6 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Add more</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Save Button */}
      {saveError && (
        <p className="text-sm text-destructive mb-2">{saveError}</p>
      )}
      {images.length >= 5 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex flex-wrap items-center gap-4"
        >
          <GradientButton
            onClick={handleSaveIdentity}
            size="lg"
            disabled={!identityName.trim() || !session?.userId || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <CheckCircle2 className="w-5 h-5" />
            )}
            Save Identity & Train Model
          </GradientButton>
          {!session?.userId && (
            <p className="text-sm text-muted-foreground">Sign in to save identities.</p>
          )}
          {session?.userId && (
            <p className="text-sm text-muted-foreground">Training takes ~5 minutes</p>
          )}
        </motion.div>
      )}

      {images.length > 0 && images.length < 5 && (
        <p className="text-sm text-muted-foreground">
          Add {5 - images.length} more photo{5 - images.length !== 1 && "s"} to enable training
        </p>
      )}

      {/* Saved identities */}
      {identities.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-10"
        >
          <h3 className="font-semibold mb-4">Your identities</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {identities.map((identity) => (
              <div
                key={identity.id}
                className="glass-card rounded-xl border border-border/50 overflow-hidden aspect-square relative"
              >
                {identity.imageUrls[0] && (
                  <Image
                    src={identity.imageUrls[0]}
                    alt={identity.name ?? "Identity"}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                )}
                <div className="absolute bottom-0 left-0 right-0 p-2 bg-background/80 text-xs truncate">
                  {identity.name || "Unnamed"} · {identity.status}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
