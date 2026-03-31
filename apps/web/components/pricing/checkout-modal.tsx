"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import {
  CreditCard,
  Lock,
  AlertCircle,
} from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface CheckoutModalProps {
  isOpen: boolean
  onClose: () => void
  type: "subscription" | "credits"
  plan?: any
  package?: any
  billingPeriod?: "monthly" | "yearly"
}

export function CheckoutModal({
  isOpen,
  onClose,
  type,
  plan,
  package: pkg,
  billingPeriod,
}: CheckoutModalProps) {
  const [processing, setProcessing] = useState(false)
  const [promoCode, setPromoCode] = useState("")
  const [agreedToTerms, setAgreedToTerms] = useState(false)

  const handleCheckout = async () => {
    if (!agreedToTerms) {
      alert("Please agree to the terms and conditions")
      return
    }

    setProcessing(true)

    // TODO: Integrate with Stripe
    // For now, simulate processing
    await new Promise(resolve => setTimeout(resolve, 2000))

    console.log("Processing checkout:", {
      type,
      plan: plan?.id,
      package: pkg?.id,
      billingPeriod,
      promoCode,
    })

    setProcessing(false)
    onClose()
    
    // Show success message
    alert("Payment successful! Redirecting...")
  }

  if (!plan && !pkg) return null

  const isSubscription = type === "subscription"
  const price = isSubscription
    ? plan.price[billingPeriod || "monthly"]
    : pkg.price
  const credits = isSubscription
    ? plan.credits[billingPeriod || "monthly"]
    : pkg.credits + pkg.bonus

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Complete Your Purchase</DialogTitle>
          <DialogDescription>
            Review your order and complete payment
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Order Summary */}
          <div className="rounded-lg border p-4 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-semibold text-gray-900">
                  {isSubscription ? plan.name : pkg.name}
                </h4>
                <p className="text-sm text-gray-600 mt-1">
                  {credits} credits
                  {isSubscription && ` per ${billingPeriod}`}
                </p>
              </div>
              <Badge variant={isSubscription ? "default" : "secondary"}>
                {isSubscription ? "Subscription" : "One-Time"}
              </Badge>
            </div>

            <Separator />

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Subtotal</span>
                <span className="font-medium">${price.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Tax</span>
                <span className="font-medium">$0.00</span>
              </div>
              <Separator />
              <div className="flex justify-between">
                <span className="font-semibold text-gray-900">Total</span>
                <span className="text-2xl font-bold text-gray-900">
                  ${price.toFixed(2)}
                </span>
              </div>
            </div>

            {isSubscription && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription className="text-sm">
                  Your subscription will auto-renew {billingPeriod === "yearly" ? "annually" : "monthly"}. 
                  Cancel anytime from your account settings.
                </AlertDescription>
              </Alert>
            )}
          </div>

          {/* Promo Code */}
          <div className="space-y-2">
            <Label>Promo Code (Optional)</Label>
            <div className="flex space-x-2">
              <Input
                placeholder="Enter code"
                value={promoCode}
                onChange={(e) => setPromoCode(e.target.value)}
              />
              <Button variant="outline">
                Apply
              </Button>
            </div>
          </div>

          {/* Payment Info */}
          <div className="rounded-lg border p-4 space-y-4">
            <div className="flex items-center space-x-2">
              <CreditCard className="h-5 w-5 text-gray-600" />
              <h4 className="font-semibold text-gray-900">Payment Method</h4>
            </div>

            {/* Stripe Card Element would go here */}
            <div className="p-8 rounded-lg bg-gray-50 text-center">
              <p className="text-sm text-gray-600">
                Stripe payment form will be integrated here
              </p>
            </div>

            <div className="flex items-start space-x-2 text-sm text-gray-600">
              <Lock className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <p>
                Your payment information is secure and encrypted. 
                We use Stripe for payment processing.
              </p>
            </div>
          </div>

          {/* Terms Checkbox */}
          <div className="flex items-start space-x-2">
            <Checkbox
              id="terms"
              checked={agreedToTerms}
              onCheckedChange={(checked) => setAgreedToTerms(checked as boolean)}
            />
            <Label
              htmlFor="terms"
              className="text-sm text-gray-600 cursor-pointer"
            >
              I agree to the{" "}
              <a href="/terms" className="text-purple-600 hover:underline">
                Terms of Service
              </a>{" "}
              and{" "}
              <a href="/privacy" className="text-purple-600 hover:underline">
                Privacy Policy
              </a>
            </Label>
          </div>

          {/* Action Buttons */}
          <div className="flex space-x-3">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={processing}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCheckout}
              disabled={processing || !agreedToTerms}
              className="flex-1"
            >
              {processing ? (
                "Processing..."
              ) : (
                <>
                  <Lock className="mr-2 h-4 w-4" />
                  Pay ${price.toFixed(2)}
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
