"use client"

import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

interface CreditPackage {
  id: string
  name: string
  credits: number
  price: number
  bonus: number
  popular: boolean
}

interface CreditPackagesProps {
  packages: CreditPackage[]
  onBuy: (packageId: string) => void
}

export function CreditPackages({ packages, onBuy }: CreditPackagesProps) {
  return (
    <div className="grid md:grid-cols-4 gap-4">
      {packages.map((pkg) => {
        const totalCredits = pkg.credits + pkg.bonus
        const pricePerCredit = (pkg.price / pkg.credits).toFixed(2)

        return (
          <Card
            key={pkg.id}
            className={cn(
              "relative transition-all hover:shadow-md bg-card border-border/50",
              pkg.popular && "border-2 border-primary"
            )}
          >
            {pkg.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <Badge className="bg-primary text-primary-foreground">
                  <Sparkles className="h-3 w-3 mr-1" />
                  Best Value
                </Badge>
              </div>
            )}

            <CardContent className="pt-6 text-center space-y-4">
              {/* Package Name */}
              <h4 className="font-semibold text-foreground">
                {pkg.name}
              </h4>

              {/* Credits */}
              <div>
                <div className="text-3xl font-bold text-primary">
                  {totalCredits}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  credits
                </p>
                {pkg.bonus > 0 && (
                  <Badge variant="secondary" className="mt-2">
                    +{pkg.bonus} Bonus
                  </Badge>
                )}
              </div>

              {/* Price */}
              <div className="py-3 px-4 rounded-lg bg-muted/50">
                <div className="text-2xl font-bold text-foreground">
                  ${pkg.price}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  ${pricePerCredit} per credit
                </p>
              </div>

              {/* Buy Button */}
              <Button
                onClick={() => onBuy(pkg.id)}
                className={cn("w-full", pkg.popular && "btn-premium text-white")}
                variant={pkg.popular ? "default" : "outline"}
              >
                Buy Now
              </Button>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
