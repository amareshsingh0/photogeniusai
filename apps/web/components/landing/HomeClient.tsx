"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { motion } from "framer-motion";
import Navbar from "@/components/landing/Navbar";
import Hero from "@/components/landing/Hero";
import Footer from "@/components/landing/Footer";
import { Camera, Film, Heart, Package, Building2, Sparkles, UtensilsCrossed, TreePine, Gamepad2 } from "lucide-react";

function SectionLoader() {
  return <div className="min-h-[200px] animate-pulse bg-muted/20 rounded-xl mx-4 my-6" />;
}

const CATEGORIES = [
  { title: "Professional Portraits", desc: "Studio-quality headshots, editorial portraits, and professional photography", icon: Camera, color: "from-blue-900/80 to-blue-800/60", prompt: "Professional headshot with soft studio lighting, 85mm lens" },
  { title: "Cinematic Scenes", desc: "Movie-quality scenes with dramatic lighting and professional composition", icon: Film, color: "from-amber-900/80 to-amber-800/60", prompt: "Cinematic wide shot of a misty forest at dawn" },
  { title: "Anime & Illustration", desc: "Beautiful anime characters, manga art, and illustration styles", icon: Heart, color: "from-pink-900/80 to-rose-800/60", prompt: "Anime girl with cherry blossoms, ghibli art style" },
  { title: "Fantasy Worlds", desc: "Magical landscapes, mythical creatures, and epic fantasy scenes", icon: Sparkles, color: "from-purple-900/80 to-violet-800/60", prompt: "Dragon flying over ancient castle at sunset" },
  { title: "Architecture & Interiors", desc: "Stunning buildings, interior design concepts, and architectural visualization", icon: Building2, color: "from-emerald-900/80 to-teal-800/60", prompt: "Modern minimalist house with infinity pool, aerial view" },
  { title: "Product Photography", desc: "Clean, professional product shots for brands and e-commerce", icon: Package, color: "from-orange-900/80 to-red-800/60", prompt: "Premium headphones on marble surface, studio lighting" },
  { title: "Food Photography", desc: "Appetizing cuisine shots that make viewers hungry", icon: UtensilsCrossed, color: "from-red-900/80 to-pink-800/60", prompt: "Gourmet sushi platter, top-down view, restaurant quality" },
  { title: "Nature & Landscapes", desc: "Breathtaking landscapes, wildlife, and natural phenomena", icon: TreePine, color: "from-green-900/80 to-emerald-800/60", prompt: "Northern lights over frozen lake, mirror reflection" },
  { title: "Cyberpunk & Sci-Fi", desc: "Neon-lit futuristic worlds and science fiction concepts", icon: Gamepad2, color: "from-cyan-900/80 to-blue-800/60", prompt: "Cyberpunk city alley, neon signs, rain puddle reflections" },
];

function CreateSection() {
  return (
    <section id="create" className="py-28 px-4 relative">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-0 w-1/3 h-80 bg-primary/5 blur-[100px] rounded-full" />
        <div className="absolute top-1/2 right-0 w-1/3 h-80 bg-indigo-500/5 blur-[100px] rounded-full" />
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
            What You Can <span className="gradient-text">Create</span>
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            From professional portraits to fantasy worlds — bring any idea to life.
          </p>
        </motion.div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {CATEGORIES.map((cat, i) => {
            const Icon = cat.icon;
            return (
              <motion.div
                key={cat.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
              >
                <Link href={`/generate?prompt=${encodeURIComponent(cat.prompt)}`}>
                  <div className={`group relative p-6 rounded-2xl bg-gradient-to-br ${cat.color} border border-white/10 hover:border-white/25 transition-all cursor-pointer h-full overflow-hidden`}>
                    <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    <div className="relative">
                      <div className="inline-flex p-2.5 rounded-xl bg-white/10 mb-4">
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      <h3 className="text-base font-bold text-white mb-2">{cat.title}</h3>
                      <p className="text-sm text-white/70 mb-4">{cat.desc}</p>
                      <p className="text-xs text-white/50 italic flex items-center gap-1">
                        <span className="text-white/40">▷</span> &quot;{cat.prompt}&quot;
                      </p>
                    </div>
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

const InstantMagicPreview = dynamic(
  () => import("@/components/landing/InstantMagicPreview"),
  { loading: () => <SectionLoader />, ssr: false }
);
const Gallery = dynamic(
  () => import("@/components/landing/Gallery"),
  { loading: () => <SectionLoader /> }
);
const Features = dynamic(
  () => import("@/components/landing/Features"),
  { loading: () => <SectionLoader /> }
);
const HowItWorks = dynamic(
  () => import("@/components/landing/HowItWorks"),
  { loading: () => <SectionLoader /> }
);
const Safety = dynamic(
  () => import("@/components/landing/Safety"),
  { loading: () => <SectionLoader /> }
);
const Testimonials = dynamic(
  () => import("@/components/landing/Testimonials"),
  { loading: () => <SectionLoader /> }
);
const Pricing = dynamic(
  () => import("@/components/landing/Pricing"),
  { loading: () => <SectionLoader /> }
);
const CTA = dynamic(
  () => import("@/components/landing/CTA"),
  { loading: () => <SectionLoader /> }
);

export default function HomeClient() {
  return (
    <div className="min-h-screen w-full bg-background relative overflow-x-hidden">
      {/* Ambient background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden -z-10">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[120%] h-[60vh] bg-gradient-to-b from-primary/[0.04] via-transparent to-transparent" />
        <div className="absolute bottom-0 left-0 w-1/2 h-[40vh] bg-indigo-500/[0.03] blur-[120px] rounded-full" />
        <div className="absolute bottom-1/3 right-0 w-1/3 h-96 bg-primary/[0.02] blur-[100px] rounded-full" />
      </div>

      <Navbar />
      <Hero />
      <InstantMagicPreview />
      <section id="features">
        <Features />
      </section>
      <CreateSection />
      <Gallery />
      <section id="how">
        <HowItWorks />
      </section>
      <section id="safety">
        <Safety />
      </section>
      <Testimonials />
      <section id="pricing">
        <Pricing />
      </section>
      <CTA />
      <Footer />
    </div>
  );
}
