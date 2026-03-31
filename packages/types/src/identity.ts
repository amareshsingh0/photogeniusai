/**
 * Identity types for PhotoGenius AI
 */

export type IdentityStatus = "pending" | "training" | "ready" | "failed";

export interface Identity {
  id: string;
  userId: string;
  name?: string;
  imageUrls: string[];
  status: IdentityStatus;
  createdAt: Date;
}
