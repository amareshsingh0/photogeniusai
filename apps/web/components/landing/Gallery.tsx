"use client";

import { motion } from "framer-motion";
import { Copy, Heart, Sparkles, Download } from "lucide-react";

const GALLERY_ITEMS = [
  {
    id: 1,
    url: "https://images.unsplash.com/photo-1682687982501-1e58f813f228?auto=format&fit=crop&q=80&w=800",
    prompt: "Cinematic portrait of a cyberpunk bounty hunter, neon city background, 8k resolution, photorealistic --ar 4:5",
    height: "h-[400px]",
    likes: "12.4k"
  },
  {
    id: 2,
    url: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&q=80&w=800",
    prompt: "Abstract liquid gold and dark matter swirling, macro photography, high contrast --v 6.0",
    height: "h-[300px]",
    likes: "8.2k"
  },
  {
    id: 3,
    url: "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&q=80&w=800",
    prompt: "A massive ancient tree glowing with bioluminescence in a dark mystical forest, ethereal lighting",
    height: "h-[500px]",
    likes: "15k"
  },
  {
    id: 4,
    url: "https://images.unsplash.com/photo-1634152962476-4b8a00e1915c?auto=format&fit=crop&q=80&w=800",
    prompt: "Futuristic spaceship interior, sleek white panels, glowing blue accents, cinematic lighting",
    height: "h-[350px]",
    likes: "9.1k"
  },
  {
    id: 5,
    url: "https://images.unsplash.com/photo-1549490349-8643362247b5?auto=format&fit=crop&q=80&w=800",
    prompt: "Minimalist architecture in the desert at sunset, brutalist concrete, warm orange lighting",
    height: "h-[450px]",
    likes: "11.3k"
  },
  {
    id: 6,
    url: "https://images.unsplash.com/photo-1682687220742-aba13b6e50ba?auto=format&fit=crop&q=80&w=800",
    prompt: "Epic fantasy mountain landscape, dragon flying in the distance, dramatic clouds --ar 16:9",
    height: "h-[280px]",
    likes: "14.7k"
  }
];

export default function Gallery() {
  return (
    <section id="gallery" className="py-32 px-4 relative bg-[#030303] overflow-hidden">
      {/* Background Glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-10 w-96 h-96 bg-violet-900/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-1/4 right-10 w-96 h-96 bg-indigo-900/10 blur-[120px] rounded-full" />
      </div>

      <div className="max-w-[1400px] mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/[0.02] mb-6">
            <Sparkles className="h-4 w-4 text-fuchsia-400" />
            <span className="text-xs font-semibold tracking-widest uppercase text-zinc-400">Community Feed</span>
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-black text-white mb-6 tracking-tighter">
            Created by the <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-fuchsia-400">Community</span>
          </h2>
          <p className="text-xl text-zinc-400 max-w-2xl mx-auto font-medium">
            Discover the endless possibilities of Pixium Studio. Get inspired by what others are generating.
          </p>
        </motion.div>

        {/* Masonry-style Grid */}
        <div className="columns-1 md:columns-2 lg:columns-3 gap-6 space-y-6">
          {GALLERY_ITEMS.map((item, i) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className={`relative group rounded-3xl overflow-hidden break-inside-avoid bg-zinc-900 border border-white/5 ${item.height}`}
            >
              <img
                src={item.url}
                alt={item.prompt}
                className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                loading="lazy"
              />
              
              {/* Glassmorphic Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-all duration-300 flex flex-col justify-end p-6">
                <p className="text-white font-medium text-sm md:text-base leading-snug mb-4 line-clamp-3">
                  "{item.prompt}"
                </p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-white/70 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-full text-xs font-semibold">
                    <Heart className="w-3.5 h-3.5 fill-current" />
                    {item.likes}
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="p-2 rounded-full bg-white/10 backdrop-blur-md text-white hover:bg-white/20 transition-colors" title="Copy Prompt">
                      <Copy className="w-4 h-4" />
                    </button>
                    <button className="p-2 rounded-full bg-white text-black hover:bg-zinc-200 transition-colors" title="Download">
                      <Download className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mt-16 text-center"
        >
          <button className="px-8 py-4 rounded-full bg-white/[0.03] border border-white/10 text-white font-semibold hover:bg-white/[0.08] transition-all duration-300">
            View Full Gallery
          </button>
        </motion.div>
      </div>
    </section>
  );
}
