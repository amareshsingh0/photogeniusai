"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { Upload, Wand2, CheckCircle2, Download } from "lucide-react";

const steps = [
  { icon: Upload, step: "01", title: "Upload Your Photo", description: "Use Identity Vault to upload a clear selfie. AI analyzes your face.", href: "/identity-vault" },
  { icon: Wand2, step: "02", title: "Choose Your Style", description: "Select Realism, Creative, or Romantic in Generate.", href: "/generate" },
  { icon: CheckCircle2, step: "03", title: "AI Generates Options", description: "Best-of-N creates multiple variants. Pick your favorite.", href: "/generate" },
  { icon: Download, step: "04", title: "Download & Share", description: "Get your high-res portrait from Gallery.", href: "/gallery" },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-24 px-4 overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-0 w-1/2 h-96 bg-primary/5 blur-3xl rounded-full" />
        <div className="absolute top-1/2 right-0 w-1/2 h-96 bg-secondary/5 blur-3xl rounded-full" />
      </div>

      <div className="relative max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            How It <span className="gradient-text">Works</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Create stunning portraits in four simple steps
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((step, index) => (
            <motion.div
              key={step.step}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.15 }}
              className="relative"
            >
              {index < steps.length - 1 && (
                <div className="hidden lg:block absolute top-12 left-[60%] w-full h-px bg-gradient-to-r from-border to-transparent" />
              )}
              <Link href={step.href} className="block">
                <div className="relative glass-card rounded-2xl p-6 text-center hover:border-primary/50 transition-colors">
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-gradient-to-r from-primary to-secondary text-xs font-bold text-primary-foreground">
                    {step.step}
                  </div>
                  <div className="inline-flex p-4 rounded-2xl bg-muted mb-4 mt-2">
                    <step.icon className="w-8 h-8 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{step.title}</h3>
                  <p className="text-muted-foreground text-sm">{step.description}</p>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
