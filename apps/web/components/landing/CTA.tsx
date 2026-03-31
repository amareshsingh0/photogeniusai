"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { GradientButton } from "@/components/ui/gradient-button";
import { ArrowRight, Sparkles } from "lucide-react";

export default function CTA() {
  return (
    <section className="relative py-24 px-4 overflow-hidden">
      <div className="absolute inset-0">
        <motion.div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-gradient-to-r from-primary/20 via-secondary/20 to-accent/20 blur-3xl"
          animate={{ scale: [1, 1.1, 1], rotate: [0, 180, 360] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
      </div>
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="relative max-w-3xl mx-auto text-center"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-card mb-8">
          <Sparkles className="w-4 h-4 text-primary" />
          <span className="text-sm text-muted-foreground">Start creating today</span>
        </div>
        <h2 className="text-4xl md:text-6xl font-bold mb-6">
          Ready to Create <span className="gradient-text">Magic?</span>
        </h2>
        <p className="text-muted-foreground text-lg mb-10 max-w-xl mx-auto">
          Join creators. 15 free credits, no card required.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <GradientButton size="xl" variant="glow" asChild>
            <Link href="/generate">
              Start Creating Free
              <ArrowRight className="w-5 h-5" />
            </Link>
          </GradientButton>
          <GradientButton size="xl" variant="ghost" asChild>
            <Link href="/#pricing">View Pricing</Link>
          </GradientButton>
        </div>
      </motion.div>
    </section>
  );
}
