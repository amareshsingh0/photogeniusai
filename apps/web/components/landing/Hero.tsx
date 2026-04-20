"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, useAnimation, useScroll, useTransform } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Sparkles, ArrowRight, ImageIcon, Zap, Wand2 } from "lucide-react";

const EXAMPLE_PROMPTS = [
  "Cyberpunk street market in Tokyo at night, neon reflections, cinematic lighting, 8k --ar 16:9",
  "Portrait of an elven queen in a glowing forest, ethereal, fantasy concept art --v 6.0",
  "Macro photography of a water droplet on a lotus leaf, hyper-realistic, vivid colors",
];

const FLOATING_IMAGES = [
  "https://images.unsplash.com/photo-1682687220742-aba13b6e50ba?auto=format&fit=crop&q=80&w=800",
  "https://images.unsplash.com/photo-1682687982501-1e58f813f228?auto=format&fit=crop&q=80&w=800",
  "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&q=80&w=800",
  "https://images.unsplash.com/photo-1634152962476-4b8a00e1915c?auto=format&fit=crop&q=80&w=800",
  "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&q=80&w=800",
  "https://images.unsplash.com/photo-1549490349-8643362247b5?auto=format&fit=crop&q=80&w=800"
];

export default function Hero() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const { scrollY } = useScroll();
  const y1 = useTransform(scrollY, [0, 1000], [0, -200]);
  const y2 = useTransform(scrollY, [0, 1000], [0, -100]);

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
    <section className="relative min-h-[100vh] flex flex-col items-center justify-center overflow-hidden px-4 pt-32 pb-24 bg-[#030303]">
      {/* Immersive Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
        <motion.div
          className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-violet-600/20 blur-[150px]"
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] rounded-full bg-fuchsia-600/20 blur-[150px]"
          animate={{
            scale: [1.2, 1, 1.2],
            opacity: [0.4, 0.7, 0.4],
          }}
          transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute top-[30%] left-[40%] w-[30%] h-[30%] rounded-full bg-indigo-600/20 blur-[120px]"
          animate={{ opacity: [0.2, 0.5, 0.2] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="absolute inset-0 bg-[url('/noise.png')] opacity-[0.03] mix-blend-overlay" />
      </div>

      {/* Floating Masonry Images (Parallax Background) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-20 sm:opacity-30 z-0">
        <motion.div style={{ y: y1 }} className="absolute -left-10 md:left-10 top-20 flex flex-col gap-6">
          <img src={FLOATING_IMAGES[0]} alt="AI Art" className="w-32 md:w-48 lg:w-64 h-48 md:h-64 lg:h-80 object-cover rounded-2xl blur-[2px]" />
          <img src={FLOATING_IMAGES[1]} alt="AI Art" className="w-32 md:w-48 lg:w-64 h-64 md:h-80 lg:h-96 object-cover rounded-2xl blur-[2px]" />
        </motion.div>
        <motion.div style={{ y: y2 }} className="absolute -right-10 md:right-10 top-40 flex flex-col gap-6">
          <img src={FLOATING_IMAGES[2]} alt="AI Art" className="w-32 md:w-48 lg:w-64 h-64 md:h-80 lg:h-96 object-cover rounded-2xl blur-[2px]" />
          <img src={FLOATING_IMAGES[3]} alt="AI Art" className="w-32 md:w-48 lg:w-64 h-48 md:h-64 lg:h-80 object-cover rounded-2xl blur-[2px]" />
        </motion.div>
      </div>

      <div className="relative z-10 w-full max-w-4xl mx-auto text-center mt-12 md:mt-20">
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/[0.02] backdrop-blur-md mb-8 shadow-[0_0_20px_rgba(255,255,255,0.05)]"
        >
          <Sparkles className="h-4 w-4 text-violet-400" />
          <span className="text-sm font-medium text-white/80 tracking-wide uppercase">
            Pixium Studio v6.0 Now Live
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-black tracking-tighter text-white mb-6 leading-[0.95]"
        >
          Imagine <span className="italic font-light text-white/60">Anything.</span><br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 via-fuchsia-400 to-indigo-400 drop-shadow-[0_0_30px_rgba(139,92,246,0.3)]">
            Create Everything.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="text-lg sm:text-xl md:text-2xl text-zinc-400 mb-12 max-w-2xl mx-auto font-medium"
        >
          The most advanced AI image generation engine. Turn simple text into hyper-realistic photos, illustrations, and 3D art in seconds.
        </motion.p>

        {/* Prompt Input - God Level Glassmorphism */}
        <motion.form
          onSubmit={handleSubmit}
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="w-full mb-8 relative group"
        >
          <div className="absolute -inset-1 bg-gradient-to-r from-violet-500 via-fuchsia-500 to-indigo-500 rounded-3xl blur-xl opacity-20 group-hover:opacity-40 transition-opacity duration-500" />
          <div className="relative flex flex-col sm:flex-row items-center w-full bg-[#0a0a0a]/80 backdrop-blur-2xl rounded-3xl p-2 md:p-3 border border-white/10 shadow-2xl focus-within:border-violet-500/50 focus-within:bg-[#111]/80 transition-all duration-300">
            <div className="flex-1 w-full flex items-center px-4 py-3 sm:py-0">
              <span className="text-violet-400 font-mono text-lg mr-3 hidden sm:block">/imagine</span>
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="A futuristic city in the clouds..."
                className="w-full bg-transparent text-white placeholder:text-zinc-500 text-lg sm:text-xl outline-none font-medium"
                autoFocus
              />
            </div>
            <Button
              type="submit"
              className="w-full sm:w-auto h-14 px-8 rounded-2xl bg-white text-black hover:bg-zinc-200 font-bold text-lg flex items-center gap-2 group/btn transition-all duration-300 shrink-0"
            >
              <Wand2 className="w-5 h-5 group-hover/btn:rotate-12 transition-transform" />
              Generate
            </Button>
          </div>
        </motion.form>

        {/* Example prompts */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="flex flex-col sm:flex-row flex-wrap justify-center items-center gap-3 mb-16"
        >
          <span className="text-sm font-medium text-zinc-500">Try these prompts:</span>
          <div className="flex flex-wrap justify-center gap-2">
            {EXAMPLE_PROMPTS.map((example, i) => (
              <button
                key={i}
                onClick={() => setPrompt(example)}
                className="text-xs sm:text-sm px-4 py-2 rounded-full text-zinc-400 bg-white/[0.03] hover:bg-white/[0.08] hover:text-white border border-white/[0.05] hover:border-white/20 transition-all duration-300 truncate max-w-[200px] sm:max-w-xs"
                title={example}
              >
                {example}
              </button>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Scroll indicator */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
      >
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Scroll to explore</span>
        <motion.div 
          animate={{ y: [0, 8, 0] }} 
          transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
          className="w-0.5 h-12 bg-gradient-to-b from-violet-500/50 to-transparent rounded-full"
        />
      </motion.div>
    </section>
  );
}
