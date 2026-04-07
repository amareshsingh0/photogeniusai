/**
 * Generation Profile Badge
 *
 * Displays detected generational/psychographic profile:
 * - Gen Z India (🔥)
 * - Millennial Parent (👨‍👩‍👧)
 * - Premium Buyer (💎)
 * - Achiever Urban (🚀)
 * - Mass Market India (🇮🇳)
 */

import { friendlyGeneration } from "@/lib/user-friendly-labels"

interface GenerationBadgeProps {
  generationProfile?: string
  className?: string
  showIcon?: boolean
  size?: "sm" | "md" | "lg"
}

export function GenerationBadge({
  generationProfile = "mass_market_india",
  className = "",
  showIcon = true,
  size = "md",
}: GenerationBadgeProps) {
  const { label, icon, color } = friendlyGeneration(generationProfile)

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs gap-1",
    md: "px-2.5 py-1 text-xs gap-1.5",
    lg: "px-3 py-1.5 text-sm gap-2",
  }

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${color} ${sizeClasses[size]} ${className}`}
    >
      {showIcon && <span>{icon}</span>}
      <span>{label}</span>
    </span>
  )
}

/**
 * Extended card with generation profile details
 */
interface GenerationCardProps {
  generationProfile?: string
  ageRange?: [number, number]
  psychographic?: string
  attentionBudget?: number // seconds
  preferredStyles?: string[]
  avoidStyles?: string[]
  className?: string
}

export function GenerationCard({
  generationProfile = "mass_market_india",
  ageRange,
  psychographic,
  attentionBudget,
  preferredStyles = [],
  avoidStyles = [],
  className = "",
}: GenerationCardProps) {
  const { label, icon, color } = friendlyGeneration(generationProfile)

  return (
    <div
      className={`flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm ${className}`}
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <h3 className="font-semibold text-card-foreground">{label}</h3>
          <p className="text-xs text-muted-foreground">Target Audience Profile</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2">
        {ageRange && (
          <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-2">
            <div className="text-xs font-medium text-muted-foreground">Age Range</div>
            <div className="text-sm font-semibold text-card-foreground">
              {ageRange[0]}-{ageRange[1]} years
            </div>
          </div>
        )}

        {psychographic && (
          <div className="flex flex-col gap-1 rounded-lg bg-muted/50 p-2">
            <div className="text-xs font-medium text-muted-foreground">Mindset</div>
            <div className="text-sm font-semibold text-card-foreground capitalize">
              {psychographic.replace(/_/g, " ")}
            </div>
          </div>
        )}

        {attentionBudget !== undefined && (
          <div className="col-span-2 flex flex-col gap-1 rounded-lg bg-muted/50 p-2">
            <div className="text-xs font-medium text-muted-foreground">Attention Budget</div>
            <div className="text-sm font-semibold text-card-foreground">
              {attentionBudget < 1
                ? `${(attentionBudget * 1000).toFixed(0)}ms`
                : `${attentionBudget.toFixed(1)}s`}{" "}
              to make impact
            </div>
          </div>
        )}
      </div>

      {/* Preferred Styles */}
      {preferredStyles.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-xs font-medium text-muted-foreground">Preferred Styles</div>
          <div className="flex flex-wrap gap-1.5">
            {preferredStyles.slice(0, 5).map((style) => (
              <span
                key={style}
                className="rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-700"
              >
                ✓ {style.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Avoid Styles */}
      {avoidStyles.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-xs font-medium text-muted-foreground">Avoid</div>
          <div className="flex flex-wrap gap-1.5">
            {avoidStyles.slice(0, 5).map((style) => (
              <span
                key={style}
                className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-700"
              >
                ✗ {style.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Compact inline badge with tooltip
 */
export function GenerationBadgeWithTooltip({
  generationProfile = "mass_market_india",
  description,
  className = "",
}: {
  generationProfile?: string
  description?: string
  className?: string
}) {
  const { label, icon, color } = friendlyGeneration(generationProfile)

  return (
    <div className={`group relative inline-flex ${className}`}>
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${color}`}
      >
        <span>{icon}</span>
        <span>{label}</span>
      </span>

      {description && (
        <div className="invisible absolute bottom-full left-1/2 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-gray-900 px-3 py-2 text-xs text-white opacity-0 shadow-lg transition-all group-hover:visible group-hover:opacity-100">
          {description}
          <div className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
        </div>
      )}
    </div>
  )
}

/**
 * Multiple generation badges (for multi-target campaigns)
 */
export function GenerationBadgeGroup({
  profiles = [],
  maxDisplay = 3,
  className = "",
}: {
  profiles: string[]
  maxDisplay?: number
  className?: string
}) {
  const displayProfiles = profiles.slice(0, maxDisplay)
  const remaining = profiles.length - maxDisplay

  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`}>
      {displayProfiles.map((profile) => (
        <GenerationBadge key={profile} generationProfile={profile} size="sm" />
      ))}

      {remaining > 0 && (
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
          +{remaining} more
        </span>
      )}
    </div>
  )
}
