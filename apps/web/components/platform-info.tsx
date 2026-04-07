/**
 * Platform Info Badge
 *
 * Displays platform-specific rules in user-friendly format:
 * - Attention window (how long users look)
 * - Dimensions (optimal size)
 * - Scroll-stop power (engagement potential)
 */

import { friendlyPlatform } from "@/lib/user-friendly-labels"

interface PlatformInfoProps {
  platform?: string
  attentionWindow?: number // seconds
  dimensions?: { w: number; h: number }
  scrollStopPower?: number // 0.0-1.0
  className?: string
}

export function PlatformInfo({
  platform = "general",
  attentionWindow,
  dimensions,
  scrollStopPower,
  className = "",
}: PlatformInfoProps) {
  const { label, icon } = friendlyPlatform(platform)

  return (
    <div
      className={`inline-flex flex-col gap-1 rounded-lg border bg-card p-3 text-sm ${className}`}
    >
      {/* Platform Header */}
      <div className="flex items-center gap-2">
        <span className="text-lg">{icon}</span>
        <span className="font-semibold text-card-foreground">{label}</span>
      </div>

      {/* Platform Stats */}
      <div className="flex flex-col gap-0.5 text-xs text-muted-foreground">
        {attentionWindow !== undefined && (
          <div className="flex items-center gap-1.5">
            <span className="opacity-60">⏱️</span>
            <span>
              {attentionWindow < 1 ? (
                <>{(attentionWindow * 1000).toFixed(0)}ms attention window</>
              ) : (
                <>{attentionWindow.toFixed(1)}s attention window</>
              )}
            </span>
          </div>
        )}

        {dimensions && (
          <div className="flex items-center gap-1.5">
            <span className="opacity-60">📐</span>
            <span>
              {dimensions.w} × {dimensions.h}px
            </span>
          </div>
        )}

        {scrollStopPower !== undefined && (
          <div className="flex items-center gap-1.5">
            <span className="opacity-60">🎯</span>
            <span>
              {getEngagementLevel(scrollStopPower)} engagement (
              {(scrollStopPower * 100).toFixed(0)}%)
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Compact badge version for inline display
 */
export function PlatformBadge({
  platform = "general",
  className = "",
}: {
  platform?: string
  className?: string
}) {
  const { label, icon } = friendlyPlatform(platform)

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 ${className}`}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </span>
  )
}

/**
 * Full info card with all platform details
 */
export function PlatformInfoCard({
  platform = "general",
  attentionWindow,
  dimensions,
  scrollStopPower,
  safeZones,
  copyLimits,
  className = "",
}: PlatformInfoProps & {
  safeZones?: { top: number; bottom: number; left: number; right: number }
  copyLimits?: { headline?: number; subheadline?: number; cta?: number; body?: number }
}) {
  const { label, icon } = friendlyPlatform(platform)

  return (
    <div
      className={`flex flex-col gap-4 rounded-xl border bg-card p-4 shadow-sm ${className}`}
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <h3 className="font-semibold text-card-foreground">{label}</h3>
          <p className="text-xs text-muted-foreground">Platform Specifications</p>
        </div>
      </div>

      {/* Specs Grid */}
      <div className="grid grid-cols-2 gap-3">
        {/* Attention Window */}
        {attentionWindow !== undefined && (
          <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-2.5">
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <span>⏱️</span>
              <span>Attention Window</span>
            </div>
            <div className="text-lg font-bold text-card-foreground">
              {attentionWindow < 1
                ? `${(attentionWindow * 1000).toFixed(0)}ms`
                : `${attentionWindow.toFixed(1)}s`}
            </div>
          </div>
        )}

        {/* Scroll Stop Power */}
        {scrollStopPower !== undefined && (
          <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-2.5">
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <span>🎯</span>
              <span>Engagement</span>
            </div>
            <div className="text-lg font-bold text-card-foreground">
              {getEngagementLevel(scrollStopPower)}
            </div>
          </div>
        )}

        {/* Dimensions */}
        {dimensions && (
          <div className="col-span-2 flex flex-col gap-1 rounded-lg bg-muted/50 p-2.5">
            <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <span>📐</span>
              <span>Optimal Dimensions</span>
            </div>
            <div className="text-lg font-bold text-card-foreground">
              {dimensions.w} × {dimensions.h}px
            </div>
          </div>
        )}
      </div>

      {/* Safe Zones */}
      {safeZones && (
        <div className="flex flex-col gap-2">
          <div className="text-xs font-medium text-muted-foreground">Safe Zones</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>Top: {safeZones.top}px</div>
            <div>Bottom: {safeZones.bottom}px</div>
            <div>Left: {safeZones.left}px</div>
            <div>Right: {safeZones.right}px</div>
          </div>
        </div>
      )}

      {/* Copy Limits */}
      {copyLimits && (
        <div className="flex flex-col gap-2">
          <div className="text-xs font-medium text-muted-foreground">Text Limits</div>
          <div className="flex flex-col gap-1 text-xs">
            {copyLimits.headline && <div>Headline: {copyLimits.headline} chars</div>}
            {copyLimits.subheadline && <div>Subheadline: {copyLimits.subheadline} chars</div>}
            {copyLimits.cta && <div>CTA: {copyLimits.cta} chars</div>}
            {copyLimits.body && <div>Body: {copyLimits.body} chars</div>}
          </div>
        </div>
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// Helper Functions
// ══════════════════════════════════════════════════════════════════════════════

function getEngagementLevel(scrollStopPower: number): string {
  if (scrollStopPower >= 0.8) return "Very High"
  if (scrollStopPower >= 0.6) return "High"
  if (scrollStopPower >= 0.4) return "Medium"
  if (scrollStopPower >= 0.2) return "Low"
  return "Very Low"
}
