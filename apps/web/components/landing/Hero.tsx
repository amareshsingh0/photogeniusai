"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Sparkles, ArrowRight, Shield, Zap, Lock } from "lucide-react";

const EXAMPLE_PROMPTS = [
  "Professional headshot with soft lighting",
  "Cinematic portrait at golden hour",
  "Artistic photo with vibrant colors",
];

export default function Hero() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (trimmed.length >= 5) {
      router.push(`/generate?prompt=${encodeURIComponent(trimmed)}`);
    } else {
      router.push("/generate");
    }
  };

  return (
    <section className="relative min-h-[90vh] flex flex-col items-center justify-center overflow-hidden px-4 pt-28 pb-24">
      {/* Gradient mesh / orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-[15%] left-[20%] w-[500px] h-[500px] rounded-full bg-primary/12 blur-[120px]"
          animate={{
            scale: [1, 1.15, 1],
            opacity: [0.5, 0.8, 0.5],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute top-[40%] right-[10%] w-[400px] h-[400px] rounded-full bg-indigo-500/10 blur-[100px]"
          animate={{
            scale: [1.1, 1, 1.1],
            opacity: [0.4, 0.7, 0.4],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute bottom-[20%] left-1/2 -translate-x-1/2 w-[600px] h-[300px] rounded-full bg-violet-500/10 blur-[100px]"
          animate={{ opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        />
        {/* Subtle grid */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,.08) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255,255,255,.08) 1px, transparent 1px)`,
            backgroundSize: "64px 64px",
          }}
        />
      </div>

      <div className="relative z-10 w-full max-w-3xl mx-auto text-center">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/[0.04] backdrop-blur-sm mb-8"
        >
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          <span className="text-xs font-medium text-muted-foreground">
            AI-powered portrait studio · No design skills needed
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-foreground mb-5 leading-[1.1]"
        >
          Turn Imagination
          <br />
          <span className="bg-gradient-to-r from-purple-300 via-violet-400 to-indigo-400 bg-clip-text text-transparent">
            into Stunning Images
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.25 }}
          className="text-base sm:text-lg text-muted-foreground mb-10 max-w-lg mx-auto"
        >
          Describe what you want. Get professional portraits and visuals in seconds.
        </motion.p>

        {/* Input - premium glass style */}
        <motion.form
          onSubmit={handleSubmit}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.35 }}
          className="w-full mb-6"
        >
          <div className="relative flex items-center w-full max-w-2xl mx-auto rounded-2xl overflow-hidden border border-white/10 bg-white/[0.03] backdrop-blur-xl shadow-2xl shadow-black/20 focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/20 transition-all duration-300">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe your photo..."
              className="w-full px-6 py-4 sm:py-5 bg-transparent text-foreground placeholder:text-muted-foreground/80 text-base outline-none"
            />
            <Button
              type="submit"
              size="sm"
              className="m-2 h-10 sm:h-11 px-5 rounded-xl btn-premium text-white shrink-0 font-semibold"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Create
            </Button>
          </div>
        </motion.form>

        {/* Example prompts */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="flex flex-wrap justify-center gap-2 mb-10"
        >
          <span className="text-xs text-muted-foreground/80 mr-1 self-center">Try:</span>
          {EXAMPLE_PROMPTS.map((example, i) => (
            <button
              key={example}
              onClick={() => setPrompt(example)}
              className="text-xs px-4 py-2 rounded-full text-muted-foreground hover:text-foreground hover:bg-white/10 border border-transparent hover:border-white/10 transition-all duration-200"
            >
              {example}
            </button>
          ))}
        </motion.div>

        {/* Trust line with icons */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="flex flex-wrap justify-center items-center gap-6 text-xs text-muted-foreground"
        >
          <span className="inline-flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5 text-primary/80" />
            Results in ~30s
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Lock className="h-3.5 w-3.5 text-primary/80" />
            Private & secure
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-primary/80" />
            No credit card required
          </span>
        </motion.div>

        {/* Secondary CTA */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.7 }}
        >
          <Link href="/generate" className="inline-block mt-8">
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground group">
              Open full studio
              <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-0.5 transition-transform" />
            </Button>
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
