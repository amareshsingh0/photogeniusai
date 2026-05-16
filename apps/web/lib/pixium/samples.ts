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
// May 16 2026 — new Pixium showcase imagery
import alcoholTypoImg from "@/assets/alcohol_typography.png";
import glowTypoImg from "@/assets/glow_typography.png";
import liquidDetergentTypoImg from "@/assets/liquid_detergent_typography.png";
import medicalTypoImg from "@/assets/medical_typography.png";
import newCollectionTypoImg from "@/assets/new_collection_typography.png";
import songLaunchTypoImg from "@/assets/song_launch_typography.png";
import sunscreenTypoImg from "@/assets/sunscreen_typography.png";
import tigerShampooTypoImg from "@/assets/tiger_shampoo_typograpgy.png";
import realismLionImg from "@/assets/realism_lion.png";
import realismPeacockImg from "@/assets/realism_peacock.png";
import artisticLionImg from "@/assets/artistic_lion.png";

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
const alcoholTypo = alcoholTypoImg.src;
const glowTypo = glowTypoImg.src;
const liquidDetergentTypo = liquidDetergentTypoImg.src;
const medicalTypo = medicalTypoImg.src;
const newCollectionTypo = newCollectionTypoImg.src;
const songLaunchTypo = songLaunchTypoImg.src;
const sunscreenTypo = sunscreenTypoImg.src;
const tigerShampooTypo = tigerShampooTypoImg.src;
const realismLion = realismLionImg.src;
const realismPeacock = realismPeacockImg.src;
const artisticLion = artisticLionImg.src;

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
  // — Typography (ad creatives, headlines, lockups) —
  { id: "ty-alcohol",   src: alcoholTypo,          prompt: "Premium dark spirits bottle with elegant gold typography",     author: "@pixium", model: "Studio",   style: "Product",     ratio: "portrait" },
  { id: "ty-glow",      src: glowTypo,             prompt: "Luminous beauty product ad with radiant glow typography",      author: "@pixium", model: "Studio",   style: "Product",     ratio: "portrait" },
  { id: "ty-liquid",    src: liquidDetergentTypo,  prompt: "Vibrant liquid detergent campaign with bold layout",           author: "@pixium", model: "Studio",   style: "Product",     ratio: "portrait" },
  { id: "ty-medical",   src: medicalTypo,          prompt: "Clean medical product ad with trust-building typography",      author: "@pixium", model: "Studio",   style: "Product",     ratio: "portrait" },
  { id: "ty-newcoll",   src: newCollectionTypo,    prompt: "Fashion new-collection launch poster, editorial layout",       author: "@pixium", model: "Studio",   style: "Fashion",     ratio: "portrait" },
  { id: "ty-song",      src: songLaunchTypo,       prompt: "Album / song launch poster with hero typography",              author: "@pixium", model: "Studio",   style: "Cinematic",   ratio: "portrait" },
  { id: "ty-sunscreen", src: sunscreenTypo,        prompt: "Sunscreen summer campaign with sun-kissed typography",         author: "@pixium", model: "Studio",   style: "Product",     ratio: "portrait" },
  { id: "ty-tiger",     src: tigerShampooTypo,     prompt: "Tiger shampoo bold animal-themed brand ad",                    author: "@pixium", model: "Studio",   style: "Product",     ratio: "portrait" },

  // — Photorealism (animals, portraits, products) —
  { id: "rl-lion",      src: realismLion,          prompt: "Photoreal majestic lion portrait with detailed mane",          author: "@pixium", model: "Vista",    style: "Photoreal",   ratio: "portrait" },
  { id: "rl-peacock",   src: realismPeacock,       prompt: "Photoreal peacock with iridescent feather detail",             author: "@pixium", model: "Vista",    style: "Photoreal",   ratio: "portrait" },

  // — Artistic (painterly, surreal) —
  { id: "ar-lion",      src: artisticLion,         prompt: "Painterly lion in dramatic chiaroscuro lighting",              author: "@pixium", model: "Vista",    style: "Surreal",     ratio: "portrait" },

  // — Replaced May 16 2026: 4 of these were updated to richer typography ad creatives —
  { id: "ty-velourveil", src: portrait,     prompt: "VelourVeil luminous setting powder launch ad, soft beige tones, 'Blur the lines. Not your glow.'", author: "@pixium", model: "Studio", style: "Product", ratio: "portrait" },
  { id: "a1",            src: architecture, prompt: "Floating crystalline citadel above pastel clouds",                                                 author: "@noor",   model: "Vista",  style: "Architectural", ratio: "portrait" },
  { id: "an1",           src: anime,        prompt: "Shoujo girl beneath cherry blossoms, painterly",                                                   author: "@hana",   model: "Sakura", style: "Anime",         ratio: "portrait" },
  { id: "ty-glamour",    src: product,      prompt: "Glamour Banarasi saree heritage launch ad, rich gold and saffron, 'Timeless. Elegant. You.'",      author: "@pixium", model: "Studio", style: "Fashion",       ratio: "square"   },
  { id: "ab1",           src: abstractImg,  prompt: "Liquid metal in zero gravity, oil-slick chroma",                                                   author: "@flux",   model: "Prism",  style: "Abstract",      ratio: "portrait" },
  { id: "ty-maharani",   src: fashion,      prompt: "Maharani bridal couture ad, opulent red lehenga, 'Your perfect day — begin with the things of your dreams.'", author: "@pixium", model: "Studio", style: "Fashion", ratio: "portrait" },
  { id: "s1",            src: scifi,        prompt: "Cyberpunk Tokyo, rain reflections, neon kanji",                                                    author: "@blade",  model: "Neon",   style: "Sci-fi",        ratio: "landscape" },
  { id: "su1",           src: surreal,      prompt: "Giant pearl moon over still ocean, painterly",                                                     author: "@dream",  model: "Vista",  style: "Surreal",       ratio: "portrait" },
  { id: "ty-embersage",  src: food,         prompt: "Ember & Sage restaurant grand-opening ad, free dessert offer, warm editorial layout",              author: "@pixium", model: "Studio", style: "Food",          ratio: "portrait" },
  { id: "il1",           src: illustration, prompt: "Fox in enchanted forest with glowing mushrooms",                                                   author: "@ink",    model: "Storybook", style: "Illustration", ratio: "portrait" },
  { id: "ls1",           src: landscape,    prompt: "Aurora borealis over Iceland black sand beach",                                                    author: "@nord",   model: "Vista",  style: "Landscape",     ratio: "landscape" },
  { id: "td1",           src: jelly,        prompt: "Translucent bioluminescent jelly creature",                                                        author: "@octane", model: "Render3D", style: "3D",          ratio: "portrait" },
  { id: "cn1",           src: cinematic,    prompt: "Vintage car in desert at golden hour, symmetric",                                                  author: "@reel",   model: "Cinema", style: "Cinematic",     ratio: "landscape" },
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
    samples: [realismLion, realismPeacock, cinematic, landscape],
  },
  {
    id: "typography",
    name: "Typography",
    tag: "Posters & ads with text",
    description: "Headlines, lockups, ad creatives — perfect spelling, real layouts.",
    samples: [alcoholTypo, newCollectionTypo, sunscreenTypo, medicalTypo],
  },
  {
    id: "anime",
    name: "Anime",
    tag: "Illustration & manga",
    description: "Studio-grade anime, manga panels, cel-shaded characters.",
    samples: [anime, illustration, jelly, surreal],
  },
  {
    id: "artistic",
    name: "Artistic",
    tag: "Painterly & surreal",
    description: "Editorial concept art, surrealism, cinematic worlds.",
    samples: [artisticLion, surreal, abstractImg, scifi],
  },
  {
    id: "vector",
    name: "Vector",
    tag: "Logos & icons",
    description: "Clean SVG marks, brand logos, infographics.",
    samples: [glowTypo, songLaunchTypo, tigerShampooTypo, liquidDetergentTypo],
  },
  {
    id: "fast",
    name: "Fast",
    tag: "Quick drafts",
    description: "Sub-5-second generations for rapid ideation.",
    samples: [architecture, scifi, anime, illustration],
  },
];

/** Legacy alias — the old `models` array. Some pages still reference it. */
export const models = types;

/**
 * Set of all bundled asset URLs (Next.js hashed). Used by the protected-image
 * component to distinguish bundled showcase imagery (DO NOT allow download)
 * from user-generated S3 images (download OK).
 */
export const PROTECTED_ASSET_URLS = new Set<string>([
  portrait, architecture, anime, product, abstractImg, fashion, scifi, surreal,
  food, illustration, landscape, jelly, cinematic,
  alcoholTypo, glowTypo, liquidDetergentTypo, medicalTypo, newCollectionTypo,
  songLaunchTypo, sunscreenTypo, tigerShampooTypo,
  realismLion, realismPeacock, artisticLion,
]);

/** Helper: should this image be download-protected? */
export const isProtectedAsset = (src: string | undefined | null): boolean => {
  if (!src) return false;
  return PROTECTED_ASSET_URLS.has(src);
};
