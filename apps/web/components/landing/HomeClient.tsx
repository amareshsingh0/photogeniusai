"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { motion } from "framer-motion";
import Navbar from "@/components/landing/Navbar";
import Hero from "@/components/landing/Hero";
import Footer from "@/components/landing/Footer";
import { Camera, Film, Heart, Sparkles, Building2, Package, Gamepad2, ArrowRight } from "lucide-react";

function SectionLoader() {
  return <div className="min-h-[200px] animate-pulse bg-white/5 rounded-3xl mx-4 my-6" />;
}

const CATEGORIES = [
  { title: "Cinematic Realms", desc: "Movie-quality scenes with dramatic lighting", icon: Film, bg: "bg-zinc-900", border: "border-fuchsia-500/20", col: "md:col-span-2 md:row-span-2", img: "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&q=80&w=800" },
  { title: "Professional Portraits", desc: "Studio-quality headshots and editorial portraits", icon: Camera, bg: "bg-zinc-900", border: "border-blue-500/20", col: "md:col-span-1 md:row-span-1", img: "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&q=80&w=800" },
  { title: "Anime & Illustration", desc: "Beautiful manga art and illustration styles", icon: Heart, bg: "bg-zinc-900", border: "border-pink-500/20", col: "md:col-span-1 md:row-span-1", img: "https://images.unsplash.com/photo-1549490349-8643362247b5?auto=format&fit=crop&q=80&w=800" },
  { title: "Fantasy Worlds", desc: "Magical landscapes and mythical creatures", icon: Sparkles, bg: "bg-zinc-900", border: "border-violet-500/20", col: "md:col-span-2 md:row-span-1", img: "https://images.unsplash.com/photo-1682687220742-aba13b6e50ba?auto=format&fit=crop&q=80&w=800" },
];

function CreateSection() {
  return (
    <section id="create" className="py-32 px-4 relative bg-[#030303]">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-0 w-[500px] h-[500px] bg-violet-600/10 blur-[150px] rounded-full" />
        <div className="absolute top-1/2 right-0 w-[500px] h-[500px] bg-indigo-600/10 blur-[150px] rounded-full" />
      </div>
      <div className="max-w-[1400px] mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-20"
        >
          <h2 className="text-4xl md:text-5xl lg:text-7xl font-black text-white mb-6 tracking-tighter">
            Unlimited <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-fuchsia-400">Potential</span>
          </h2>
          <p className="text-xl text-zinc-400 max-w-2xl mx-auto font-medium">
            From hyper-realistic portraits to vast fantasy worlds, Pixium adapts to your imagination.
          </p>
        </motion.div>

        {/* Bento Grid Layout */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[250px]">
          {CATEGORIES.map((cat, i) => {
            const Icon = cat.icon;
            return (
              <motion.div
                key={cat.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className={`relative group rounded-[2rem] overflow-hidden ${cat.col} border ${cat.border} ${cat.bg} hover:border-white/20 transition-all duration-500 cursor-pointer`}
              >
                <img src={cat.img} alt={cat.title} className="absolute inset-0 w-full h-full object-cover opacity-40 group-hover:opacity-60 group-hover:scale-105 transition-all duration-700 mix-blend-luminosity group-hover:mix-blend-normal" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />
                <div className="absolute inset-0 p-8 flex flex-col justify-end">
                  <div className="w-12 h-12 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center mb-6 group-hover:-translate-y-2 transition-transform duration-500">
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="text-2xl md:text-3xl font-bold text-white mb-3 tracking-tight group-hover:-translate-y-1 transition-transform duration-500">{cat.title}</h3>
                  <p className="text-zinc-400 font-medium group-hover:text-zinc-300 transition-colors duration-500">{cat.desc}</p>
                </div>
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
    <div className="min-h-screen w-full bg-[#030303] text-white relative overflow-x-hidden selection:bg-violet-500/30">
      {/* Global Ambient Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-[-1] bg-[#030303]">
        <div className="absolute inset-0 bg-[url('/noise.png')] opacity-[0.02] mix-blend-overlay" />
      </div>

      <Navbar />
      <Hero />
      <div className="relative z-10 bg-[#030303]">
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
    </div>
  );
}
