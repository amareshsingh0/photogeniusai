"use client";

import { useState } from "react";

/**
 * Consent flow. Checkboxes and submit for training/generation.
 */
export function ConsentFlow({
  onAccept,
  loading = false,
}: {
  onAccept: (checked: boolean[]) => void;
  loading?: boolean;
}) {
  const [a, setA] = useState(false);
  const [b, setB] = useState(false);
  const [c, setC] = useState(false);

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={a} onChange={(e) => setA(e.target.checked)} />
        <span>I consent to use my photos for AI training.</span>
      </label>
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={b} onChange={(e) => setB(e.target.checked)} />
        <span>I agree to the terms of service.</span>
      </label>
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={c} onChange={(e) => setC(e.target.checked)} />
        <span>I am 18 or older.</span>
      </label>
      <button
        type="button"
        disabled={!a || !b || !c || loading}
        onClick={() => onAccept([a, b, c])}
        className="rounded-md bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50"
      >
        {loading ? "Submitting…" : "Accept"}
      </button>
    </div>
  );
}
