"use client";

import { useCallback, useState } from "react";

export type Toast = { id: string; message: string; variant?: "default" | "destructive" };

/**
 * Simple toast state. Replace with sonner or radix toast when using shadcn toaster.
 */
export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, variant: "default" | "destructive" = "default") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3000);
  }, []);

  return { toasts, toast };
}
