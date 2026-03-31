"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Eye, EyeOff, Sparkles, ArrowRight, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const devSignUp = async (emailVal?: string, nameVal?: string) => {
    setLoading(true);
    document.cookie = "dev_session=dev_user_123; path=/; max-age=86400";
    localStorage.setItem(
      "dev_user",
      JSON.stringify({
        id: "dev_user_123",
        email: emailVal || "dev@photogenius.local",
        name: nameVal || emailVal?.split("@")[0] || "User",
      })
    );
    await new Promise((r) => setTimeout(r, 800));
    router.push("/dashboard");
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = "Name is required";
    if (!email.trim()) e.email = "Email is required";
    else if (!/\S+@\S+\.\S+/.test(email)) e.email = "Enter a valid email";
    if (!password.trim()) e.password = "Password is required";
    else if (password.length < 8) e.password = "At least 8 characters";
    if (!agreed) e.agreed = "You must accept the terms";
    return e;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    await devSignUp(email, name);
  };

  const passwordStrength = password.length === 0 ? 0 : password.length < 6 ? 1 : password.length < 10 ? 2 : 3;
  const strengthLabel = ["", "Weak", "Good", "Strong"][passwordStrength];
  const strengthColor = ["", "bg-red-500", "bg-yellow-500", "bg-emerald-500"][passwordStrength];

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex">
      {/* Left — Visual */}
      <div className="hidden lg:flex flex-1 relative overflow-hidden bg-gradient-to-br from-indigo-950/30 via-zinc-900/50 to-[#0a0a0a] order-first">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(99,102,241,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(99,102,241,0.03)_1px,transparent_1px)] bg-[size:40px_40px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col items-center justify-center w-full px-16 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <div className="grid grid-cols-3 gap-2 mb-10 max-w-[200px] mx-auto">
              {[
                "bg-violet-500/20",
                "bg-indigo-500/30",
                "bg-violet-600/25",
                "bg-indigo-400/20",
                "bg-violet-400/30",
                "bg-indigo-500/20",
                "bg-violet-500/25",
                "bg-indigo-600/20",
                "bg-violet-400/20",
              ].map((bg, i) => (
                <div
                  key={i}
                  className={cn("aspect-square rounded-xl", bg, "border border-white/5")}
                />
              ))}
            </div>

            <h2 className="text-3xl font-bold text-white mb-4 leading-tight">
              Start creating<br />
              <span className="bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
                for free today
              </span>
            </h2>
            <p className="text-zinc-500 text-sm leading-relaxed max-w-xs mx-auto">
              Join thousands of creators using AI to generate stunning, professional-quality images.
            </p>

            <div className="mt-10 space-y-3 max-w-xs mx-auto">
              {[
                { label: "10 free credits to start" },
                { label: "No credit card required" },
                { label: "Cancel anytime" },
              ].map(({ label }) => (
                <div key={label} className="flex items-center gap-3">
                  <div className="w-5 h-5 rounded-full bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
                    <Check className="w-3 h-3 text-emerald-400" />
                  </div>
                  <span className="text-sm text-zinc-400 text-left">{label}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Right — Form */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 lg:px-16">
        <Link href="/" className="flex items-center gap-2.5 mb-10 self-start lg:self-auto">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
            <Sparkles className="w-[18px] h-[18px] text-white" />
          </div>
          <span className="text-base font-bold text-white tracking-tight">PhotoGenius</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-violet-500/15 text-violet-400 font-bold tracking-widest border border-violet-500/20">AI</span>
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm"
        >
          <h1 className="text-2xl font-bold text-white mb-1.5">Create your account</h1>
          <p className="text-zinc-500 text-sm mb-8">Get started with 10 free credits.</p>

          {/* Social buttons */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            {[
              {
                label: "Google",
                icon: (
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                ),
              },
              {
                label: "Apple",
                icon: (
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"/>
                  </svg>
                ),
              },
            ].map((provider) => (
              <button
                key={provider.label}
                type="button"
                onClick={() => devSignUp()}
                disabled={loading}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-zinc-800 bg-zinc-900/60 text-sm text-zinc-300 hover:border-zinc-600 hover:text-white hover:bg-zinc-800/60 transition-all disabled:opacity-50"
              >
                {provider.icon}
                <span>{provider.label}</span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-zinc-800" />
            <span className="text-xs text-zinc-600">or</span>
            <div className="flex-1 h-px bg-zinc-800" />
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => { setName(e.target.value); setErrors((p) => ({ ...p, name: "" })); }}
                placeholder="Your name"
                autoComplete="name"
                className={cn(
                  "w-full px-4 py-3 rounded-xl bg-zinc-900/80 border text-white placeholder:text-zinc-600 text-sm focus:outline-none transition-all",
                  errors.name ? "border-red-500/50" : "border-zinc-800 focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20"
                )}
              />
              {errors.name && <p className="text-xs text-red-400 mt-1">{errors.name}</p>}
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setErrors((p) => ({ ...p, email: "" })); }}
                placeholder="you@example.com"
                autoComplete="email"
                className={cn(
                  "w-full px-4 py-3 rounded-xl bg-zinc-900/80 border text-white placeholder:text-zinc-600 text-sm focus:outline-none transition-all",
                  errors.email ? "border-red-500/50" : "border-zinc-800 focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20"
                )}
              />
              {errors.email && <p className="text-xs text-red-400 mt-1">{errors.email}</p>}
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-2 uppercase tracking-wider">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: "" })); }}
                  placeholder="Min. 8 characters"
                  autoComplete="new-password"
                  className={cn(
                    "w-full px-4 py-3 rounded-xl bg-zinc-900/80 border text-white placeholder:text-zinc-600 text-sm pr-11 focus:outline-none transition-all",
                    errors.password ? "border-red-500/50" : "border-zinc-800 focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20"
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {/* Password strength */}
              {password.length > 0 && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex gap-1 flex-1">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className={cn(
                          "h-1 flex-1 rounded-full transition-all",
                          i <= passwordStrength ? strengthColor : "bg-zinc-800"
                        )}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-zinc-500">{strengthLabel}</span>
                </div>
              )}
              {errors.password && <p className="text-xs text-red-400 mt-1">{errors.password}</p>}
            </div>

            {/* Terms */}
            <div>
              <label className="flex items-start gap-3 cursor-pointer group">
                <div
                  onClick={() => { setAgreed(!agreed); setErrors((p) => ({ ...p, agreed: "" })); }}
                  className={cn(
                    "w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0 mt-0.5 transition-all cursor-pointer",
                    agreed ? "bg-violet-600 border-violet-600" : "bg-zinc-900 border-zinc-700 group-hover:border-zinc-500"
                  )}
                >
                  {agreed && <Check className="w-3 h-3 text-white" />}
                </div>
                <span className="text-xs text-zinc-500 leading-relaxed">
                  I agree to the{" "}
                  <Link href="/terms" className="text-violet-400 hover:text-violet-300">Terms of Service</Link>
                  {" "}and{" "}
                  <Link href="/privacy" className="text-violet-400 hover:text-violet-300">Privacy Policy</Link>
                </span>
              </label>
              {errors.agreed && <p className="text-xs text-red-400 mt-1 ml-8">{errors.agreed}</p>}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold hover:from-violet-500 hover:to-indigo-500 transition-all shadow-lg shadow-violet-500/20 disabled:opacity-60 disabled:cursor-not-allowed mt-1"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating account...
                </span>
              ) : (
                <>
                  Create account
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-zinc-600 mt-7">
            Already have an account?{" "}
            <Link href="/login" className="text-violet-400 hover:text-violet-300 font-medium transition-colors">
              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
