"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Check, Zap, Star, Crown, Sparkles } from "lucide-react";
import { GradientButton } from "@/components/ui/gradient-button";

const plans = [
  { name: "Free", price: "Rs 0", period: "forever", credits: "15 credits", icon: Sparkles, description: "Try the magic", features: ["15 AI portrait credits", "Realism mode", "Standard quality", "Watermarked outputs"], cta: "Get Started", popular: false },
  { name: "Fast", price: "Rs 499", period: "/month", credits: "40 credits", icon: Zap, description: "For enthusiasts", features: ["40 AI portrait credits", "Realism + Creative", "High quality", "No watermarks", "Priority queue"], cta: "Subscribe", popular: false },
  { name: "Pro", price: "Rs 1,499", period: "/month", credits: "120 credits", icon: Star, description: "Most popular", features: ["120 AI portrait credits", "All modes", "Best-of-4", "Quality report", "Priority support", "Commercial license"], cta: "Subscribe", popular: true },
  { name: "Premium", price: "Rs 4,999", period: "/month", credits: "Unlimited Realism", icon: Crown, description: "For professionals", features: ["Unlimited Realism", "80 Creative/Romantic", "Best-of-N", "API access", "Dedicated support", "Custom LoRA", "White-label"], cta: "Contact Sales", popular: false },
];

export default function Pricing() {
  return (
    <section id="pricing" className="relative py-24 px-4">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Simple <span className="gradient-text">Pricing</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Start free, upgrade when you need more. All prices in INR.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {plans.map((plan, index) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className={plan.popular ? "relative lg:-mt-4 lg:mb-4" : "relative"}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 z-10">
                  <div className="px-4 py-1 rounded-full bg-gradient-to-r from-primary to-secondary text-xs font-bold text-primary-foreground">
                    Most Popular
                  </div>
                </div>
              )}
              <div className={"glass-card rounded-2xl p-6 h-full flex flex-col transition-all duration-300 hover:scale-[1.02] " + (plan.popular ? "border-primary/50 glow-primary" : "")}>
                <div className="flex items-center gap-3 mb-4">
                  <div className={"p-2 rounded-xl " + (plan.popular ? "bg-gradient-to-r from-primary to-secondary" : "bg-muted")}>
                    <plan.icon className={"w-5 h-5 " + (plan.popular ? "text-primary-foreground" : "text-primary")} />
                  </div>
                  <div>
                    <h3 className="font-semibold">{plan.name}</h3>
                    <p className="text-xs text-muted-foreground">{plan.description}</p>
                  </div>
                </div>
                <div className="mb-4">
                  <span className="text-4xl font-bold">{plan.price}</span>
                  <span className="text-muted-foreground text-sm">{plan.period}</span>
                  <div className="text-sm text-primary mt-1">{plan.credits}</div>
                </div>
                <ul className="space-y-3 mb-6 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <Check className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                      <span className="text-muted-foreground">{f}</span>
                    </li>
                  ))}
                </ul>
                <GradientButton variant={plan.popular ? "glow" : "outline"} className="w-full" asChild>
                  <Link href={plan.cta === "Get Started" ? "/generate" : "/dashboard"}>{plan.cta}</Link>
                </GradientButton>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
