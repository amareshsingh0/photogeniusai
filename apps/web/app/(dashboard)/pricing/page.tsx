"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import {
  Check,
  Sparkles,
  Zap,
  Crown,
  Gift,
  AlertCircle,
} from "lucide-react"
import { PricingCard } from "@/components/pricing/pricing-card"
import { CreditPackages } from "@/components/pricing/credit-packages"
import { CheckoutModal } from "@/components/pricing/checkout-modal"

type BillingPeriod = "monthly" | "yearly"

const subscriptionPlans = [
  {
    id: "free",
    name: "Free",
    icon: Gift,
    price: { monthly: 0, yearly: 0 },
    credits: { monthly: 10, yearly: 120 },
    features: [
      "10 credits per month",
      "Basic generation modes",
      "1 identity slot",
      "Standard quality",
      "Community support",
    ],
    limitations: [
      "Watermarked images",
      "Standard processing queue",
    ],
    popular: false,
    color: "gray",
  },
  {
    id: "pro",
    name: "Pro",
    icon: Zap,
    price: { monthly: 29, yearly: 290 },
    credits: { monthly: 200, yearly: 2500 },
    features: [
      "200 credits per month",
      "All generation modes",
      "5 identity slots",
      "High quality outputs",
      "Priority processing",
      "No watermarks",
      "Advanced settings",
      "Email support",
    ],
    limitations: [],
    popular: true,
    color: "purple",
    savings: 17,
  },
  {
    id: "business",
    name: "Business",
    icon: Crown,
    price: { monthly: 99, yearly: 990 },
    credits: { monthly: 1000, yearly: 12500 },
    features: [
      "1000 credits per month",
      "All Pro features",
      "Unlimited identity slots",
      "API access",
      "Bulk generation",
      "Custom LoRA training",
      "White-label option",
      "Priority support",
      "SLA guarantee",
    ],
    limitations: [],
    popular: false,
    color: "amber",
    savings: 17,
  },
]

const creditPackages = [
  {
    id: "starter",
    name: "Starter Pack",
    credits: 50,
    price: 9.99,
    bonus: 0,
    popular: false,
  },
  {
    id: "popular",
    name: "Popular Pack",
    credits: 150,
    price: 24.99,
    bonus: 10,
    popular: true,
  },
  {
    id: "pro",
    name: "Pro Pack",
    credits: 300,
    price: 44.99,
    bonus: 30,
    popular: false,
  },
  {
    id: "mega",
    name: "Mega Pack",
    credits: 1000,
    price: 129.99,
    bonus: 150,
    popular: false,
  },
]

