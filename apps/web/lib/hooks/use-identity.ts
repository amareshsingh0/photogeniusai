"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchIdentities, createIdentity, fetchSession, uploadFile } from "@/lib/api";

/**
 * Hook for identities. Fetch list, create with uploads.
 */
export function useIdentity() {
  const qc = useQueryClient();

  const session = useQuery({ queryKey: ["session"], queryFn: fetchSession });
  const identities = useQuery({
    queryKey: ["identities"],
    queryFn: fetchIdentities,
    enabled: !!session.data?.userId,
  });

  const create = useMutation({
    mutationFn: async (payload: { name: string; imageUrls: string[] }) =>
      createIdentity({ name: payload.name, imageUrls: payload.imageUrls }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["identities"] }),
  });

  return { session, identities, create, uploadFile };
}
