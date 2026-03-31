"use client";

import { motion } from "framer-motion";
import { Wand2, Palette, Star, Users, Maximize2, Shield } from "lucide-react";

const features = [
  {
    icon: Wand2,
    title: "Describe & Create",
    description: "Just type what you imagine. AI understands your vision and creates stunning, professional images instantly.",
    color: "from-purple-500 to-indigo-500",
  },
  {
    icon: Palette,
    title: "Any Style You Want",
    description: "Portraits, anime, architecture, products, fantasy — get beautiful results for any creative need.",
    color: "from-blue-500 to-cyan-500",
  },
  {
    icon: Star,
    title: "Professional Quality",
    description: "Every image is automatically optimized for color, detail, and composition. Print-ready results from simple descriptions.",
    color: "from-amber-500 to-orange-500",
  },
  {
    icon: Users,
    title: "Face Consistency",
    description: "Upload reference photos and generate the same person across different scenes and styles.",
    color: "from-pink-500 to-rose-500",
  },
  {
    icon: Maximize2,
    title: "Flexible Dimensions",
    description: "Square, portrait, landscape, widescreen, or fully custom dimensions — any size you need.",
    color: "from-emerald-500 to-teal-500",
  },
  {
    icon: Shield,
    title: "Private & Secure",
    description: "Your creations are always private. Download, share, or keep them — your choice, always.",
    color: "from-slate-500 to-zinc-500",
  },
];

export default function Features() {
  return (
    <section id="features" className="relative py-28 px-4 overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-0 w-1/3 h-96 bg-primary/5 blur-[120px] rounded-full" />
        <div className="absolute top-1/2 right-0 w-1/3 h-96 bg-indigo-500/5 blur-[120px] rounded-full" />
      </div>

      <div className="max-w-6xl mx-auto relative">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="text-center mb-20"
        >
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mb-4">
            Everything You <span className="gradient-text">Need</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Professional tools made simple. Just describe, create, and download.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                className="group"
              >
                <div className="relative p-6 rounded-2xl glass-card border border-white/[0.06] hover:border-white/15 transition-all duration-300 h-full">
                  <div className={`inline-flex p-3 rounded-xl bg-gradient-to-br ${feature.color} mb-4 shadow-lg`}>
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <h3 className="text-base font-semibold text-foreground mb-2">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
