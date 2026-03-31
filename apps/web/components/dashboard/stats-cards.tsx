"use client"

import { Card, CardContent } from "@/components/ui/card"
import { ImagePlus, Image, User, TrendingUp, Loader2 } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { fetchDashboardStats } from "@/lib/api"
import { cn } from "@/lib/utils"

const statConfig = [
  {
    key: "credits" as const,
    name: "Credits Available",
    icon: TrendingUp,
    color: "text-primary",
    bgColor: "bg-primary/10",
  },
  {
    key: "imagesGenerated" as const,
    name: "Image Generated",
    icon: Image,
    color: "text-secondary",
    bgColor: "bg-secondary/10",
  },
  {
    key: "identitiesCount" as const,
    name: "Identities",
    icon: User,
    color: "text-accent",
    bgColor: "bg-accent/10",
  },
]

export function StatsCards() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
  })

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="border-border/50 bg-card/50 backdrop-blur-sm">
            <CardContent className="p-6">
              <div className="flex items-center justify-center h-24">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {statConfig.map((stat) => (
        <Card 
          key={stat.key} 
          className="border-border/50 bg-card/50 backdrop-blur-sm hover:border-primary/30 transition-colors"
        >
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  {stat.name}
                </p>
                <p className="mt-2 text-3xl font-bold">
                  {stats?.[stat.key] ?? 0}
                </p>
              </div>
              <div className={cn("rounded-xl p-3", stat.bgColor)}>
                <stat.icon className={cn("h-6 w-6", stat.color)} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