export default function PricingPage() {
  const [billingPeriod, setBillingPeriod] = useState<BillingPeriod>("monthly")
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [selectedPackage, setSelectedPackage] = useState<string | null>(null)
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false)
  const [checkoutType, setCheckoutType] = useState<"subscription" | "credits">("subscription")

  const handleSubscribe = (planId: string) => {
    setSelectedPlan(planId)
    setCheckoutType("subscription")
    setIsCheckoutOpen(true)
  }

  const handleBuyCredits = (packageId: string) => {
    setSelectedPackage(packageId)
    setCheckoutType("credits")
    setIsCheckoutOpen(true)
  }

  const currentPlan = subscriptionPlans.find(p => p.id === selectedPlan)
  const currentPackage = creditPackages.find(p => p.id === selectedPackage)

  return (
    <div className="max-w-7xl mx-auto space-y-12">
      {/* Header */}
      <div className="text-center space-y-4">
        <Badge variant="secondary" className="text-sm">
          <Sparkles className="mr-1 h-3 w-3" />
          Flexible Pricing
        </Badge>
        <h1 className="text-4xl font-bold text-foreground">
          Choose Your Plan
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Start free, upgrade as you grow. No hidden fees, cancel anytime.
        </p>
      </div>

      {/* Billing Period Toggle */}
      <div className="flex items-center justify-center space-x-4">
        <Label
          htmlFor="billing-period"
          className={billingPeriod === "monthly" ? "font-semibold text-foreground" : "text-muted-foreground"}
        >
          Monthly
        </Label>
        <Switch
          id="billing-period"
          checked={billingPeriod === "yearly"}
          onCheckedChange={(checked) => setBillingPeriod(checked ? "yearly" : "monthly")}
        />
        <Label
          htmlFor="billing-period"
          className={billingPeriod === "yearly" ? "font-semibold text-foreground" : "text-muted-foreground"}
        >
          Yearly
          <Badge variant="secondary" className="ml-2">
            Save 17%
          </Badge>
        </Label>
      </div>

      {/* Subscription Plans */}
      <div className="grid md:grid-cols-3 gap-6">
        {subscriptionPlans.map((plan) => (
          <PricingCard
            key={plan.id}
            plan={plan}
            billingPeriod={billingPeriod}
            onSubscribe={() => handleSubscribe(plan.id)}
          />
        ))}
      </div>

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-background px-4 text-sm text-muted-foreground">
            Or buy credits as needed
          </span>
        </div>
      </div>

      {/* One-Time Credit Packages */}
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-foreground mb-2">
            One-Time Credit Packages
          </h2>
          <p className="text-muted-foreground">
            No subscription required. Credits never expire.
          </p>
        </div>

        <CreditPackages
          packages={creditPackages}
          onBuy={handleBuyCredits}
        />
      </div>

      {/* Credit Usage Info */}
      <Card className="bg-card border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <AlertCircle className="h-5 w-5 text-primary" />
            <span>How Credits Work</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-3 gap-6">
            <div>
              <h4 className="font-semibold text-foreground mb-2">
                Realism Mode
              </h4>
              <p className="text-3xl font-bold text-primary mb-1">3</p>
              <p className="text-sm text-muted-foreground">
                credits per generation
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-foreground mb-2">
                Romantic Mode
              </h4>
              <p className="text-3xl font-bold text-pink-500 mb-1">4</p>
              <p className="text-sm text-muted-foreground">
                credits per generation
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-foreground mb-2">
                Creative Mode
              </h4>
              <p className="text-3xl font-bold text-purple-500 mb-1">5</p>
              <p className="text-sm text-muted-foreground">
                credits per generation
              </p>
            </div>
          </div>

          <div className="mt-6 p-4 rounded-lg bg-primary/10 border border-primary/20">
            <p className="text-sm text-foreground">
              <strong>Pro Tip:</strong> Each generation creates 4 high-quality variants,
              and our AI automatically selects the best 2 for you. You only pay for one generation!
            </p>
          </div>
        </CardContent>
      </Card>

      {/* FAQ Section */}
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-foreground text-center">
          Frequently Asked Questions
        </h2>

        <div className="grid md:grid-cols-2 gap-6">
          <Card className="bg-card border-border/50">
            <CardContent className="pt-6">
              <h4 className="font-semibold text-foreground mb-2">Can I cancel anytime?</h4>
              <p className="text-sm text-muted-foreground">
                Yes! Cancel your subscription anytime. Your credits remain available
                until the end of your billing period.
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border/50">
            <CardContent className="pt-6">
              <h4 className="font-semibold text-foreground mb-2">Do credits expire?</h4>
              <p className="text-sm text-muted-foreground">
                Subscription credits expire at the end of each billing period.
                One-time credit packages never expire!
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border/50">
            <CardContent className="pt-6">
              <h4 className="font-semibold text-foreground mb-2">Can I upgrade or downgrade?</h4>
              <p className="text-sm text-muted-foreground">
                Yes! You can change plans anytime. We&apos;ll prorate the difference
                and adjust your credits accordingly.
              </p>
            </CardContent>
          </Card>

          <Card className="bg-card border-border/50">
            <CardContent className="pt-6">
              <h4 className="font-semibold text-foreground mb-2">What payment methods do you accept?</h4>
              <p className="text-sm text-muted-foreground">
                We accept all major credit cards, debit cards, and payment methods
                supported by Stripe.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Checkout Modal */}
      <CheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        type={checkoutType}
        plan={currentPlan}
        package={currentPackage}
        billingPeriod={billingPeriod}
      />
    </div>
  )
}
