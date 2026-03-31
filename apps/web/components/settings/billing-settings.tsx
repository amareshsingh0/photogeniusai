"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  CreditCard,
  Coins,
  Download,
  Calendar,
  CheckCircle,
  ExternalLink,
  Zap,
  TrendingUp,
} from "lucide-react"
import { format } from "date-fns"

const PLANS = [
  {
    id: "free",
    name: "Free",
    price: 0,
    credits: 50,
    features: [
      "50 credits/month",
      "2 identities",
      "Basic generation modes",
      "Standard quality",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: 29,
    credits: 500,
    features: [
      "500 credits/month",
      "10 identities",
      "All generation modes",
      "High quality",
      "Priority support",
      "API access",
    ],
    popular: true,
  },
  {
    id: "business",
    name: "Business",
    price: 99,
    credits: 2000,
    features: [
      "2000 credits/month",
      "Unlimited identities",
      "All generation modes",
      "Highest quality",
      "Priority support",
      "Advanced API access",
      "Custom training",
      "Team collaboration",
    ],
  },
]

const CREDIT_PACKS = [
  { credits: 100, price: 9.99, bonus: 0 },
  { credits: 500, price: 39.99, bonus: 50 },
  { credits: 1000, price: 69.99, bonus: 150 },
  { credits: 2500, price: 149.99, bonus: 500 },
]

export function BillingSettings() {
  const [currentPlan] = useState("free")
  const [credits, setCredits] = useState<number | null>(null)
  const [generationsCount, setGenerationsCount] = useState(0)

  useEffect(() => {
    fetch("/api/user/stats")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data) {
          setCredits(data.credits ?? 0)
          setGenerationsCount(data.generationsCount ?? 0)
        }
      })
      .catch(() => {})
  }, [])

  const currentPlanData = PLANS.find((p) => p.id === currentPlan)!

  const invoices = [
    {
      id: "inv_001",
      date: "2024-01-01",
      amount: 29.0,
      status: "paid",
      description: "Pro Plan - January 2024",
    },
    {
      id: "inv_002",
      date: "2023-12-01",
      amount: 29.0,
      status: "paid",
      description: "Pro Plan - December 2023",
    },
    {
      id: "inv_003",
      date: "2023-11-01",
      amount: 29.0,
      status: "paid",
      description: "Pro Plan - November 2023",
    },
  ]

  return (
    <div className="space-y-6">
      {/* Current Plan & Credits */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Current Plan */}
        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Zap className="h-5 w-5 text-primary" />
              <span className="text-foreground">Current Plan</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-baseline space-x-2">
                <h3 className="text-3xl font-bold text-foreground">
                  {currentPlanData.name}
                </h3>
                <Badge variant="secondary" className="border-primary/30">Active</Badge>
              </div>

              <div className="text-sm text-muted-foreground space-y-1">
                {currentPlanData.features.map((feature, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <CheckCircle className="h-4 w-4 text-primary" />
                    <span>{feature}</span>
                  </div>
                ))}
              </div>

              <div className="pt-4 border-t border-border/50">
                <Button className="w-full">
                  {currentPlan === "free" ? "Upgrade Plan" : "Manage Subscription"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Credit Balance */}
        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Coins className="h-5 w-5 text-primary" />
              <span className="text-foreground">Credit Balance</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-baseline space-x-2">
                {credits === null ? (
                  <div className="h-9 w-20 bg-muted/50 animate-pulse rounded" />
                ) : (
                  <h3 className="text-3xl font-bold text-foreground">{credits.toLocaleString()}</h3>
                )}
                <span className="text-muted-foreground">credits remaining</span>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Generations created</span>
                  <span className="font-medium text-foreground">{generationsCount}</span>
                </div>
                <Progress
                  value={Math.min((generationsCount / Math.max(currentPlanData.credits, 1)) * 100, 100)}
                  className="h-2"
                />
                <p className="text-xs text-muted-foreground">
                  {currentPlan === "free" ? "Free plan: 50 credits/month" : "Credits replenish monthly"}
                </p>
              </div>

              <div className="pt-4 border-t border-border/50">
                <Button variant="outline" className="w-full">
                  <Coins className="mr-2 h-4 w-4" />
                  Buy More Credits
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Available Plans */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">Available Plans</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-4">
            {PLANS.map((plan) => {
              const isCurrent = plan.id === currentPlan

              return (
                <div
                  key={plan.id}
                  className={`p-6 rounded-lg border-2 transition-all glass-card ${
                    plan.popular
                      ? "border-primary bg-primary/10"
                      : isCurrent
                      ? "border-primary/50 bg-primary/5"
                      : "border-border/50"
                  }`}
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-foreground">
                      {plan.name}
                    </h3>
                    {plan.popular && (
                      <Badge className="bg-primary border-primary/30">Popular</Badge>
                    )}
                    {isCurrent && (
                      <Badge variant="secondary" className="border-primary/30">Current</Badge>
                    )}
                  </div>

                  <div className="mb-6">
                    <div className="flex items-baseline space-x-1">
                      <span className="text-4xl font-bold text-foreground">
                        ${plan.price}
                      </span>
                      <span className="text-muted-foreground">/month</span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {plan.credits} credits/month
                    </p>
                  </div>

                  <ul className="space-y-2 mb-6">
                    {plan.features.map((feature, index) => (
                      <li
                        key={index}
                        className="flex items-start space-x-2 text-sm"
                      >
                        <CheckCircle className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                        <span className="text-muted-foreground">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  <Button
                    className="w-full"
                    variant={isCurrent ? "outline" : "default"}
                    disabled={isCurrent}
                  >
                    {isCurrent ? "Current Plan" : "Upgrade"}
                  </Button>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Credit Packs */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-foreground">One-Time Credit Packs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-4">
            {CREDIT_PACKS.map((pack) => (
              <div
                key={pack.credits}
                className="p-4 rounded-lg border-2 border-border/50 hover:border-primary/50 transition-all glass-card"
              >
                <div className="text-center mb-3">
                  <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-2">
                    <Coins className="h-6 w-6 text-primary" />
                  </div>
                  <h4 className="font-semibold text-foreground">
                    {pack.credits} Credits
                  </h4>
                  {pack.bonus > 0 && (
                    <Badge variant="secondary" className="mt-1 border-primary/30">
                      +{pack.bonus} bonus
                    </Badge>
                  )}
                </div>

                <div className="text-center mb-3">
                  <span className="text-2xl font-bold text-foreground">
                    ${pack.price}
                  </span>
                </div>

                <Button variant="outline" size="sm" className="w-full">
                  Buy Now
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Payment Method */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <CreditCard className="h-5 w-5 text-primary" />
            <span className="text-foreground">Payment Method</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 rounded-lg border border-border/50 bg-muted/30">
            <div className="flex items-center space-x-3">
              <div className="h-10 w-10 rounded bg-muted flex items-center justify-center">
                <CreditCard className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="font-medium text-foreground">Visa ending in 4242</p>
                <p className="text-sm text-muted-foreground">Expires 12/2025</p>
              </div>
            </div>
            <Button variant="outline" size="sm">
              Update
            </Button>
          </div>

          <div className="mt-4">
            <Button variant="outline" className="w-full">
              Add Payment Method
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Billing History */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="text-foreground">Billing History</span>
            <Button variant="outline" size="sm">
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {invoices.map((invoice) => (
              <div
                key={invoice.id}
                className="flex items-center justify-between p-4 rounded-lg border border-border/50 bg-muted/30"
              >
                <div className="flex items-center space-x-4">
                  <div className="h-10 w-10 rounded bg-primary/20 flex items-center justify-center">
                    <Calendar className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">
                      {invoice.description}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {format(new Date(invoice.date), "MMMM d, yyyy")}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-4">
                  <Badge
                    variant={invoice.status === "paid" ? "secondary" : "destructive"}
                    className={invoice.status === "paid" ? "border-primary/30" : ""}
                  >
                    {invoice.status}
                  </Badge>
                  <span className="font-semibold text-foreground">
                    ${invoice.amount.toFixed(2)}
                  </span>
                  <Button variant="ghost" size="sm">
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Usage Statistics */}
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <span className="text-foreground">Usage Statistics</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-6">
            <div className="text-center">
              <p className="text-3xl font-bold text-foreground">1,247</p>
              <p className="text-sm text-muted-foreground mt-1">Total Generations</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-foreground">8</p>
              <p className="text-sm text-muted-foreground mt-1">Identities Created</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-foreground">3,891</p>
              <p className="text-sm text-muted-foreground mt-1">Credits Used (All Time)</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
