import Link from "next/link";

export const metadata = {
  title: "Terms of Service | Pixium AI",
  description: "Pixium AI terms of service — rules and conditions for using our platform.",
};

const SECTIONS = [
  {
    title: "1. Acceptance of terms",
    body: "By accessing or using Pixium AI (the “Service”), you agree to these Terms of Service. If you do not agree, do not use the Service.",
  },
  {
    title: "2. Use of the service",
    body: "You may use the Service only for lawful purposes. You must not use it to generate content that is illegal, harmful, infringing, or that violates others’ rights. You are responsible for your prompts and how you use generated images.",
  },
  {
    title: "3. Account & eligibility",
    body: "You must provide accurate information when creating an account. You must be at least 13 years old (or the minimum age in your jurisdiction). You are responsible for keeping your account secure.",
  },
  {
    title: "4. Subscriptions & payment",
    body: "Paid plans are billed according to the pricing shown at the time of purchase. Fees are non-refundable except where required by law or stated in our refund policy. We may change pricing with notice.",
  },
  {
    title: "5. Intellectual property & your content",
    body: "You retain rights to the content you create, subject to a license to us to operate and improve the Service. We do not claim ownership of your generated images. Do not upload or generate content you do not have rights to use.",
  },
  {
    title: "6. Prohibited conduct",
    body: "You may not: reverse-engineer or misuse the Service; resell or redistribute access; use automated means to abuse the API or site; or attempt to gain unauthorized access to our systems or other users’ accounts.",
  },
  {
    title: "7. Disclaimers",
    body: "The Service is provided “as is.” We do not guarantee uninterrupted or error-free operation. AI-generated content may be imperfect; use at your own discretion.",
  },
  {
    title: "8. Limitation of liability",
    body: "To the maximum extent permitted by law, we are not liable for indirect, incidental, or consequential damages arising from your use of the Service.",
  },
  {
    title: "9. Changes & termination",
    body: "We may modify these terms with notice. Continued use after changes means acceptance. We may suspend or terminate your access for breach or at our discretion.",
  },
];

export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <p className="kerned text-white/40 mb-3">LEGAL</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight text-white mb-3">
        Terms of Service
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
          Questions? Contact{" "}
          <a href="mailto:legal@pixium.ai" className="text-white/85 hover:text-white underline">
            legal@pixium.ai
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
