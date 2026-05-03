"""
Mine real-world ad data into per-category recipes.

INPUT (server-only, ~30MB total):
  ~/PhotoGenius-AI/datasets/pitt-ads-text/image/  (Pitt Image Ads annotations)
    - Topics.json                       {image_id: [topic_id_str, ...]}
    - Topics_List.txt                   "1  \"label\" (ABBREVIATION: \"abbr\")"
    - Slogans.json                      {image_id: ["tagline", ...]}
    - QA_Action.json                    {image_id: ["I should X", ...]}
    - Sentiments.json                   {image_id: [sentiment_id_str, ...]}
    - Sentiments_List.txt               "1. \"label\" (ABBREVIATION: \"abbr\")"
    - Strategies.json                   {image_id: [strategy_id_str, ...]}
    - Strategies_List.txt               "1, Process"
  ~/PhotoGenius-AI/datasets/ad-copy/Ads_Creative_Ad_Copy_Programmatic.csv

OUTPUT:
  apps/api/app/services/smart/data/category_recipes_mined.json

Schema mirrors existing manual category_recipes.json so the loader can union both.

Run on the Ubuntu server (where datasets/ live):
    cd ~/PhotoGenius-AI/apps/api && source venv/bin/activate
    python3 scripts/mine_category_recipes.py
Then scp the generated JSON back to local repo and commit.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (resolved relative to ~/PhotoGenius-AI on server)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]            # ~/PhotoGenius-AI
DATASETS  = REPO_ROOT / "datasets"
PITT_DIR  = DATASETS / "pitt-ads-text" / "image"
ADCOPY_CSV = DATASETS / "ad-copy" / "Ads_Creative_Ad_Copy_Programmatic.csv"
OUT_PATH  = REPO_ROOT / "apps" / "api" / "app" / "services" / "smart" / "data" / "category_recipes_mined.json"

# ---------------------------------------------------------------------------
# Pitt topic abbr -> our canonical category key + aliases used for runtime
# keyword matching against user prompts. Skips meta categories (Unclear,
# domestic_violence etc) that don't translate to commercial ad recipes.
# ---------------------------------------------------------------------------
PITT_TO_CANONICAL: dict[str, dict[str, Any]] = {
    "restaurant":      {"key": "restaurant_cafe",   "aliases": ["restaurant", "cafe", "fast food", "diner", "bistro", "eatery", "food court"]},
    "chocolate":       {"key": "chocolate_candy",   "aliases": ["chocolate", "candy", "cookie", "ice cream", "dessert", "confectionery"]},
    "chips":           {"key": "snacks_packaged",   "aliases": ["chips", "snacks", "nuts", "cereal", "yogurt", "granola", "crackers"]},
    "seasoning":       {"key": "seasoning_condiments","aliases": ["seasoning", "spice", "ketchup", "sauce", "condiment", "masala"]},
    "petfood":         {"key": "pet_care",          "aliases": ["pet", "petfood", "dog food", "cat food", "pet care", "puppy", "kitten"]},
    "alcohol":         {"key": "alcohol_beverage",  "aliases": ["beer", "wine", "whiskey", "vodka", "rum", "alcohol", "liquor", "champagne"]},
    "coffee":          {"key": "coffee_tea",        "aliases": ["coffee", "tea", "espresso", "latte", "cappuccino", "chai", "matcha"]},
    "soda":            {"key": "beverage_soft",     "aliases": ["soda", "juice", "milk", "energy drink", "water", "soft drink", "cola"]},
    "cars":            {"key": "automotive",        "aliases": ["car", "auto", "automobile", "vehicle", "suv", "sedan", "truck", "motorcycle", "bike"]},
    "electronics":     {"key": "consumer_electronics","aliases": ["laptop", "computer", "phone", "smartphone", "tablet", "tv", "headphone", "earbuds", "smartwatch"]},
    "phone_tv_internet_providers": {"key": "telecom_isp", "aliases": ["telecom", "broadband", "internet", "isp", "phone plan", "mobile plan", "5g", "fiber"]},
    "financial":       {"key": "financial_services","aliases": ["bank", "credit card", "loan", "investment", "insurance", "finance", "mortgage", "banking"]},
    "education":       {"key": "education",         "aliases": ["university", "college", "school", "online course", "degree", "kindergarten", "tuition", "coaching"]},
    "security":        {"key": "security_safety",   "aliases": ["security", "anti-theft", "alarm", "safety course", "cctv", "surveillance"]},
    "software":        {"key": "saas_software",     "aliases": ["software", "saas", "app", "streaming", "subscription", "platform", "tool", "service"]},
    "other_service":   {"key": "professional_services","aliases": ["dating", "tax", "legal", "loan", "religious", "printing", "catering", "consulting"]},
    "beauty":          {"key": "beauty_cosmetics",  "aliases": ["beauty", "makeup", "cosmetics", "skincare", "deodorant", "toothpaste", "haircare", "perfume", "fragrance"]},
    "healthcare":      {"key": "healthcare",        "aliases": ["hospital", "clinic", "doctor", "medication", "vitamin", "allergy", "remedy", "health insurance", "pharmacy"]},
    "clothing":        {"key": "fashion_apparel",   "aliases": ["clothing", "apparel", "jeans", "shoes", "handbag", "watch", "jewelry", "eyewear", "accessory"]},
    "baby":            {"key": "baby_products",     "aliases": ["baby", "infant", "diaper", "baby food", "sippy cup", "stroller", "newborn", "toddler"]},
    "game":            {"key": "games_toys",        "aliases": ["game", "toy", "video game", "mobile game", "console", "boardgame", "gaming"]},
    "cleaning":        {"key": "cleaning_products", "aliases": ["detergent", "soap", "tissue", "paper towel", "cleaning", "fabric softener", "disinfectant"]},
    "home_improvement":{"key": "home_improvement",  "aliases": ["furniture", "decoration", "lawn", "plumbing", "renovation", "interior", "diy", "garden"]},
    "home_appliance":  {"key": "home_appliances",   "aliases": ["coffee maker", "dishwasher", "vacuum", "heater", "appliance", "fridge", "microwave", "blender"]},
    "travel":          {"key": "travel_hospitality","aliases": ["airline", "cruise", "hotel", "resort", "theme park", "travel", "vacation", "tour", "flight"]},
    "media":           {"key": "media_entertainment","aliases": ["tv show", "movie", "musical", "book", "audio book", "podcast", "concert", "streaming"]},
    "sports":          {"key": "sports_fitness",    "aliases": ["sports", "fitness", "gym", "workout", "athletic", "running", "yoga", "cycling"]},
    "shopping":        {"key": "retail_shopping",   "aliases": ["department store", "drug store", "grocery", "supermarket", "mall", "retail", "store"]},
    "gambling":        {"key": "gambling_lottery",  "aliases": ["lottery", "casino", "poker", "betting", "jackpot", "gambling"]},
    "environment":     {"key": "environment_eco",   "aliases": ["environment", "nature", "pollution", "wildlife", "conservation", "sustainability", "eco"]},
    "animal_right":    {"key": "animal_welfare",    "aliases": ["animal rights", "animal abuse", "shelter", "rescue", "endangered"]},
    "human_right":     {"key": "human_rights",      "aliases": ["human rights", "equality", "freedom", "justice", "civil rights"]},
    "safety":          {"key": "safety_awareness",  "aliases": ["safe driving", "fire safety", "road safety", "drunk driving", "seatbelt"]},
    "political":       {"key": "political_campaign","aliases": ["candidate", "election", "vote", "campaign", "political"]},
    "charities":       {"key": "charity_nonprofit", "aliases": ["donate", "charity", "fundraiser", "ngo", "nonprofit", "volunteer"]},
}

ASCII_RE = re.compile(r"[^\x00-\x7f]+")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]{1,}")
_STOP = set("""
a an the and or but if then else when where why how is am are was were be been being have has had do does did
will would shall should can could may might must to of in on for with at by from as into onto upon over under
out about up down off again further so very just not no nor too only also more most some any all each every other
this that these those i you he she it we they me him her us them my your his its our their mine yours hers ours theirs
get got make made take taken give given see seen know known
""".split())
_GENERIC_VERBS = {"buy","try","use","get","shop","visit","go","see","watch","eat","drink","read","listen","play","wear","take","find","support","donate","help","learn","check","experience","enjoy","choose"}


def _read_list_file(path: Path) -> dict[int, str]:
    """Parse Pitt's Topics_List.txt / Sentiments_List.txt / Strategies_List.txt.

    Real-file formats observed (note encoding noise -> BOM / replacement chars):
        Topics_List.txt:      "<BOM>1\t\"Restaurants...\" (ABBREVIATION: \"restaurant\")"
        Sentiments_List.txt:  "1. \"Active...\" (ABBREVIATION: \"active\")"
        Strategies_List.txt:  "1, Process"

    Topics file: ALL lines on one logical record may share BOMs / non-ASCII
    quote chars (smart quotes from Word). We strip non-ASCII first and use
    a tolerant id+abbreviation extraction that doesn't anchor at start.
    """
    out: dict[int, str] = {}
    raw_text = path.read_bytes().decode("utf-8", errors="replace")
    # Drop any non-ASCII chars (BOM, replacement chars, smart quotes).
    text = ASCII_RE.sub(" ", raw_text)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Pull the first integer anywhere in the line (handles "<spaces>1<tab>...").
        m_id = re.search(r"\b(\d+)\b", line)
        if not m_id:
            continue
        id_ = int(m_id.group(1))
        m_abbr = re.search(r'ABBREVIATION:\s*"?([A-Za-z_][A-Za-z0-9_]*)"?', line, re.IGNORECASE)
        if m_abbr:
            out[id_] = m_abbr.group(1).strip().lower()
        else:
            # Strategies file: "1, Process" -> take the word after the separator.
            m_lbl = re.match(r"^\s*\d+\s*[,.\-:\s]\s*(\S+)", line)
            if m_lbl:
                out[id_] = m_lbl.group(1).strip().lower()
    return out


def _majority(items: list[str]) -> str:
    """Return the most-voted label (Pitt has 3-5 annotators per ad)."""
    if not items:
        return ""
    return Counter(items).most_common(1)[0][0]


def _clean_slogan(s: str) -> str:
    s = ASCII_RE.sub(" ", s).strip().strip('"').strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_action(s: str) -> str:
    """Strip 'I should ' prefix to get a CTA verb phrase."""
    s = ASCII_RE.sub(" ", s).strip()
    s = re.sub(r"^\s*(?:I should|I will|I must|i ought to|We should|You should)\s+", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" .,;:")
    return s


def _action_to_cta(action: str) -> str:
    """'buy these earbuds' -> 'Buy Now' / 'Shop Now'. Coerce free-form actions to canonical CTA buttons."""
    a = action.lower()
    if not a:
        return ""
    if any(w in a for w in ("buy", "purchase", "order", "shop")): return "Shop Now"
    if any(w in a for w in ("donate", "give", "contribute"))    : return "Donate Now"
    if any(w in a for w in ("subscribe", "sign up", "join"))    : return "Sign Up"
    if any(w in a for w in ("download", "install", "get the"))  : return "Download"
    if any(w in a for w in ("book", "reserve", "schedule"))     : return "Book Now"
    if any(w in a for w in ("call", "contact"))                 : return "Call Now"
    if any(w in a for w in ("visit", "go to", "come to"))       : return "Visit Us"
    if any(w in a for w in ("learn", "know", "find out"))       : return "Learn More"
    if any(w in a for w in ("watch", "see", "view"))            : return "Watch Now"
    if any(w in a for w in ("try", "taste", "use", "experience")): return "Try It"
    if any(w in a for w in ("vote", "support"))                 : return "Support"
    return ""


def _vocab_distinctive(category_words: Counter, global_words: Counter, k: int = 25) -> list[str]:
    """Words that appear MORE in this category than overall — distinctive vocabulary."""
    total_cat = sum(category_words.values()) or 1
    total_glb = sum(global_words.values()) or 1
    scored: list[tuple[float, str]] = []
    for w, c in category_words.items():
        if c < 3 or w in _STOP or len(w) < 3:
            continue
        p_cat = c / total_cat
        p_glb = max(global_words.get(w, 0), 1) / total_glb
        lift = p_cat / p_glb
        if lift > 1.4:
            scored.append((lift * c**0.5, w))
    scored.sort(reverse=True)
    seen, out = set(), []
    for _, w in scored:
        if w in seen: continue
        seen.add(w); out.append(w)
        if len(out) >= k: break
    return out


def main() -> None:
    if not PITT_DIR.exists():
        raise SystemExit(f"Pitt dir not found: {PITT_DIR}\nRun on the server where datasets/ are downloaded.")

    print(f"[mine] reading lists from {PITT_DIR}")
    topics_list      = _read_list_file(PITT_DIR / "Topics_List.txt")
    sentiments_list  = _read_list_file(PITT_DIR / "Sentiments_List.txt")
    strategies_list  = _read_list_file(PITT_DIR / "Strategies_List.txt")
    print(f"[mine]   topics={len(topics_list)} sentiments={len(sentiments_list)} strategies={len(strategies_list)}")

    topics      = json.loads((PITT_DIR / "Topics.json").read_text(encoding="utf-8"))
    slogans     = json.loads((PITT_DIR / "Slogans.json").read_text(encoding="utf-8"))
    actions     = json.loads((PITT_DIR / "QA_Action.json").read_text(encoding="utf-8"))
    sentiments  = json.loads((PITT_DIR / "Sentiments.json").read_text(encoding="utf-8"))
    strategies  = json.loads((PITT_DIR / "Strategies.json").read_text(encoding="utf-8"))
    print(f"[mine]   ads={len(topics)} slogans_ads={len(slogans)} action_ads={len(actions)}")

    # Aggregate per Pitt abbreviation
    per_topic: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "slogans": [], "actions": [], "sentiments": [], "strategies": [], "word_counter": Counter(),
    })
    global_words: Counter = Counter()

    for img_id, topic_ids in topics.items():
        votes = []
        for tid in topic_ids:
            try:
                votes.append(topics_list.get(int(tid), ""))
            except (TypeError, ValueError):
                continue
        topic_abbr = _majority(votes)
        if not topic_abbr or topic_abbr not in PITT_TO_CANONICAL:
            continue
        bucket = per_topic[topic_abbr]

        for s in slogans.get(img_id, []) or []:
            cs = _clean_slogan(s)
            if 2 <= len(cs.split()) <= 12:
                bucket["slogans"].append(cs)
                for w in (m.group(0).lower() for m in _WORD_RE.finditer(cs)):
                    bucket["word_counter"][w] += 1
                    global_words[w] += 1

        for a in actions.get(img_id, []) or []:
            na = _normalize_action(a)
            if na:
                bucket["actions"].append(na)
                cta = _action_to_cta(na)
                if cta:
                    bucket["actions"].append(f"__CTA__:{cta}")

        for sid in sentiments.get(img_id, []) or []:
            try: bucket["sentiments"].append(sentiments_list.get(int(sid), ""))
            except (TypeError, ValueError): pass

        for stid in strategies.get(img_id, []) or []:
            try: bucket["strategies"].append(strategies_list.get(int(stid), ""))
            except (TypeError, ValueError): pass

    # Build output
    out: dict[str, Any] = {
        "_meta": {
            "version": "2.0.0-mined",
            "purpose": "Data-driven category recipes mined from Pitt Image Ads (CVPR 2017, 64K real ads, 38 industry topics) + AdCopy programmatic dataset. Loaded by simple_prompt_engine.py and union'd with manual category_recipes.json — mined entries take priority where both define the same key.",
            "source": "Pitt Image Ads (https://people.cs.pitt.edu/~kovashka/ads/) + PeterBrendan/Ads_Creative_Ad_Copy_Programmatic on HuggingFace",
            "fields": "aliases, hero_patterns, cta_patterns, top_sentiments, top_strategies, distinctive_vocabulary, sample_count",
            "ascii_only": True,
        },
    }

    for abbr, agg in per_topic.items():
        meta = PITT_TO_CANONICAL[abbr]
        ctas = [s.split(":",1)[1] for s in agg["actions"] if s.startswith("__CTA__:")]
        raw_actions = [s for s in agg["actions"] if not s.startswith("__CTA__:")]
        action_verbs = [a.split(" ")[0].lower() for a in raw_actions if a]
        action_verbs = [v for v in action_verbs if v not in _STOP]

        # De-dupe slogans, keep top by length-bucketed frequency
        slogan_counts = Counter(agg["slogans"])
        top_slogans = [s for s, _ in slogan_counts.most_common(40) if 2 <= len(s.split()) <= 8][:20]

        cta_counts = Counter(ctas)
        top_ctas = [c for c, _ in cta_counts.most_common(8)] if cta_counts else []

        sent_counts = Counter([s for s in agg["sentiments"] if s])
        strat_counts = Counter([s for s in agg["strategies"] if s])

        out[meta["key"]] = {
            "aliases":               meta["aliases"],
            "hero_patterns":         top_slogans,
            "cta_patterns":          top_ctas or ["Learn More", "Shop Now"],
            "top_sentiments":        [s for s, _ in sent_counts.most_common(5)],
            "top_strategies":        [s for s, _ in strat_counts.most_common(5)],
            "distinctive_vocabulary": _vocab_distinctive(agg["word_counter"], global_words, k=25),
            "sample_count":          sum(slogan_counts.values()),
            "_pitt_abbr":            abbr,
        }
        print(f"[mine] {meta['key']:28s} slogans={len(top_slogans):3d} ctas={len(top_ctas):2d} samples={out[meta['key']]['sample_count']}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"\n[mine] wrote {OUT_PATH} ({OUT_PATH.stat().st_size//1024} KB, {len(out)-1} categories)")


if __name__ == "__main__":
    main()
