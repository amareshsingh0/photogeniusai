"use client";

import Link from "next/link";
import { useState } from "react";
import { User, Mail, KeyRound, Shield, CreditCard, Bell, LogOut, Copy, Check, Sparkles } from "lucide-react";

const SECTIONS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "plan", label: "Plan & billing", icon: CreditCard },
  { id: "api", label: "API keys", icon: KeyRound },
  { id: "security", label: "Security", icon: Shield },
  { id: "notifications", label: "Notifications", icon: Bell },
] as const;

export default function Account() {
  const [section, setSection] = useState<typeof SECTIONS[number]["id"]>("profile");
  const user = {
    id: "usr_8a3f2c19b4e7d65a",
    handle: "@aria.noir",
    name: "Aria Noir",
    email: "aria@pixium.ai",
    plan: "Studio",
    credits: 847,
    creditsMax: 3000,
    joined: "March 2025",
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pb-24">
      <header className="py-8">
        <p className="kerned text-white/40">Account</p>
        <h1 className="mt-2 font-display text-4xl sm:text-5xl">Settings</h1>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_1fr]">
        {/* Sidebar */}
        <aside className="glass-panel h-fit rounded-3xl p-3">
          <div className="flex items-center gap-3 rounded-2xl bg-white/5 p-3">
            <div className="grid h-11 w-11 place-items-center rounded-full font-display text-lg" style={{ background: "var(--gradient-aurora)", color: "black" }}>
              {user.name.split(" ").map((n) => n[0]).join("")}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user.name}</p>
              <p className="truncate text-xs text-white/50">{user.handle}</p>
            </div>
          </div>
          <nav aria-label="Account sections" className="mt-3 flex flex-col gap-0.5">
            {SECTIONS.map((s) => {
              const Icon = s.icon;
              const active = section === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => setSection(s.id)}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm transition ${active ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"}`}
                >
                  <Icon className="h-4 w-4" aria-hidden />
                  {s.label}
                </button>
              );
            })}
            <button className="mt-2 flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-white/60 hover:bg-white/5 hover:text-white">
              <LogOut className="h-4 w-4" aria-hidden /> Sign out
            </button>
          </nav>
        </aside>

        {/* Content */}
        <section aria-live="polite" className="space-y-4">
          {section === "profile" && <ProfilePanel user={user} />}
          {section === "plan" && <PlanPanel user={user} />}
          {section === "api" && <ApiPanel />}
          {section === "security" && <SecurityPanel />}
          {section === "notifications" && <NotificationsPanel />}
        </section>
      </div>
    </div>
  );
}

function Card({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="glass-panel rounded-3xl p-6">
      <h2 className="font-display text-2xl">{title}</h2>
      {desc && <p className="mt-1 text-sm text-white/60">{desc}</p>}
      <div className="mt-5 space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="kerned mb-1.5 block text-white/50">{label}</span>
      {children}
    </label>
  );
}

function ProfilePanel({ user }: { user: any }) {
  return (
    <>
      <Card title="Profile" desc="How you appear across Pixium.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Display name"><input defaultValue={user.name} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm" /></Field>
          <Field label="Handle"><input defaultValue={user.handle} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm" /></Field>
          <Field label="Email"><input type="email" defaultValue={user.email} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm" /></Field>
          <Field label="Member since"><input disabled defaultValue={user.joined} className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white/50" /></Field>
        </div>
        <Field label="Bio">
          <textarea rows={3} defaultValue="Cinematic AI imagery, slow shutter, Stockholm." className="w-full resize-none rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm" />
        </Field>
        <div className="flex justify-end">
          <button className="rounded-xl px-4 py-2 text-sm font-medium text-black" style={{ background: "var(--gradient-aurora)" }}>Save changes</button>
        </div>
      </Card>

      <Card title="User ID" desc="Use this for support requests and integrations.">
        <CopyRow value={user.id} />
      </Card>
    </>
  );
}

