import { MetadataRoute } from "next";
import { prisma } from "@/lib/db";

const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://photogenius.ai";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    { url: baseUrl, lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    { url: `${baseUrl}/explore`, lastModified: new Date(), changeFrequency: "hourly", priority: 0.9 },
    { url: `${baseUrl}/login`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
    { url: `${baseUrl}/signup`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
  ];

  let galleryPages: MetadataRoute.Sitemap = [];
  try {
    const ids = await prisma.generation.findMany({
      where: { isPublic: true, isDeleted: false, galleryModeration: "APPROVED" },
      select: { id: true, updatedAt: true },
      take: 500,
      orderBy: { publishedAt: "desc" },
    });
    galleryPages = ids.map((g) => ({
      url: `${baseUrl}/explore?highlight=${g.id}`,
      lastModified: g.updatedAt,
      changeFrequency: "weekly" as const,
      priority: 0.6,
    }));
  } catch {
    // ignore
  }

  return [...staticPages, ...galleryPages];
}
