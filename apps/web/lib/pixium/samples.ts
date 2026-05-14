import portraitImg from "@/assets/hero-portrait.jpg";
import architectureImg from "@/assets/sample-architecture.jpg";
import animeImg from "@/assets/sample-anime.jpg";
import productImg from "@/assets/sample-product.jpg";
import abstractImgRaw from "@/assets/sample-abstract.jpg";
import fashionImg from "@/assets/sample-fashion.jpg";
import scifiImg from "@/assets/sample-scifi.jpg";
import surrealImg from "@/assets/sample-surreal.jpg";
import foodImg from "@/assets/sample-food.jpg";
import illustrationImg from "@/assets/sample-illustration.jpg";
import landscapeImg from "@/assets/sample-landscape.jpg";
import jellyImg from "@/assets/sample-3d.jpg";
import cinematicImg from "@/assets/sample-cinematic.jpg";

// Next.js webpack returns StaticImageData {src, width, height, ...}.
// We expose `.src` as a string URL so plain <img src={s.src}> works in JSX —
// matches the webs Vite import pattern visually but uses Next's hashed asset URL.
const portrait = portraitImg.src;
const architecture = architectureImg.src;
const anime = animeImg.src;
const product = productImg.src;
const abstractImg = abstractImgRaw.src;
const fashion = fashionImg.src;
const scifi = scifiImg.src;
const surreal = surrealImg.src;
const food = foodImg.src;
const illustration = illustrationImg.src;
const landscape = landscapeImg.src;
const jelly = jellyImg.src;
const cinematic = cinematicImg.src;

export type Sample = {
  id: string;
  src: string;
  prompt: string;
  author: string;
  model: string;
  style: string;
  ratio: "portrait" | "landscape" | "square";
};

export const HERO = portrait;

export const samples: Sample[] = [
  { id: "p1", src: portrait, prompt: "Iridescent holographic portrait, electric violet rim light, 85mm", author: "@kira", model: "Aurora XL", style: "Cinematic", ratio: "portrait" },
  { id: "a1", src: architecture, prompt: "Floating crystalline citadel above pastel clouds", author: "@noor", model: "Vista", style: "Architectural", ratio: "portrait" },
  { id: "an1", src: anime, prompt: "Shoujo girl beneath cherry blossoms, painterly", author: "@hana", model: "Sakura", style: "Anime", ratio: "portrait" },
  { id: "pr1", src: product, prompt: "Luxury black perfume bottle, golden rim light", author: "@studio", model: "Aurora XL", style: "Product", ratio: "square" },
  { id: "ab1", src: abstractImg, prompt: "Liquid metal in zero gravity, oil-slick chroma", author: "@flux", model: "Prism", style: "Abstract", ratio: "portrait" },
  { id: "f1", src: fashion, prompt: "Avant-garde silver couture, neon backlight", author: "@vogue", model: "Aurora XL", style: "Fashion", ratio: "portrait" },
  { id: "s1", src: scifi, prompt: "Cyberpunk Tokyo, rain reflections, neon kanji", author: "@blade", model: "Neon", style: "Sci-fi", ratio: "landscape" },
  { id: "su1", src: surreal, prompt: "Giant pearl moon over still ocean, painterly", author: "@dream", model: "Vista", style: "Surreal", ratio: "portrait" },
  { id: "fd1", src: food, prompt: "Panna cotta on dark stone, michelin top-down", author: "@chef", model: "Studio", style: "Food", ratio: "square" },
  { id: "il1", src: illustration, prompt: "Fox in enchanted forest with glowing mushrooms", author: "@ink", model: "Storybook", style: "Illustration", ratio: "portrait" },
  { id: "ls1", src: landscape, prompt: "Aurora borealis over Iceland black sand beach", author: "@nord", model: "Vista", style: "Landscape", ratio: "landscape" },
  { id: "td1", src: jelly, prompt: "Translucent bioluminescent jelly creature", author: "@octane", model: "Render3D", style: "3D", ratio: "portrait" },
  { id: "cn1", src: cinematic, prompt: "Vintage car in desert at golden hour, symmetric", author: "@reel", model: "Cinema", style: "Cinematic", ratio: "landscape" },
];

export const styles = ["Cinematic", "Anime", "Photoreal", "Illustration", "3D", "Abstract", "Fashion", "Product", "Sci-fi", "Surreal", "Architectural", "Food", "Storybook"];

/**
 * Capability "types" — replaces the old per-model showcase.
 * Aligned with Pixium's BUCKET_MODEL_MAP (typography, photorealism, anime, artistic, vector, fast).
 * The /models route is hidden; /types displays these buckets.
 */
export type CapabilityType = {
  id: string;
  name: string;
  tag: string;
  description: string;
  samples: string[];
};

export const types: CapabilityType[] = [
  {
    id: "photorealism",
    name: "Photorealism",
    tag: "Lifelike imagery",
    description: "Portraits, products, environments — indistinguishable from a camera.",
    samples: [portrait, fashion, product, cinematic],
  },
  {
    id: "typography",
    name: "Typography",
    tag: "Posters & ads with text",
    description: "Headlines, lockups, ad creatives — perfect spelling, real layouts.",
    samples: [product, fashion, abstractImg, cinematic],
  },
  {
    id: "anime",
    name: "Anime",
    tag: "Illustration & manga",
    description: "Studio-grade anime, manga panels, cel-shaded characters.",
    samples: [anime, illustration, surreal, abstractImg],
  },
  {
    id: "artistic",
    name: "Artistic",
    tag: "Painterly & surreal",
    description: "Editorial concept art, surrealism, cinematic worlds.",
    samples: [surreal, abstractImg, scifi, cinematic],
  },
  {
    id: "vector",
    name: "Vector",
    tag: "Logos & icons",
    description: "Clean SVG marks, brand logos, infographics.",
    samples: [abstractImg, product, illustration, jelly],
  },
  {
    id: "fast",
    name: "Fast",
    tag: "Quick drafts",
    description: "Sub-5-second generations for rapid ideation.",
    samples: [landscape, food, scifi, anime],
  },
];

/** Legacy alias — the old `models` array. Some pages still reference it. */
export const models = types;
