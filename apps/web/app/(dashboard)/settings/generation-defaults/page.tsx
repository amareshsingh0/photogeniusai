"use client"

import { GenerationDefaults } from "@/components/settings/generation-defaults"

export default function GenerationDefaultsPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-8 pb-24 space-y-6">
      <div>
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">Generation Defaults</h1>
        <p className="mt-1 text-sm text-white/50">Set default style, aspect ratio, and quality options for image generation.</p>
      </div>
      <GenerationDefaults />
    </div>
  )
}
