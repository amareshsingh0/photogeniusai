import { prisma } from "@/lib/db";
import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PhotoGenius AI Gallery",
  description: "AI-generated portrait from PhotoGenius",
  robots: "noindex, nofollow",
};

export default async function EmbedPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const { id } = await searchParams;
  if (!id) {
    return (
      <div className="min-h-[200px] flex items-center justify-center bg-muted/30 rounded-lg p-4">
        <p className="text-sm text-muted-foreground">No image selected. Use ?id=...</p>
      </div>
    );
  }

  const gen = await prisma.generation.findFirst({
    where: {
      id,
      isPublic: true,
      isDeleted: false,
      galleryModeration: "APPROVED",
    },
    select: {
      id: true,
      originalPrompt: true,
      selectedOutputUrl: true,
      outputUrls: true,
      galleryLikesCount: true,
    },
  }).catch(() => null);

  if (!gen) {
    return (
      <div className="min-h-[200px] flex items-center justify-center bg-muted/30 rounded-lg p-4">
        <p className="text-sm text-muted-foreground">Image not found or not public.</p>
      </div>
    );
  }

  const url = gen.selectedOutputUrl ?? (Array.isArray(gen.outputUrls) ? (gen.outputUrls[0] as string) : null);

  return (
    <div className="max-w-md mx-auto rounded-xl overflow-hidden border border-border/50 bg-card shadow-lg">
      {url ? (
        <div className="relative aspect-square">
          <Image src={url} alt={gen.originalPrompt || "Gallery image"} fill className="object-cover" unoptimized />
        </div>
      ) : (
        <div className="aspect-square bg-muted flex items-center justify-center">No image</div>
      )}
      <div className="p-3">
        <p className="text-sm text-foreground line-clamp-2">{gen.originalPrompt}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {gen.galleryLikesCount ?? 0} likes · PhotoGenius AI
        </p>
        <Link
          href={`${process.env.NEXT_PUBLIC_APP_URL || ""}/explore?highlight=${gen.id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-primary hover:underline mt-1 inline-block"
        >
          View on PhotoGenius →
        </Link>
      </div>
    </div>
  );
}
