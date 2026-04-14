"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { cn } from "@/lib/utils";
import RatingModal from "./rating-modal";

interface ImageRatingProps {
  generationId: string;
  imageUrl: string;
  currentRating?: number;
  onRatingSubmit?: (rating: number, reason: string) => void;
}

export default function ImageRating({
  generationId,
  imageUrl,
  currentRating,
  onRatingSubmit,
}: ImageRatingProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [rating, setRating] = useState(currentRating || 0);

  const handleSubmit = async (newRating: number, reason: string) => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://api.creatives.bimoraai.com";
      const res = await fetch(`${apiUrl}/api/v1/rate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          generationId,
          rating: newRating,
          reason: reason || undefined,
        }),
      });

      if (!res.ok) throw new Error("Failed to submit rating");

      setRating(newRating);
      onRatingSubmit?.(newRating, reason);
    } catch (error) {
      console.error("Error submitting rating:", error);
      throw error;
    }
  };

  return (
    <>
      {/* Rating Display/Trigger */}
      <div className="flex items-center gap-1">
        {rating > 0 ? (
          // Show current rating
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((star) => (
              <Star
                key={star}
                className={cn(
                  "w-4 h-4",
                  star <= rating ? "fill-yellow-500 text-yellow-500" : "text-zinc-600"
                )}
              />
            ))}
            <button
              onClick={() => setIsModalOpen(true)}
              className="ml-2 text-xs text-zinc-400 hover:text-white underline"
            >
              Change
            </button>
          </div>
        ) : (
          // Rate button
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-sm font-medium transition-colors"
          >
            <Star className="w-4 h-4" />
            Rate this
          </button>
        )}
      </div>

      {/* Rating Modal */}
      <RatingModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleSubmit}
        imageUrl={imageUrl}
      />
    </>
  );
}
