"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { saveGeneration } from "@/lib/api";

/**
 * Hook for saving a generation. Invalidates generations query on success.
 */
export function useGeneration() {
  const qc = useQueryClient();

  const save = useMutation({
    mutationFn: saveGeneration,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["generations"] });
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
  });

  return { save };
}
