"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Sparkles,
  Users,
  Image,
  Upload,
  ArrowRight,
} from "lucide-react"
import Link from "next/link"

export function QuickActions() {
  const actions = [
    {
      title: "Generate AI Avatar",
      description: "Create stunning AI-generated images",
      icon: Sparkles,
      href: "/generate",
      color: "purple",
    },
    {
      title: "Create Identity",
      description: "Upload photos to train new identity",
      icon: Users,
      href: "/identity-vault",
      color: "blue",
    },
    {
      title: "View Gallery",
      description: "Browse your generated images",
      icon: Image,
      href: "/gallery",
      color: "pink",
    },
    {
      title: "Upload Photos",
      description: "Add more reference photos",
      icon: Upload,
      href: "/identity-vault",
      color: "green",
    },
  ]

  return (
    <Card className="glass-card">
      <CardHeader>
        <CardTitle>Quick Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {actions.map((action) => {
            const Icon = action.icon
            const getColorClasses = (color: string) => {
              switch (color) {
                case "purple":
                  return {
                    bg: "bg-primary/20",
                    text: "text-primary",
                    border: "border-primary/30",
                    hoverBg: "hover:bg-primary/20",
                    hoverBorder: "hover:border-primary/30",
                  }
                case "blue":
                  return {
                    bg: "bg-primary/20",
                    text: "text-primary",
                    border: "border-primary/30",
                    hoverBg: "hover:bg-primary/20",
                    hoverBorder: "hover:border-primary/30",
                  }
                case "pink":
                  return {
                    bg: "bg-secondary/20",
                    text: "text-secondary",
                    border: "border-secondary/30",
                    hoverBg: "hover:bg-secondary/20",
                    hoverBorder: "hover:border-secondary/30",
                  }
                case "green":
                  return {
                    bg: "bg-accent/20",
                    text: "text-accent",
                    border: "border-accent/30",
                    hoverBg: "hover:bg-accent/20",
                    hoverBorder: "hover:border-accent/30",
                  }
                default:
                  return {
                    bg: "bg-primary/20",
                    text: "text-primary",
                    border: "border-primary/30",
                    hoverBg: "hover:bg-primary/20",
                    hoverBorder: "hover:border-primary/30",
                  }
              }
            }
            const colors = getColorClasses(action.color)

            return (
              <Link key={action.title} href={action.href}>
                <div className={`group p-4 rounded-lg border border-border/50 ${colors.hoverBorder} ${colors.hoverBg} transition-all cursor-pointer`}>
                  <div className={`h-10 w-10 rounded-lg ${colors.bg} flex items-center justify-center mb-3`}>
                    <Icon className={`h-5 w-5 ${colors.text}`} />
                  </div>
                  <h4 className="font-semibold text-foreground mb-1">
                    {action.title}
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    {action.description}
                  </p>
                  <div className={`mt-3 flex items-center text-sm ${colors.text} group-hover:translate-x-1 transition-transform`}>
                    Get started
                    <ArrowRight className="ml-1 h-4 w-4" />
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
