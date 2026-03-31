"use client";

import { motion } from "framer-motion";
import { Shield, Lock, Eye, FileCheck, AlertTriangle, UserCheck } from "lucide-react";

const safetyFeatures = [
  { icon: Shield, title: "CSAM Detection", description: "PhotoDNA integration blocks illegal content." },
  { icon: Eye, title: "NSFW Filtering", description: "Dual-layer moderation pre and post-gen." },
  { icon: UserCheck, title: "Age Verification", description: "AI age estimator blocks minors." },
  { icon: AlertTriangle, title: "Celebrity Protection", description: "Blocks sexual content of public figures." },
  { icon: FileCheck, title: "Content Provenance", description: "C2PA metadata in every image." },
  { icon: Lock, title: "Consent Records", description: "Uploads logged with IP, timestamp, consent." },
];

export default function Safety() {
  return (
    <section id="safety" className="relative py-24 px-4 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-muted/20 to-transparent" />

      <div className="relative max-w-6xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm mb-6">
              <Shield className="w-4 h-4" />
              Safety First
            </div>
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Built for <span className="gradient-text">Trust</span>
            </h2>
            <p className="text-muted-foreground text-lg mb-8">
              Our safety system ensures every generation is legal, ethical, and consent-verified. We block harmful requests before GPU spend.
            </p>
            <div className="flex items-center gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-primary" />
                <span className="text-muted-foreground">India Compliant</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-secondary" />
                <span className="text-muted-foreground">180-Day Audit Logs</span>
              </div>
            </div>
          </motion.div>

          <div className="grid grid-cols-2 gap-4">
            {safetyFeatures.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: index * 0.1 }}
                className="glass-card rounded-xl p-4 hover:border-primary/30 transition-colors"
              >
                <feature.icon className="w-5 h-5 text-primary mb-2" />
                <h4 className="font-semibold text-sm mb-1">{feature.title}</h4>
                <p className="text-xs text-muted-foreground">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
