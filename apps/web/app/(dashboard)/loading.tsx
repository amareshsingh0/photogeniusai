"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

export default function DashboardLoading() {
  const [showFallback, setShowFallback] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setShowFallback(true), 4000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3">
        {!showFallback ? (
          <>
            <div className="w-8 h-8 border-2 border-zinc-700 border-t-zinc-400 rounded-full animate-spin" />
            <p className="text-sm text-zinc-500">Loading...</p>
          </>
        ) : (
          <>
            <p className="text-sm text-zinc-500">Taking longer than usual.</p>
            <Link
              href="/"
              className="text-sm text-primary hover:underline"
            >
              Go to home
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
