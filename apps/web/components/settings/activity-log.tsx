"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Activity,
  Search,
  Download,
  Sparkles,
  Key,
  Settings,
  User,
  Calendar,
} from "lucide-react"
import { format } from "date-fns"

interface ActivityLogEntry {
  id: string
  type: string
  action: string
  description: string
  timestamp: string
  metadata?: Record<string, any>
}

const ACTIVITY_TYPES = [
  { value: "all", label: "All Activities" },
  { value: "generation", label: "Generations" },
  { value: "identity", label: "Identities" },
  { value: "account", label: "Account" },
  { value: "api", label: "API" },
  { value: "billing", label: "Billing" },
]

const MOCK_ACTIVITIES: ActivityLogEntry[] = [
  {
    id: "1",
    type: "generation",
    action: "Image Generated",
    description: "Generated 2 images in Realism mode",
    timestamp: "2024-01-27T14:30:00Z",
    metadata: { mode: "REALISM", credits: 3 },
  },
  {
    id: "2",
    type: "identity",
    action: "Identity Created",
    description: "Created new identity: Professional Headshots",
    timestamp: "2024-01-27T10:15:00Z",
  },
  {
    id: "3",
    type: "account",
    action: "Profile Updated",
    description: "Updated profile information",
    timestamp: "2024-01-26T16:45:00Z",
  },
  {
    id: "4",
    type: "api",
    action: "API Key Created",
    description: "Created new API key: Production API",
    timestamp: "2024-01-26T09:20:00Z",
  },
  {
    id: "5",
    type: "billing",
    action: "Credits Purchased",
    description: "Purchased 500 credits for $39.99",
    timestamp: "2024-01-25T11:30:00Z",
    metadata: { amount: 39.99, credits: 500 },
  },
  {
    id: "6",
    type: "generation",
    action: "Image Generated",
    description: "Generated 2 images in Creative mode",
    timestamp: "2024-01-25T08:00:00Z",
    metadata: { mode: "CREATIVE", credits: 5 },
  },
  {
    id: "7",
    type: "identity",
    action: "Identity Training Started",
    description: "Started training: Casual Photos",
    timestamp: "2024-01-24T15:30:00Z",
  },
  {
    id: "8",
    type: "account",
    action: "Password Changed",
    description: "Password was updated",
    timestamp: "2024-01-24T12:00:00Z",
  },
  {
    id: "9",
    type: "generation",
    action: "Image Deleted",
    description: "Deleted 3 images from gallery",
    timestamp: "2024-01-23T18:20:00Z",
  },
  {
    id: "10",
    type: "api",
    action: "API Request",
    description: "Generated image via API",
    timestamp: "2024-01-23T14:10:00Z",
  },
]

