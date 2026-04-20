"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Sparkles, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const navLinks = [
  { name: "Explore", href: "#explore" },
  { name: "Create", href: "#create" },
  { name: "Community", href: "#gallery" },
  { name: "Pricing", href: "#pricing" },
];

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled 
          ? "border-b border-white/[0.04] bg-[#030303]/80 backdrop-blur-3xl shadow-[0_4px_30px_rgba(0,0,0,0.5)]" 
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 md:h-20">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-2xl bg-gradient-to-tr from-violet-600 via-fuchsia-600 to-indigo-600 shadow-[0_0_20px_rgba(139,92,246,0.4)] group-hover:shadow-[0_0_30px_rgba(139,92,246,0.6)] transition-all duration-300">
              <div className="absolute inset-[1px] rounded-[15px] bg-[#050505] opacity-50 group-hover:opacity-0 transition-opacity duration-300" />
              <Sparkles className="relative h-4 w-4 text-white z-10" strokeWidth={2.5} />
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-black text-white tracking-tighter leading-none">PIXIUM</span>
              <span className="text-[9px] uppercase tracking-[0.3em] text-white/50 font-bold mt-0.5">Studio</span>
            </div>
          </Link>

          <div className="hidden md:flex items-center gap-1 p-1 rounded-full bg-white/[0.02] border border-white/[0.05] backdrop-blur-md">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="px-5 py-2 text-sm font-medium text-zinc-400 hover:text-white rounded-full hover:bg-white/[0.06] transition-all duration-300"
              >
                {link.name}
              </Link>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-4">
            {!mounted ? (
              <div className="w-24 h-10 rounded-full bg-white/[0.05] animate-pulse" />
            ) : (
              <>
                <Link href="/login">
                  <Button size="sm" variant="ghost" className="text-sm font-medium text-zinc-400 hover:text-white hover:bg-white/5 rounded-full px-4">
                    Sign In
                  </Button>
                </Link>
                <Link href="/generate">
                  <Button size="sm" className="relative group overflow-hidden rounded-full px-6 h-10 bg-white text-black hover:bg-zinc-200 transition-all duration-300">
                    <span className="relative z-10 flex items-center gap-2 font-bold tracking-tight">
                      Launch App <Wand2 className="h-3.5 w-3.5" />
                    </span>
                    <div className="absolute inset-0 bg-gradient-to-r from-violet-200 via-fuchsia-200 to-indigo-200 opacity-0 group-hover:opacity-100 transition-opacity duration-500 blur-md" />
                  </Button>
                </Link>
              </>
            )}
          </div>

          <button
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden p-2.5 -mr-2 rounded-full text-white hover:bg-white/10 transition-colors"
            aria-label="Toggle menu"
          >
            {isOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="md:hidden absolute top-full left-0 right-0 border-b border-white/[0.04] bg-[#030303]/95 backdrop-blur-2xl"
          >
            <div className="p-4 space-y-2">
              {navLinks.map((link) => (
                <Link
                  key={link.name}
                  href={link.href}
                  className="block py-3 px-4 text-base font-medium text-zinc-400 hover:text-white rounded-xl hover:bg-white/[0.04] transition-colors"
                  onClick={() => setIsOpen(false)}
                >
                  {link.name}
                </Link>
              ))}
              <div className="pt-4 mt-2 border-t border-white/[0.04] space-y-3">
                <Link href="/login" onClick={() => setIsOpen(false)} className="block">
                  <Button variant="outline" className="w-full rounded-xl h-12 border-white/10 bg-transparent text-white hover:bg-white/5">Sign In</Button>
                </Link>
                <Link href="/generate" onClick={() => setIsOpen(false)} className="block">
                  <Button className="w-full rounded-xl h-12 bg-white text-black hover:bg-zinc-200 font-bold">Launch App</Button>
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}

