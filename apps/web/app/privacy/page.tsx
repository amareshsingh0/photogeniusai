import Link from "next/link"
import { Sparkles } from "lucide-react"

export const metadata = {
  title: "Privacy Policy | PhotoGenius AI",
  description: "PhotoGenius AI privacy policy — how we collect, use, and protect your data.",
}

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-zinc-950">
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/[0.08] bg-zinc-950/70 backdrop-blur-2xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
                <Sparkles className="h-4 w-4 text-white" strokeWidth={2.5} />
              </div>
              <span className="text-lg font-bold text-white tracking-tight">PhotoGenius</span>
              <span className="text-[10px] uppercase tracking-widest text-purple-400 font-bold px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/20">AI</span>
            </Link>
            <div className="hidden md:flex items-center gap-8">
              <Link href="/#features" className="text-sm text-zinc-400 hover:text-white transition-colors">Features</Link>
              <Link href="/#create" className="text-sm text-zinc-400 hover:text-white transition-colors">What You Can Create</Link>
              <Link href="/#how" className="text-sm text-zinc-400 hover:text-white transition-colors">How It Works</Link>
            </div>
            <div className="flex items-center gap-3">
              <Link href="/login" className="text-sm text-zinc-400 hover:text-white transition-colors hidden sm:block">Sign In</Link>
              <Link href="/generate" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white text-sm font-semibold shadow-lg shadow-purple-500/25 transition-all">
                <Sparkles className="h-4 w-4" strokeWidth={2.5} /> Start Creating
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="pt-28 pb-20">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">Privacy Policy</h1>
          <p className="text-zinc-500 text-sm mb-12">Last updated: February 2026</p>

          <div className="prose prose-invert prose-zinc max-w-none space-y-8 text-zinc-300">
            <section>
              <h2 className="text-xl font-semibold text-white mb-3">1. Information We Collect</h2>
              <p className="leading-relaxed">We collect information you provide when you sign up, use the service, or contact us — such as email, name, account details, prompts and images you create, and usage data (e.g. how you use the product). We may also collect technical data like IP address and device information.</p>
            </section>
            <section>
              <h2 className="text-xl font-semibold text-white mb-3">2. How We Use Your Information</h2>
              <p className="leading-relaxed">We use your information to provide and improve PhotoGenius AI, to process generations, to communicate with you, to enforce our terms, and to comply with law. We do not sell your personal information to third parties.</p>
            </section>
            <section>
              <h2 className="text-xl font-semibold text-white mb-3">3. Data Storage & Security</h2>
              <p className="leading-relaxed">Your data is stored securely. We use industry-standard measures to protect your information. Generated images and prompts may be processed by our AI providers in accordance with their policies and our agreements.</p>
            </section>
            <section>
              <h2 className="text-xl font-semibold text-white mb-3">4. Your Rights</h2>
              <p className="leading-relaxed">Depending on your location, you may have rights to access, correct, delete, or port your data, and to object to or restrict certain processing. You can manage preferences and data in your account settings or contact us.</p>
            </section>
            <section>
              <h2 className="text-xl font-semibold text-white mb-3">5. Cookies & Similar Technologies</h2>
              <p className="leading-relaxed">We use cookies and similar technologies for authentication, preferences, and analytics. You can control cookies through your browser settings.</p>
            </section>
            <section>
              <h2 className="text-xl font-semibold text-white mb-3">6. Changes</h2>
              <p className="leading-relaxed">We may update this policy from time to time. We will notify you of material changes via the service or email where appropriate.</p>
            </section>
            <p className="text-zinc-400 text-sm pt-4">For questions about this Privacy Policy, contact us at <a href="mailto:privacy@photogenius.ai" className="text-purple-400 hover:underline">privacy@photogenius.ai</a> or via the <Link href="/contact" className="text-purple-400 hover:underline">Contact</Link> page.</p>
          </div>
        </div>
      </main>

      <footer className="border-t border-white/[0.08] bg-zinc-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-8 lg:gap-12">
            <div className="lg:col-span-5">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
                  <Sparkles className="h-4 w-4 text-white" strokeWidth={2.5} />
                </div>
                <span className="text-xl font-bold text-white">PhotoGenius AI</span>
              </div>
              <p className="text-sm text-zinc-400 leading-relaxed mb-4">Turn imagination into stunning images. Professional-quality AI image generation for portraits, anime, architecture, products, and more.</p>
              <div className="flex items-center gap-3 flex-wrap">
                <a href="https://linkedin.com/company/photogenius-ai" target="_blank" rel="noopener noreferrer" className="text-zinc-600 hover:text-zinc-400 transition-colors" aria-label="LinkedIn">
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                </a>
                <a href="https://x.com/photogeniusai" target="_blank" rel="noopener noreferrer" className="text-zinc-600 hover:text-zinc-400 transition-colors" aria-label="X (Twitter)">
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                </a>
                <a href="https://facebook.com/photogeniusai" target="_blank" rel="noopener noreferrer" className="text-zinc-600 hover:text-zinc-400 transition-colors" aria-label="Meta (Facebook)">
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                </a>
                <a href="https://instagram.com/photogeniusai" target="_blank" rel="noopener noreferrer" className="text-zinc-600 hover:text-zinc-400 transition-colors" aria-label="Instagram">
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                </a>
                <a href="https://youtube.com/@photogeniusai" target="_blank" rel="noopener noreferrer" className="text-zinc-600 hover:text-zinc-400 transition-colors" aria-label="YouTube">
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                </a>
                <a href="https://discord.com/invite/photogeniusai" target="_blank" rel="noopener noreferrer" className="text-zinc-600 hover:text-zinc-400 transition-colors" aria-label="Discord">
                  <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026 13.83 13.83 0 0 0 1.226-1.963.074.074 0 0 0-.041-.104 13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0 a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028zM8.02 15.278c-1.182 0-2.157-1.069-2.157-2.38 0-1.312.956-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.956 2.38-2.157 2.38zm7.975 0c-1.183 0-2.157-1.069-2.157-2.38 0-1.312.955-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.946 2.38-2.157 2.38z"/></svg>
                </a>
              </div>
            </div>
            <div className="lg:col-span-2">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-4">Product</h3>
              <ul className="space-y-3">
                <li><Link href="/generate" className="text-sm text-zinc-400 hover:text-white transition-colors">AI Generator</Link></li>
                <li><Link href="/gallery" className="text-sm text-zinc-400 hover:text-white transition-colors">Gallery</Link></li>
                <li><Link href="/pricing" className="text-sm text-zinc-400 hover:text-white transition-colors">Pricing</Link></li>
              </ul>
            </div>
            <div className="lg:col-span-2">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-4">Company</h3>
              <ul className="space-y-3">
                <li><Link href="/about" className="text-sm text-zinc-400 hover:text-white transition-colors">About</Link></li>
                <li><Link href="/blog" className="text-sm text-zinc-400 hover:text-white transition-colors">Blog</Link></li>
                <li><Link href="/contact" className="text-sm text-zinc-400 hover:text-white transition-colors">Contact</Link></li>
              </ul>
            </div>
            <div className="lg:col-span-3">
              <h3 className="text-xs font-bold text-zinc-500 uppercase tracking-wider mb-4">Legal</h3>
              <ul className="space-y-3">
                <li><Link href="/privacy" className="text-sm text-zinc-400 hover:text-white transition-colors">Privacy Policy</Link></li>
                <li><Link href="/terms" className="text-sm text-zinc-400 hover:text-white transition-colors">Terms of Service</Link></li>
              </ul>
            </div>
          </div>
          <div className="mt-12 pt-8 border-t border-white/[0.08] flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-sm text-zinc-500">© 2026 PhotoGenius AI. All rights reserved.</p>
            <p className="text-sm text-zinc-400"><span className="inline-flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span>Imagination to Reality.</span></p>
          </div>
        </div>
      </footer>
    </div>
  )
}
