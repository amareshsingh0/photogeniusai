"use client"

import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Check, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"

interface PricingCardProps {
  plan: {
    id: string
    name: string
    icon: LucideIcon
    price: { monthly: number; yearly: number }
    credits: { monthly: number; yearly: number }
    features: string[]
    limitations: string[]
    popular: boolean
    color: string
    savings?: number
  }
  billingPeriod: "monthly" | "yearly"
  onSubscribe: () => void
}

export function PricingCard({ plan, billingPeriod, onSubscribe }: PricingCardProps) {
  const Icon = plan.icon
  const price = plan.price[billingPeriod]
  const credits = plan.credits[billingPeriod]
  const monthlySavings = billingPeriod === "yearly" && plan.savings
    ? Math.round((plan.price.monthly * 12 - plan.price.yearly) / 12)
    : 0

  const colorClasses: Record<string, { bg: string; text: string; border: string }> = {
    gray: { bg: "bg-muted", text: "text-muted-foreground", border: "border-border" },
    purple: { bg: "bg-primary/10", text: "text-primary", border: "border-primary/50" },
    amber: { bg: "bg-amber-500/10", text: "text-amber-500", border: "border-amber-500/50" },
  }

  const colorClass = colorClasses[plan.color] || colorClasses.gray

  return (
    <Card
      className={cn(
        "relative transition-all hover:shadow-lg bg-card border-border/50",
        plan.popular && "border-2 border-primary shadow-lg scale-105"
      )}
    >
      {/* Popular Badge */}
      {plan.popular && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2">
          <Badge className="bg-primary text-primary-foreground">
            Most Popular
          </Badge>
        </div>
      )}

      <CardHeader className="text-center pb-4">
        {/* Icon */}
        <div
          className={cn(
            "inline-flex items-center justify-center h-12 w-12 rounded-lg mx-auto mb-4",
            colorClass.bg
          )}
        >
          <Icon className={cn("h-6 w-6", colorClass.text)} />
        </div>

        {/* Plan Name */}
        <h3 className="text-2xl font-bold text-foreground">
          {plan.name}
        </h3>

        {/* Price */}
        <div className="mt-4">
          <div className="flex items-baseline justify-center">
            <span className="text-5xl font-bold text-foreground">
              ${price}
            </span>
            <span className="text-muted-foreground ml-2">
              /{billingPeriod === "yearly" ? "year" : "month"}
            </span>
          </div>

          {monthlySavings > 0 && (
            <p className="text-sm text-emerald-500 mt-2">
              Save ${monthlySavings}/month
            </p>
          )}
        </div>

        {/* Credits */}
        <div className="mt-4 py-2 px-4 rounded-lg bg-muted/50">
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">{credits}</span> credits{" "}
            {billingPeriod === "yearly" ? "per year" : "per month"}
          </p>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Subscribe Button */}
        <Button
          onClick={onSubscribe}
          className={cn(
            "w-full",
            plan.popular ? "btn-premium text-white" : ""
          )}
          variant={plan.popular ? "default" : "outline"}
          size="lg"
        >
          {plan.id === "free" ? "Start Free" : "Subscribe Now"}
        </Button>

        {/* Features */}
        <div className="space-y-3">
          <p className="text-sm font-semibold text-foreground">
            What&apos;s included:
          </p>
          {plan.features.map((feature, index) => (
            <div key={index} className="flex items-start space-x-3">
              <Check className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" />
              <span className="text-sm text-muted-foreground">{feature}</span>
            </div>
          ))}

          {/* Limitations */}
          {plan.limitations.length > 0 && (
            <>
              <div className="pt-3 border-t border-border">
                <p className="text-sm font-semibold text-foreground mb-3">
                  Limitations:
                </p>
                {plan.limitations.map((limitation, index) => (
                  <div key={index} className="flex items-start space-x-3">
                    <X className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-muted-foreground">{limitation}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
