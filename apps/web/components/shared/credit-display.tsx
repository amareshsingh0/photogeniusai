"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Coins, Zap, TrendingUp, AlertCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"

interface CreditDisplayProps {
  credits: number
  monthlyUsage?: number
  monthlyLimit?: number
  showProgress?: boolean
  showUpgrade?: boolean
  className?: string
  variant?: "default" | "compact" | "detailed"
}

export function CreditDisplay({
  credits,
  monthlyUsage,
  monthlyLimit,
  showProgress = false,
  showUpgrade = false,
  className,
  variant = "default",
}: CreditDisplayProps) {
  const isLow = credits < 10
  const usagePercentage = monthlyLimit && monthlyUsage
    ? (monthlyUsage / monthlyLimit) * 100
    : 0

  if (variant === "compact") {
    return (
      <div className={cn("flex items-center space-x-2", className)}>
        <Coins className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium text-foreground">{credits}</span>
        <span className="text-xs text-muted-foreground">credits</span>
      </div>
    )
  }

  if (variant === "detailed") {
    return (
      <Card className={cn("glass-card", className)}>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Coins className="h-5 w-5 text-primary" />
                <span className="text-sm font-medium text-muted-foreground">
                  Credit Balance
                </span>
              </div>
              <Badge
                variant={isLow ? "destructive" : "secondary"}
                className={cn(
                  "border-primary/30",
                  isLow && "border-destructive/50"
                )}
              >
                {isLow ? "Low" : "Active"}
              </Badge>
            </div>

            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-bold text-foreground">{credits}</span>
              <span className="text-sm text-muted-foreground">credits</span>
            </div>

            {showProgress && monthlyLimit && monthlyUsage !== undefined && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Monthly usage</span>
                  <span className="font-medium text-foreground">
                    {monthlyUsage} / {monthlyLimit}
                  </span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full transition-all",
                      usagePercentage >= 90
                        ? "bg-destructive"
                        : usagePercentage >= 70
                        ? "bg-primary"
                        : "bg-primary"
                    )}
                    style={{ width: `${Math.min(usagePercentage, 100)}%` }}
                  />
                </div>
              </div>
            )}

            {isLow && (
              <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30">
                <div className="flex items-start space-x-2">
                  <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">
                      Low Credits
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Consider purchasing more credits to continue generating
                    </p>
                  </div>
                </div>
              </div>
            )}

            {showUpgrade && (
              <Link href="/pricing" className="block">
                <Button variant="outline" className="w-full">
                  <Zap className="mr-2 h-4 w-4" />
                  Buy More Credits
                </Button>
              </Link>
            )}
          </div>
        </CardContent>
      </Card>
    )
  }

  // Default variant
  return (
    <Card className={cn("glass-card", className)}>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
              <Coins className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Credits</p>
              <p className="text-2xl font-bold text-foreground">{credits}</p>
            </div>
          </div>
          {showUpgrade && (
            <Link href="/pricing">
              <Button variant="outline" size="sm">
                <TrendingUp className="mr-2 h-4 w-4" />
                Upgrade
              </Button>
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
