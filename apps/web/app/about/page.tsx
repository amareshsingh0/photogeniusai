import { Target, Heart, Zap } from "lucide-react";

export const metadata = {
  title: "About | Pixium AI",
  description:
    "Learn about Pixium AI — our mission, team, and how we help you turn imagination into stunning images.",
};

const VALUES = [
  {
    icon: Target,
    label: "MISSION",
    title: "Democratize creation",
    body: "Make professional-quality image generation accessible to anyone with an idea — no design skills required.",
  },
  {
    icon: Heart,
    label: "AUDIENCE",
    title: "For everyone",
    body: "Creators, marketers, founders, and teams who need beautiful visuals on demand.",
  },
  {
    icon: Zap,
    label: "SPEED",
    title: "Seconds, not hours",
    body: "Describe, generate, refine, and download — the whole loop in less time than a coffee break.",
  },
];

const TEAM = [
  { initials: "AS", name: "Amaresh Singh", role: "Founder & Engineering" },
  { initials: "PX", name: "Pixium Research", role: "Prompt + Quality" },
  { initials: "PX", name: "Pixium Platform", role: "Infra + Models" },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <p className="kerned text-white/40 mb-3">ABOUT</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight text-white mb-4">
        Imagination,{" "}
        <span className="text-aurora">rendered.</span>
      </h1>
      <p className="text-lg text-white/60 leading-relaxed mb-12">
        Pixium AI turns natural-language ideas into print-ready images. Portraits, products, posters, anime, architecture
        — one prompt, one click, three providers working in parallel to ship the cleanest frame.
      </p>

      <div className="space-y-6 text-white/70 leading-relaxed mb-16">
        <p>
          We built Pixium because the gap between an idea and a finished visual is still measured in hours of
          studio time, stock-photo licenses, and revision cycles. We think it should be measured in seconds.
        </p>
        <p>
          Under the hood, every prompt routes through a Claude-driven brief generator, a 16-bucket intent classifier,
          and a multi-provider stack that picks the cheapest model that matches your aesthetic. You get the result.
          The plumbing stays out of the way.
        </p>
      </div>

      <p className="kerned text-white/40 mb-3">VALUES</p>
      <div className="grid sm:grid-cols-3 gap-3 mb-16">
        {VALUES.map((v) => {
          const Icon = v.icon;
          return (
            <div
              key={v.label}
              className="glass-panel rounded-2xl p-5 transition hover:translate-y-[-2px]"
            >
              <Icon className="h-5 w-5 text-white/70 mb-4" />
              <p className="kerned text-white/40 mb-2">{v.label}</p>
              <h3 className="font-display text-lg text-white mb-2 tracking-tight">{v.title}</h3>
              <p className="text-sm text-white/60 leading-relaxed">{v.body}</p>
            </div>
          );
        })}
      </div>

      <p className="kerned text-white/40 mb-3">TEAM</p>
      <div className="glass-panel rounded-2xl p-5">
        <ul className="divide-y divide-white/5">
          {TEAM.map((m) => (
            <li key={m.name} className="flex items-center gap-4 py-3 first:pt-0 last:pb-0">
              <div className="h-10 w-10 rounded-full bg-white/5 hairline flex items-center justify-center">
                <span className="font-mono text-[11px] text-white/70">{m.initials}</span>
              </div>
              <div className="flex-1">
                <p className="text-sm text-white/85">{m.name}</p>
                <p className="text-xs text-white/50">{m.role}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
