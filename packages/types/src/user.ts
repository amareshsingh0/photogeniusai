/**
 * User types for PhotoGenius AI
 */

export interface User {
  id: string;
  email: string;
  name?: string;
  avatarUrl?: string;
  credits: number;
  createdAt: Date;
}
