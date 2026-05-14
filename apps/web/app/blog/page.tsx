import Link from "next/link";
import { ArrowRight } from "lucide-react";

export const metadata = {
  title: "Blog | Pixium AI",
  description: "Tips, updates, and inspiration for AI image generation with Pixium.",
};

const POSTS = [
  {
    slug: "getting-started",
    date: "FEB 2026",
    title: "Getting started with AI image generation",
    excerpt:
      "Your first ten prompts will be bad. Your eleventh will be great. Here is how to skip straight to eleven.",
  },
  {
    slug: "prompt-tips",
    date: "JAN 2026",
    title: "Prompt tips for cleaner outputs",
    excerpt:
      "Subject, style, composition, lighting — the four words that separate amateur prompts from professional ones.",
  },
  {
    slug: "styles-and-modes",
    date: "JAN 2026",
    title: "Styles & creative modes",
    excerpt:
      "Portrait, anime, cinematic, vector, typography — pick the right mode for your idea and the model picks itself.",
  },
  {
    slug: "ad-creator-brain",
    date: "MAY 2026",
    title: "How Pixium thinks about ads",
    excerpt:
      "A 5-phase ad-creator brain — from master sentence to the 0.3-second test — baked into every generation.",
  },
  {
    slug: "logo-framework",
    date: "MAY 2026",
    title: "The 7-phase logo cognitive framework",
    excerpt:
      "Brand archetype, shape psychology, typography personality — the discipline behind every Pixium logo.",
  },
  {
    slug: "multi-reference",
    date: "MAY 2026",
    title: "Five reference images, one frame",
    excerpt:
      "GPT Image 2 edit mode now accepts up to five references. Compose, restyle, and remix without leaving Pixium.",
  },
];

export default function BlogPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <p className="kerned text-white/40 mb-3">BLOG</p>
      <h1 className="font-display text-4xl sm:text-5xl tracking-tight text-white mb-4">
        Notes from the studio.
      </h1>
      <p className="text-lg text-white/60 leading-relaxed mb-12">
        Tips, releases, research notes, and the occasional rant about AI ad slop.
      </p>

      <div className="space-y-3">
        {POSTS.map((post) => (
          <article
            key={post.slug}
            className="glass-panel rounded-2xl p-5 transition hover:translate-y-[-2px]"
          >
            <p className="kerned text-white/40 mb-2">{post.date}</p>
            <h2 className="font-display text-2xl tracking-tight text-white mb-2">
              {post.title}
            </h2>
            <p className="text-sm text-white/60 leading-relaxed mb-4">{post.excerpt}</p>
            <Link
              href="#"
              className="inline-flex items-center gap-2 text-sm text-white/85 hover:text-white transition-colors"
            >
              Read more <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}
