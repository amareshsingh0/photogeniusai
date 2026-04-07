/**
 * Quality Score Visualization
 *
 * Displays the 12-dimension quality breakdown + 10 Beast Standard gates
 * from the Quality Critic agent.
 */

"use client"

import { useState } from "react"

interface QualityDimension {
  score: number // 0-10
  reasoning: string
  weight: number // 0.0-1.0
  floor: number // minimum threshold
  below_floor: boolean
}

interface BeastGate {
  pass: boolean
  name: string
  criteria?: string
}

interface QualityScoreDisplayProps {
  overall: number // 0-10
  dimensionScores: Record<string, QualityDimension>
  beastGates: Record<string, BeastGate>
  verdict?: "APPROVED" | "REVISE" | "ESCALATE"
  className?: string
}

export function QualityScoreDisplay({
  overall,
  dimensionScores,
  beastGates,
  verdict = "APPROVED",
  className = "",
}: QualityScoreDisplayProps) {
  const [expandedDimension, setExpandedDimension] = useState<string | null>(null)

  const passedGates = Object.values(beastGates).filter((g) => g.pass).length
  const totalGates = Object.keys(beastGates).length

  // Sort dimensions by score (weakest first for visibility)
  const sortedDimensions = Object.entries(dimensionScores).sort(
    ([, a], [, b]) => a.score - b.score
  )

  return (
    <div className={`flex flex-col gap-6 rounded-xl border bg-card p-6 shadow-lg ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-card-foreground">Quality Assessment</h2>
          <p className="text-sm text-muted-foreground">12-Dimension Beast Standard Analysis</p>
        </div>
        <div className="flex items-center gap-3">
          {verdict === "APPROVED" && (
            <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-700">
              ✅ Approved
            </span>
          )}
          {verdict === "REVISE" && (
            <span className="rounded-full bg-yellow-100 px-3 py-1 text-sm font-semibold text-yellow-700">
              ⚠️ Needs Revision
            </span>
          )}
          {verdict === "ESCALATE" && (
            <span className="rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-700">
              🚨 Human Review
            </span>
          )}
        </div>
      </div>

      {/* Overall Score */}
      <div className="flex items-center gap-6">
        <div className="flex flex-col items-center">
          <CircularProgress value={overall} max={10} size={120} />
          <div className="mt-2 text-center">
            <div className="text-3xl font-bold text-card-foreground">{overall.toFixed(1)}</div>
            <div className="text-xs text-muted-foreground">Overall Score</div>
          </div>
        </div>

        <div className="flex-1">
          <div className="text-sm font-medium text-muted-foreground">Beast Standards</div>
          <div className="mt-1 text-2xl font-bold text-card-foreground">
            {passedGates}/{totalGates} Passed
          </div>
          <div className="mt-2">
            <ProgressBar value={passedGates} max={totalGates} />
          </div>
        </div>
      </div>

      {/* Beast Gates */}
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-card-foreground">Beast Standard Gates</h3>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(beastGates).map(([id, gate]) => (
            <div
              key={id}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                gate.pass
                  ? "border-green-200 bg-green-50 text-green-700"
                  : "border-red-200 bg-red-50 text-red-700"
              }`}
            >
              <span className="text-lg">{gate.pass ? "✅" : "❌"}</span>
              <span className="font-medium">{gate.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 12 Dimensions */}
      <div className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-card-foreground">Quality Dimensions</h3>

        <div className="flex flex-col gap-2">
          {sortedDimensions.map(([dimName, dimData]) => (
            <div key={dimName} className="flex flex-col gap-2">
              {/* Dimension Bar */}
              <button
                onClick={() =>
                  setExpandedDimension(expandedDimension === dimName ? null : dimName)
                }
                className="flex w-full items-center gap-3 rounded-lg border bg-background p-3 text-left transition-all hover:border-primary hover:shadow-sm"
              >
                {/* Name + Weight */}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium capitalize text-card-foreground">
                      {dimName.replace(/_/g, " ")}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({(dimData.weight * 100).toFixed(0)}% weight)
                    </span>
                    {dimData.below_floor && (
                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                        Below Floor
                      </span>
                    )}
                  </div>
                </div>

                {/* Score Bar */}
                <div className="w-48">
                  <div className="flex items-center gap-2">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
                      <div
                        className={`h-full transition-all ${getBarColor(dimData.score)}`}
                        style={{ width: `${(dimData.score / 10) * 100}%` }}
                      />
                    </div>
                    <span className={`text-sm font-bold ${getScoreColor(dimData.score)}`}>
                      {dimData.score.toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Expand Icon */}
                <span className="text-muted-foreground">
                  {expandedDimension === dimName ? "▼" : "▶"}
                </span>
              </button>

              {/* Expanded Reasoning */}
              {expandedDimension === dimName && (
                <div className="ml-6 rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
                  {dimData.reasoning}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * Compact inline quality score badge
 */
export function QualityScoreBadge({
  score,
  className = "",
}: {
  score: number
  className?: string
}) {
  const grade = getGrade(score)

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ${getGradeBadgeColor(
        grade
      )} ${className}`}
    >
      <span>{getGradeEmoji(grade)}</span>
      <span>
        {score.toFixed(1)} ({grade})
      </span>
    </span>
  )
}

/**
 * Minimal quality indicator (just the circle + score)
 */
export function QualityIndicator({ score, size = 60 }: { score: number; size?: number }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <CircularProgress value={score} max={10} size={size} />
      <span className="text-xs font-medium text-muted-foreground">{score.toFixed(1)}/10</span>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// Helper Components
// ══════════════════════════════════════════════════════════════════════════════

function CircularProgress({ value, max, size = 100 }: { value: number; max: number; size?: number }) {
  const percentage = (value / max) * 100
  const circumference = 2 * Math.PI * 45 // radius = 45
  const offset = circumference - (percentage / 100) * circumference

  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      {/* Background circle */}
      <circle
        cx="50"
        cy="50"
        r="45"
        fill="none"
        stroke="#e5e7eb"
        strokeWidth="8"
      />
      {/* Progress circle */}
      <circle
        cx="50"
        cy="50"
        r="45"
        fill="none"
        stroke={getCircleColor(percentage)}
        strokeWidth="8"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 50 50)"
        style={{ transition: "stroke-dashoffset 0.5s ease" }}
      />
    </svg>
  )
}

function ProgressBar({ value, max }: { value: number; max: number }) {
  const percentage = (value / max) * 100

  return (
    <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200">
      <div
        className={`h-full transition-all ${getBarColor((percentage / 100) * 10)}`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
// Helper Functions
// ══════════════════════════════════════════════════════════════════════════════

function getBarColor(score: number): string {
  if (score >= 9) return "bg-green-500"
  if (score >= 8.5) return "bg-emerald-500"
  if (score >= 8) return "bg-blue-500"
  if (score >= 7) return "bg-yellow-500"
  if (score >= 6) return "bg-orange-500"
  return "bg-red-500"
}

function getCircleColor(percentage: number): string {
  if (percentage >= 90) return "#10b981" // green-500
  if (percentage >= 85) return "#059669" // emerald-600
  if (percentage >= 80) return "#3b82f6" // blue-500
  if (percentage >= 70) return "#eab308" // yellow-500
  if (percentage >= 60) return "#f97316" // orange-500
  return "#ef4444" // red-500
}

function getScoreColor(score: number): string {
  if (score >= 9) return "text-green-600"
  if (score >= 8.5) return "text-emerald-600"
  if (score >= 8) return "text-blue-600"
  if (score >= 7) return "text-yellow-600"
  if (score >= 6) return "text-orange-600"
  return "text-red-600"
}

function getGrade(score: number): string {
  if (score >= 9.5) return "S"
  if (score >= 9.0) return "A+"
  if (score >= 8.5) return "A"
  if (score >= 8.0) return "B+"
  if (score >= 7.5) return "B"
  if (score >= 7.0) return "C+"
  if (score >= 6.5) return "C"
  if (score >= 6.0) return "D"
  return "F"
}

function getGradeEmoji(grade: string): string {
  if (grade === "S" || grade === "A+") return "🏆"
  if (grade === "A" || grade === "B+") return "⭐"
  if (grade === "B" || grade === "C+") return "✨"
  if (grade === "C") return "👍"
  return "⚠️"
}

function getGradeBadgeColor(grade: string): string {
  if (grade === "S" || grade === "A+") return "bg-purple-100 text-purple-700"
  if (grade === "A") return "bg-green-100 text-green-700"
  if (grade === "B+" || grade === "B") return "bg-blue-100 text-blue-700"
  if (grade === "C+" || grade === "C") return "bg-yellow-100 text-yellow-700"
  return "bg-red-100 text-red-700"
}