function PlanPanel({ user }: { user: any }) {
  const pct = Math.round((user.credits / user.creditsMax) * 100);
  return (
    <>
      <Card title="Plan" desc="Manage your subscription and credits.">
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/5 p-4">
          <div>
            <p className="kerned text-white/50">Current plan</p>
            <p className="mt-1 font-display text-3xl">{user.plan}</p>
            <p className="text-xs text-white/50">$24 / month · renews May 30</p>
          </div>
          <Link href="/pricing" className="rounded-xl bg-white/10 px-4 py-2 text-sm hover:bg-white/15">Change plan</Link>
        </div>
        <div>
          <div className="mb-1.5 flex items-center justify-between text-xs text-white/60">
            <span>Credits this cycle</span>
            <span className="font-mono">{user.credits} / {user.creditsMax}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
            <div className="h-full" style={{ width: `${pct}%`, background: "var(--gradient-aurora)" }} />
          </div>
        </div>
        <button className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm hover:bg-white/10">
          <Sparkles className="h-3.5 w-3.5" aria-hidden /> Buy credit pack
        </button>
      </Card>
      <Card title="Payment method">
        <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 p-4">
          <div className="flex items-center gap-3">
            <CreditCard className="h-5 w-5 text-white/60" aria-hidden />
            <div>
              <p className="text-sm">Visa ending in 4242</p>
              <p className="text-xs text-white/50">Expires 08/29</p>
            </div>
          </div>
          <button className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10">Update</button>
        </div>
      </Card>
    </>
  );
}

function ApiPanel() {
  return (
    <Card title="API keys" desc="Programmatic access to the Pixium API.">
      <CopyRow value="lmn_live_pk_4f2c19b8a3e7d65a9c01" mask />
      <button className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm hover:bg-white/10">Generate new key</button>
    </Card>
  );
}

function SecurityPanel() {
  return (
    <>
      <Card title="Password">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Current"><input type="password" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm" /></Field>
          <Field label="New"><input type="password" className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm" /></Field>
        </div>
      </Card>
      <Card title="Active sessions">
        {[
          { d: "MacBook Pro · Stockholm", t: "Active now" },
          { d: "iPhone 16 · Stockholm", t: "2 hours ago" },
          { d: "Chrome · Berlin", t: "Yesterday" },
        ].map((s) => (
          <div key={s.d} className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 p-3">
            <div>
              <p className="text-sm">{s.d}</p>
              <p className="text-xs text-white/50">{s.t}</p>
            </div>
            <button className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-xs hover:bg-white/10">Revoke</button>
          </div>
        ))}
      </Card>
    </>
  );
}

function NotificationsPanel() {
  const items = [
    "Email me when a render completes",
    "Weekly community highlights",
    "Product updates & new models",
    "Security alerts",
  ];
  return (
    <Card title="Notifications">
      {items.map((i, idx) => (
        <label key={i} className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 p-3 text-sm">
          <span>{i}</span>
          <input type="checkbox" defaultChecked={idx !== 2} className="h-4 w-4 accent-white" />
        </label>
      ))}
    </Card>
  );
}

function CopyRow({ value, mask = false }: { value: string; mask?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [reveal, setReveal] = useState(!mask);
  const display = reveal ? value : value.slice(0, 8) + "•".repeat(Math.max(0, value.length - 8));
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-black/30 p-2">
      <Mail className="ml-1 h-4 w-4 text-white/40" aria-hidden />
      <code className="flex-1 truncate font-mono text-xs text-white/80">{display}</code>
      {mask && (
        <button onClick={() => setReveal((r) => !r)} className="rounded-lg px-2 py-1 text-xs text-white/60 hover:bg-white/5">
          {reveal ? "Hide" : "Reveal"}
        </button>
      )}
      <button
        onClick={() => { navigator.clipboard?.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        className="inline-flex items-center gap-1 rounded-lg bg-white/10 px-2.5 py-1 text-xs hover:bg-white/15"
        aria-label="Copy"
      >
        {copied ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Copy className="h-3.5 w-3.5" aria-hidden />}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
