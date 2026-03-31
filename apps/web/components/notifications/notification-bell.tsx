"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Bell,
  Check,
  Sparkles,
  AlertCircle,
  Info,
} from "lucide-react"

const notifications = [
  {
    id: "1",
    type: "success",
    title: "Generation Complete",
    message: "Your 'Professional Headshot' is ready!",
    time: "2 min ago",
    read: false,
  },
  {
    id: "2",
    type: "info",
    title: "Identity Training Complete",
    message: "Your 'Creative' identity is now ready to use",
    time: "1 hour ago",
    read: false,
  },
  {
    id: "3",
    type: "warning",
    title: "Low Credits",
    message: "You have 15 credits remaining",
    time: "2 hours ago",
    read: true,
  },
]

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const unreadCount = notifications.filter(n => !n.read).length

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
            >
              {unreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0 glass-card border-border/50" align="end">
        <div className="flex items-center justify-between p-4 border-b border-border/50">
          <h3 className="font-semibold text-foreground">Notifications</h3>
          <Button variant="ghost" size="sm" className="h-auto p-0 text-sm text-muted-foreground hover:text-foreground">
            <Check className="h-4 w-4 mr-1" />
            Mark all read
          </Button>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <Bell className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm">No notifications</p>
            </div>
          ) : (
            <div className="divide-y divide-border/50">
              {notifications.map((notification) => {
                const Icon =
                  notification.type === "success"
                    ? Sparkles
                    : notification.type === "warning"
                    ? AlertCircle
                    : Info

                return (
                  <div
                    key={notification.id}
                    className={`p-4 hover:bg-muted/30 cursor-pointer transition-colors ${
                      !notification.read ? "bg-primary/5" : ""
                    }`}
                  >
                    <div className="flex items-start space-x-3">
                      <div
                        className={`h-8 w-8 rounded-full flex items-center justify-center ${
                          notification.type === "success"
                            ? "bg-primary/20"
                            : notification.type === "warning"
                            ? "bg-secondary/20"
                            : "bg-accent/20"
                        }`}
                      >
                        <Icon
                          className={`h-4 w-4 ${
                            notification.type === "success"
                              ? "text-primary"
                              : notification.type === "warning"
                              ? "text-secondary"
                              : "text-accent"
                          }`}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground">
                          {notification.title}
                        </p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {notification.message}
                        </p>
                        <p className="text-xs text-muted-foreground/70 mt-1">
                          {notification.time}
                        </p>
                      </div>
                      {!notification.read && (
                        <div className="h-2 w-2 rounded-full bg-primary flex-shrink-0 mt-1" />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
