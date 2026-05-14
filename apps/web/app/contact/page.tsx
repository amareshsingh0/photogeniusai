import { Mail, MessageSquare, Clock } from "lucide-react";

export const metadata = {
  title: "Contact | Pixium AI",
  description: "Get in touch with the Pixium AI team for support, partnerships, or feedback.",
};

export default function ContactPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <p className="kerned text-white/40 mb-3">CONTACT</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight text-white mb-4">
        Say hello.
      </h1>
      <p className="text-lg text-white/60 leading-relaxed mb-12">
        Bug reports, partnerships, press, or just feedback — drop us a line.
      </p>

      <div className="grid sm:grid-cols-2 gap-3 mb-3">
        <a
          href="mailto:support@pixium.ai"
          className="glass-panel rounded-2xl p-5 transition hover:translate-y-[-2px] block"
        >
          <Mail className="h-5 w-5 text-white/70 mb-4" />
          <p className="kerned text-white/40 mb-2">EMAIL</p>
          <h2 className="font-display text-xl tracking-tight text-white mb-1">
            support@pixium.ai
          </h2>
          <p className="text-sm text-white/60">Support, billing, general inquiries.</p>
        </a>
        <a
          href="#"
          className="glass-panel rounded-2xl p-5 transition hover:translate-y-[-2px] block"
        >
          <MessageSquare className="h-5 w-5 text-white/70 mb-4" />
          <p className="kerned text-white/40 mb-2">COMMUNITY</p>
          <h2 className="font-display text-xl tracking-tight text-white mb-1">
            Join Discord
          </h2>
          <p className="text-sm text-white/60">Share work, swap prompts, talk shop.</p>
        </a>
      </div>

      <div className="glass-panel rounded-2xl p-5 mb-3">
        <Clock className="h-5 w-5 text-white/70 mb-4" />
        <p className="kerned text-white/40 mb-2">RESPONSE TIME</p>
        <p className="text-sm text-white/70 leading-relaxed">
          We typically respond within 1–2 business days. For urgent issues, prefix your subject line
          with <span className="font-mono text-[11px] text-white/85">URGENT</span>.
        </p>
      </div>

      <form className="glass-panel rounded-2xl p-5 space-y-4">
        <div>
          <label className="kerned text-white/40 mb-2 block">YOUR EMAIL</label>
          <input
            type="email"
            placeholder="you@studio.com"
            className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30"
          />
        </div>
        <div>
          <label className="kerned text-white/40 mb-2 block">SUBJECT</label>
          <input
            type="text"
            className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30"
          />
        </div>
        <div>
          <label className="kerned text-white/40 mb-2 block">MESSAGE</label>
          <textarea
            rows={5}
            className="w-full rounded-lg border border-white/10 bg-black/20 p-2 text-sm outline-none focus:border-white/30 resize-none"
          />
        </div>
        <button
          type="submit"
          className="rounded-xl px-4 py-2 text-sm font-medium text-black"
          style={{ background: "var(--gradient-aurora)" }}
        >
          Send message
        </button>
      </form>
    </div>
  );
}
