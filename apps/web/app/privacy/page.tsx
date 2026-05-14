import Link from "next/link";

export const metadata = {
  title: "Privacy Policy | Pixium AI",
  description: "Pixium AI privacy policy — how we collect, use, and protect your data.",
};

const SECTIONS = [
  {
    title: "1. Information we collect",
    body: "We collect information you provide when you sign up, use the service, or contact us — such as email, name, account details, prompts and images you create, and usage data. We may also collect technical data like IP address and device information.",
  },
  {
    title: "2. How we use your information",
    body: "We use your information to provide and improve Pixium AI, process generations, communicate with you, enforce our terms, and comply with law. We do not sell your personal information to third parties.",
  },
  {
    title: "3. Data storage & security",
    body: "Your data is stored securely. We use industry-standard measures to protect your information. Generated images and prompts may be processed by our AI providers in accordance with their policies and our agreements.",
  },
  {
    title: "4. Your rights",
    body: "Depending on your location, you may have rights to access, correct, delete, or port your data, and to object to or restrict certain processing. You can manage preferences and data in your account settings or contact us.",
  },
  {
    title: "5. Cookies & similar technologies",
    body: "We use cookies and similar technologies for authentication, preferences, and analytics. You can control cookies through your browser settings.",
  },
  {
    title: "6. Changes",
    body: "We may update this policy from time to time. We will notify you of material changes via the service or email where appropriate.",
  },
];

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <p className="kerned text-white/40 mb-3">LEGAL</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight text-white mb-3">
        Privacy Policy
      </h1>
      <p className="font-mono text-[11px] text-white/50 mb-12">LAST UPDATED · FEBRUARY 2026</p>

      <div className="glass-panel rounded-2xl p-6 space-y-8">
        {SECTIONS.map((s) => (
          <section key={s.title}>
            <h2 className="font-display text-xl tracking-tight text-white mb-2">{s.title}</h2>
            <p className="text-sm text-white/70 leading-relaxed">{s.body}</p>
          </section>
        ))}
        <p className="text-sm text-white/60 pt-4 border-t border-white/5">
          For questions, contact{" "}
          <a href="mailto:privacy@pixium.ai" className="text-white/85 hover:text-white underline">
            privacy@pixium.ai
          </a>{" "}
          or visit the{" "}
          <Link href="/contact" className="text-white/85 hover:text-white underline">
            contact
          </Link>{" "}
          page.
        </p>
      </div>
    </div>
  );
}
