"use client";

import { QueryClientProvider, QueryClient } from "@tanstack/react-query"
import { useState } from "react";
import { Toaster } from "@/components/ui/toaster";

function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000,
        refetchOnWindowFocus: false,
      },
    },
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  // Minimal providers: no next-themes (avoids hydration/first-paint delay). Dark theme via CSS only.
  return (
    <QueryProvider>
      {children}
      <Toaster />
    </QueryProvider>
  );
}