export function ActivityLog() {
  const [activities, setActivities] = useState<ActivityLogEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filterType, setFilterType] = useState("all")
  const [searchQuery, setSearchQuery] = useState("")

  useEffect(() => {
    fetch("/api/generations")
      .then((r) => r.ok ? r.json() : [])
      .then((data: Array<{ id: string; prompt?: string; mode?: string; createdAt?: string }>) => {
        if (Array.isArray(data) && data.length > 0) {
          setActivities(data.slice(0, 20).map((g) => ({
            id: g.id,
            type: "generation",
            action: "Image Generated",
            description: g.prompt ? `Generated: "${g.prompt.slice(0, 60)}${g.prompt.length > 60 ? "..." : ""}"` : "Image generated",
            timestamp: g.createdAt ?? new Date().toISOString(),
            metadata: { mode: g.mode },
          })))
        } else {
          // Fallback to mock if no real data
          setActivities(MOCK_ACTIVITIES)
        }
        setIsLoading(false)
      })
      .catch(() => { setActivities(MOCK_ACTIVITIES); setIsLoading(false) })
  }, [])

  const getActivityIcon = (type: string) => {
    switch (type) {
      case "generation":
        return <Sparkles className="h-5 w-5 text-primary" />
      case "identity":
        return <User className="h-5 w-5 text-primary" />
      case "account":
        return <Settings className="h-5 w-5 text-muted-foreground" />
      case "api":
        return <Key className="h-5 w-5 text-primary" />
      case "billing":
        return <Calendar className="h-5 w-5 text-primary" />
      default:
        return <Activity className="h-5 w-5 text-muted-foreground" />
    }
  }

  const getActivityColor = (type: string) => {
    switch (type) {
      case "generation":
        return "bg-primary/20"
      case "identity":
        return "bg-primary/20"
      case "account":
        return "bg-muted"
      case "api":
        return "bg-primary/20"
      case "billing":
        return "bg-primary/20"
      default:
        return "bg-muted"
    }
  }

  const filteredActivities = activities.filter((activity) => {
    const matchesType = filterType === "all" || activity.type === filterType
    const matchesSearch =
      searchQuery === "" ||
      activity.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      activity.action.toLowerCase().includes(searchQuery.toLowerCase())

    return matchesType && matchesSearch
  })

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card className="glass-card">
        <CardContent className="pt-6">
          <div className="flex space-x-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search activities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ACTIVITY_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Activity Timeline */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="text-foreground">Activity Timeline</span>
            <Badge variant="secondary" className="border-primary/30">
              {filteredActivities.length} activities
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredActivities.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-foreground mb-2">
                No activities found
              </h3>
              <p className="text-muted-foreground">
                Try adjusting your filters or search query
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredActivities.map((activity, index) => (
                <div key={activity.id} className="relative">
                  {/* Timeline line */}
                  {index !== filteredActivities.length - 1 && (
                    <div className="absolute left-6 top-12 bottom-0 w-0.5 bg-border" />
                  )}

                  <div className="flex space-x-4">
                    {/* Icon */}
                    <div
                      className={`h-12 w-12 rounded-full ${getActivityColor(
                        activity.type
                      )} flex items-center justify-center flex-shrink-0 relative z-10`}
                    >
                      {getActivityIcon(activity.type)}
                    </div>

                    {/* Content */}
                    <div className="flex-1 pb-4">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="font-semibold text-foreground">
                          {activity.action}
                        </h4>
                        <span className="text-sm text-muted-foreground">
                          {format(new Date(activity.timestamp), "MMM d, h:mm a")}
                        </span>
                      </div>

                      <p className="text-sm text-muted-foreground mb-2">
                        {activity.description}
                      </p>

                      {activity.metadata && (
                        <div className="flex items-center space-x-2">
                          {Object.entries(activity.metadata).map(
                            ([key, value]) => (
                              <Badge key={key} variant="outline" className="text-xs border-border/50">
                                {key}: {value}
                              </Badge>
                            )
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Activity Summary */}
      <div className="grid md:grid-cols-4 gap-4">
        <Card className="glass-card">
          <CardContent className="pt-6 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-3">
              <Sparkles className="h-6 w-6 text-primary" />
            </div>
            <p className="text-2xl font-bold text-foreground">
              {activities.filter((a) => a.type === "generation").length}
            </p>
            <p className="text-sm text-muted-foreground mt-1">Generations</p>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardContent className="pt-6 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-3">
              <User className="h-6 w-6 text-primary" />
            </div>
            <p className="text-2xl font-bold text-foreground">
              {activities.filter((a) => a.type === "identity").length}
            </p>
            <p className="text-sm text-muted-foreground mt-1">Identity Actions</p>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardContent className="pt-6 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-3">
              <Key className="h-6 w-6 text-primary" />
            </div>
            <p className="text-2xl font-bold text-foreground">
              {activities.filter((a) => a.type === "api").length}
            </p>
            <p className="text-sm text-muted-foreground mt-1">API Requests</p>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardContent className="pt-6 text-center">
            <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-3">
              <Calendar className="h-6 w-6 text-primary" />
            </div>
            <p className="text-2xl font-bold text-foreground">
              {activities.filter((a) => a.type === "billing").length}
            </p>
            <p className="text-sm text-muted-foreground mt-1">Billing Events</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
