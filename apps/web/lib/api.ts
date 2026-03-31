/**
 * Shared API helpers for Next.js route handlers.
 */

export interface GenerationListItem {
  id: string;
  prompt: string;
  mode: string;
  preset?: string;
  previewUrl?: string;
  outputUrls: string[];
  selectedUrl?: string;
  status: string;
  createdAt: string;
  scores?: {
    face_match: number;
    aesthetic: number;
    technical: number;
    total: number;
  };
  identity?: {
    id: string;
    name: string;
  };
}

export interface DashboardStats {
  credits: number;
  imagesGenerated: number;
  identitiesCount: number;
}

export async function fetchGenerations(): Promise<GenerationListItem[]> {
  const r = await fetch("/api/generations", { cache: "no-store" });
  if (!r.ok) throw new Error("Failed to fetch generations");
  return r.json();
}

export async function saveGeneration(body: {
  prompt: string;
  mode: string;
  preset?: string;
  previewUrl?: string;
  outputUrls: string[];
  selectedUrl?: string;
  qualityScore?: number;
  faceMatchPct?: number;
  aestheticScore?: number;
  identityId?: string;
}): Promise<void> {
  const r = await fetch("/api/generations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error((data as { error?: string }).error ?? "Failed to save");
  }
}

export async function updateGeneration(
  id: string,
  patch: { selectedUrl?: string }
): Promise<void> {
  const r = await fetch(`/api/generations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error("Failed to update");
}

export async function deleteGeneration(id: string): Promise<void> {
  const r = await fetch(`/api/generations/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("Failed to delete");
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const r = await fetch("/api/dashboard/stats", { cache: "no-store" });
  if (!r.ok) throw new Error("Failed to fetch stats");
  return r.json();
}

export async function fetchSession(): Promise<{ userId: string | null }> {
  const r = await fetch("/api/auth/session", { cache: "no-store" });
  if (!r.ok) return { userId: null };
  return r.json();
}

export interface IdentityListItem {
  id: string;
  name?: string;
  imageUrls: string[];
  status: string;
  createdAt: string;
}

export async function fetchIdentities(): Promise<IdentityListItem[]> {
  const r = await fetch("/api/identities", { cache: "no-store" });
  if (!r.ok) throw new Error("Failed to fetch identities");
  return r.json();
}

export async function uploadFile(file: File): Promise<{ url: string }> {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body: form });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error((data as { error?: string }).error ?? "Upload failed");
  }
  return r.json();
}

export async function createIdentity(body: {
  name?: string;
  imageUrls: string[];
}): Promise<IdentityListItem> {
  const r = await fetch("/api/identities", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error((data as { error?: string }).error ?? "Failed to create identity");
  }
  return r.json();
}

export async function validatePhotos(photos: File[]): Promise<{
  valid: boolean;
  errors: string[];
  photoCount: number;
}> {
  const formData = new FormData();
  photos.forEach((photo) => {
    formData.append("photos", photo);
  });

  const r = await fetch("/api/identities/validate", {
    method: "POST",
    body: formData,
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error((data as { error?: string }).error ?? "Validation failed");
  }
  return r.json();
}

export async function startTraining(identityId: string): Promise<{
  success: boolean;
  message: string;
  identityId?: string;
}> {
  const r = await fetch(`/api/identities/${identityId}/train`, {
    method: "POST",
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error((data as { message?: string }).message ?? "Failed to start training");
  }
  return r.json();
}
