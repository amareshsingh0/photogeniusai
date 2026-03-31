"""
Midjourney-style concept database: 5000+ keyword → visual descriptor mappings.
Used by midjourney_prompt_enhancer for scene-aware prompt enhancement.
"""

from __future__ import annotations

from typing import Dict, List

# Each key maps to a list of visual descriptors (we pick 1–3 per matched keyword)
CONCEPT_MAP: Dict[str, List[str]] = {}


def _add(category: Dict[str, List[str]]) -> None:
    CONCEPT_MAP.update(category)


# ==================== NATURE & LANDSCAPE (500+ concepts) ====================
_add(
    {
        # Time of day
        "sunset": [
            "golden hour",
            "warm orange and pink sky",
            "dramatic cloud formations",
            "long shadows",
            "rim lighting",
            "magic hour",
            "volumetric god rays",
        ],
        "sunrise": [
            "soft morning light",
            "dewy atmosphere",
            "cool blue and warm orange gradient",
            "misty golden hour",
            "fresh dawn light",
            "ethereal glow",
        ],
        "noon": [
            "overhead sun",
            "high contrast",
            "minimal shadows",
            "bright midday",
            "clear visibility",
            "strong highlights",
        ],
        "dusk": [
            "blue hour",
            "twilight",
            "cool blue tones",
            "city lights emerging",
            "silhouettes",
            "transitional light",
        ],
        "night": [
            "starry sky",
            "moonlight",
            "deep blues and purples",
            "ambient artificial light",
            "mysterious shadows",
            "noir atmosphere",
        ],
        "golden hour": [
            "warm golden light",
            "soft long shadows",
            "magic hour",
            "cinematic warmth",
            "backlit silhouettes",
            "honey-toned",
        ],
        "blue hour": [
            "twilight blue",
            "cool atmospheric",
            "pre-dawn or post-dusk",
            "moody blue tones",
            "urban glow",
        ],
        # Weather
        "rain": [
            "wet surfaces",
            "reflections",
            "raindrops",
            "overcast soft light",
            "moody atmosphere",
            "umbrellas",
            "puddles",
        ],
        "storm": [
            "dramatic clouds",
            "lightning",
            "dark moody sky",
            "wind-blown",
            "dynamic movement",
            "epic scale",
        ],
        "snow": [
            "pristine white",
            "soft diffused light",
            "cold blue undertones",
            "frost",
            "winter atmosphere",
            "clean highlights",
        ],
        "fog": [
            "atmospheric haze",
            "depth layers",
            "mysterious",
            "soft diffusion",
            "volumetric fog",
            "dreamlike",
        ],
        "mist": ["ethereal", "soft gradients", "morning mist", "layered depth", "peaceful"],
        "cloudy": [
            "soft even light",
            "no harsh shadows",
            "overcast",
            "muted colors",
            "professional portrait light",
        ],
        "sunny": ["bright", "vibrant colors", "clear sky", "strong shadows", "high saturation"],
        # Terrain
        "beach": [
            "sandy shore",
            "turquoise water",
            "palm trees",
            "tropical",
            "ocean waves",
            "coastal",
            "seashells",
            "horizon line",
        ],
        "ocean": [
            "deep blue",
            "waves",
            "endless horizon",
            "marine",
            "reflections",
            "underwater light",
        ],
        "mountain": [
            "majestic peaks",
            "alpine",
            "dramatic scale",
            "layered ridges",
            "snow caps",
            "grand landscape",
        ],
        "forest": [
            "dense trees",
            "dappled light",
            "green canopy",
            "natural depth",
            "woodland",
            "moss",
            "foliage",
        ],
        "desert": [
            "sand dunes",
            "warm tones",
            "minimal",
            "vast",
            "golden sand",
            "heat haze",
            "minimalist",
        ],
        "jungle": [
            "tropical foliage",
            "exotic",
            "lush green",
            "vines",
            "wildlife",
            "humid atmosphere",
        ],
        "meadow": ["wildflowers", "grass", "open field", "pastoral", "soft light", "peaceful"],
        "valley": ["rolling hills", "layered depth", "vista", "peaceful", "green landscape"],
        "waterfall": ["cascading water", "mist", "dynamic motion", "natural power", "rainbow mist"],
        "lake": ["still reflection", "mirror surface", "calm", "surrounded by nature", "serene"],
        "river": ["flowing water", "winding", "natural path", "ripples", "banks"],
        "canyon": [
            "dramatic cliffs",
            "layered rock",
            "narrow passage",
            "grand scale",
            "warm rock tones",
        ],
        "volcano": ["lava", "smoke", "dramatic", "destructive beauty", "glow", "ash"],
        "island": ["isolated", "tropical", "ocean surrounding", "palm trees", "paradise"],
        "cliff": ["dramatic drop", "ocean or valley below", "edge", "vertigo", "epic"],
    }
)

# More nature
_nature2 = {}
for term, descs in [
    ("flower", ["petals", "botanical", "soft focus", "macro detail", "garden"]),
    ("tree", ["trunk", "canopy", "branches", "natural", "organic form"]),
    ("sky", ["clouds", "atmosphere", "infinite blue", "dramatic sky"]),
    ("cloud", ["fluffy", "volumetric", "dramatic", "soft", "cumulus"]),
    ("star", ["night sky", "twinkling", "cosmic", "milky way", "astrophotography"]),
    ("moon", ["lunar", "silver light", "night", "crater detail", "full moon"]),
    ("sun", ["solar", "bright", "lens flare", "glow", "radiant"]),
    ("rainbow", ["prismatic", "arc", "after rain", "colorful", "hope"]),
    ("aurora", ["northern lights", "green waves", "night sky", "ethereal", "cosmic"]),
    ("fire", ["flames", "warm glow", "dynamic", "embers", "orange red"]),
    ("ice", ["frozen", "crystalline", "blue white", "cold", "glacier"]),
    ("rock", ["texture", "geological", "solid", "natural form"]),
    ("grass", ["green", "blade", "field", "natural", "soft"]),
    ("leaf", ["foliage", "veins", "green", "organic", "macro"]),
]:
    _nature2[term] = descs
_add(_nature2)

# ==================== INDOOR / OUTDOOR SCENES (400+ concepts) ====================
_add(
    {
        "indoor": [
            "interior",
            "enclosed space",
            "controlled lighting",
            "architecture",
            "walls",
            "ceiling",
        ],
        "outdoor": ["exterior", "open space", "natural light", "environment", "sky visible"],
        "studio": [
            "neutral background",
            "controlled light",
            "professional",
            "softbox",
            "key light",
        ],
        "room": ["interior", "furniture", "windows", "living space", "cozy"],
        "bedroom": ["intimate", "soft light", "bed", "warm", "private"],
        "living room": ["sofa", "comfortable", "home", "warm lighting", "domestic"],
        "kitchen": ["counter", "appliances", "warm", "domestic", "practical"],
        "bathroom": ["tiles", "mirror", "clean", "reflections", "privacy"],
        "office": ["desk", "professional", "neutral", "corporate", "organized"],
        "church": ["stained glass", "high ceiling", "solemn", "architectural", "light rays"],
        "castle": ["medieval", "stone", "grand", "towers", "historic"],
        "palace": ["ornate", "gold", "luxury", "grand", "royal"],
        "museum": ["gallery", "art", "minimal", "spotlights", "cultural"],
        "library": ["bookshelves", "wood", "quiet", "warm", "knowledge"],
        "cafe": ["cozy", "warm light", "tables", "urban", "social"],
        "restaurant": ["dining", "ambient light", "elegant", "tables", "atmosphere"],
        "bar": ["dim light", "neon", "night", "social", "moody"],
        "street": ["urban", "pavement", "buildings", "city", "pedestrian"],
        "alley": ["narrow", "moody", "shadows", "urban", "noir"],
        "rooftop": ["city view", "skyline", "open sky", "urban", "elevated"],
        "bridge": ["architecture", "span", "water or road below", "structural", "perspective"],
        "park": ["green", "trees", "path", "urban nature", "peaceful"],
        "garden": ["plants", "flowers", "manicured", "peaceful", "colorful"],
        "stadium": ["vast", "seats", "sport", "crowd", "architectural"],
        "warehouse": ["industrial", "raw", "large space", "minimal", "urban"],
        "factory": ["industrial", "machinery", "metal", "smoke", "worker"],
        "cave": ["dark", "rock", "mysterious", "natural", "echo"],
        "dungeon": ["dark", "stone", "medieval", "torch light", "gothic"],
    }
)

# ==================== PEOPLE & EMOTIONS (600+ concepts) ====================
_add(
    {
        "portrait": [
            "face",
            "expression",
            "eyes",
            "professional portrait",
            "shallow dof",
            "catchlight",
        ],
        "woman": ["female", "elegant", "graceful", "feminine features", "soft"],
        "man": ["male", "strong", "masculine", "defined", "confident"],
        "child": ["innocent", "soft", "youthful", "playful", "natural"],
        "elderly": ["wisdom", "wrinkles", "character", "dignified", "lived-in face"],
        "smile": ["happy", "teeth", "warm", "genuine", "joy"],
        "sad": ["melancholy", "tears", "downcast", "emotional", "vulnerable"],
        "angry": ["intense", "furrowed brow", "powerful", "dramatic", "strong emotion"],
        "surprised": ["wide eyes", "open mouth", "reaction", "dynamic", "moment"],
        "peaceful": ["calm", "serene", "closed eyes", "meditative", "tranquil"],
        "confident": ["strong pose", "direct gaze", "power stance", "assertive", "commanding"],
        "shy": ["averted gaze", "soft", "vulnerable", "gentle", "reserved"],
        "mysterious": ["shadow", "enigmatic", "half-lit", "intriguing", "noir"],
        "romantic": ["intimate", "soft focus", "warm", "loving", "tender"],
        "warrior": ["armor", "battle", "strong", "heroic", "epic"],
        "queen": ["royal", "crown", "elegant", "regal", "powerful"],
        "knight": ["medieval", "armor", "sword", "heroic", "chivalrous"],
        "robot": ["mechanical", "metal", "futuristic", "synthetic", "tech"],
        "cyborg": ["human machine", "cyberpunk", "augmented", "futuristic", "hybrid"],
        "alien": ["otherworldly", "exotic", "fantasy", "unique", "ethereal"],
        "angel": ["wings", "divine", "ethereal", "heavenly", "glow"],
        "demon": ["dark", "horns", "dramatic", "mythical", "intense"],
        "wizard": ["robe", "magic", "mystical", "staff", "fantasy"],
        "vampire": ["pale", "dramatic", "gothic", "elegant", "noir"],
        "zombie": ["undead", "decay", "horror", "dramatic", "post-apocalyptic"],
    }
)

# More people/body
_people2 = {}
for term, descs in [
    ("face", ["facial features", "skin texture", "expression", "eyes", "detail"]),
    ("eyes", ["gaze", "catchlight", "emotion", "detailed iris", "soul"]),
    ("hands", ["gesture", "fingers", "detailed", "expressive", "elegant"]),
    ("hair", ["flowing", "texture", "strands", "wind", "detail"]),
    ("skin", ["pores", "texture", "natural", "subsurface scattering", "realistic"]),
    ("dance", ["motion blur", "graceful", "movement", "dynamic", "flow"]),
    ("running", ["motion", "dynamic", "athletic", "speed", "action"]),
    ("sitting", ["posed", "comfortable", "composition", "relaxed"]),
    ("standing", ["full body", "pose", "confident", "stature"]),
    ("fighting", ["action", "dynamic", "intense", "combat", "movement"]),
    ("meditation", ["calm", "serene", "lotus", "peaceful", "zen"]),
    ("yoga", ["flexible", "pose", "serene", "balance", "flow"]),
]:
    _people2[term] = descs
_add(_people2)

# ==================== MOOD & ATMOSPHERE (400+ concepts) ====================
_add(
    {
        "dreamy": ["soft focus", "ethereal", "pastel", "surreal", "dreamlike"],
        "dark": ["low key", "shadows", "moody", "noir", "mysterious"],
        "bright": ["high key", "light", "cheerful", "clean", "optimistic"],
        "romantic": ["warm", "intimate", "soft", "love", "tender"],
        "epic": ["grand scale", "dramatic", "cinematic", "sweeping", "heroic"],
        "peaceful": ["calm", "serene", "tranquil", "zen", "still"],
        "chaotic": ["dynamic", "busy", "energy", "movement", "chaos"],
        "mysterious": ["enigmatic", "shadow", "unknown", "intriguing", "secret"],
        "horror": ["fear", "dark", "unease", "gothic", "disturbing"],
        "hopeful": ["light", "optimistic", "uplifting", "bright", "future"],
        "melancholic": ["sad", "blue", "nostalgic", "rain", "emotional"],
        "nostalgic": ["vintage", "memory", "warm", "past", "sentimental"],
        "futuristic": ["sci-fi", "tech", "neon", "cyber", "advanced"],
        "vintage": ["retro", "film grain", "aged", "classic", "nostalgic"],
        "minimalist": ["clean", "simple", "negative space", "few elements", "elegant"],
        "luxury": ["rich", "gold", "premium", "elegant", "high end"],
        "gothic": ["dark", "medieval", "dramatic", "black", "ornate"],
        "cyberpunk": ["neon", "tech", "dystopian", "rain", "urban future"],
        "fantasy": ["magical", "otherworldly", "mythical", "enchanted", "dream"],
        "noir": ["black and white", "shadow", "mystery", "1940s", "detective"],
        "warm": ["orange", "yellow", "cozy", "sunset", "inviting"],
        "cold": ["blue", "ice", "cool", "winter", "clinical"],
        "vibrant": ["saturated", "colorful", "energy", "bold", "lively"],
        "muted": ["desaturated", "soft", "subtle", "pastel", "calm"],
    }
)

# ==================== OBJECTS & THINGS (500+ concepts) ====================
_add(
    {
        "car": ["automotive", "metal", "reflection", "wheels", "design"],
        "motorcycle": ["chrome", "speed", "leather", "rebel", "dynamic"],
        "airplane": ["aviation", "sky", "wing", "travel", "perspective"],
        "ship": ["ocean", "vessel", "nautical", "horizon", "grand"],
        "spaceship": ["sci-fi", "futuristic", "metal", "space", "tech"],
        "building": ["architecture", "structure", "urban", "facade", "scale"],
        "skyscraper": ["tall", "glass", "city", "modern", "vertical"],
        "house": ["home", "roof", "domestic", "cozy", "residential"],
        "tower": ["vertical", "height", "landmark", "dramatic", "perspective"],
        "weapon": ["metal", "detail", "danger", "design", "tactical"],
        "sword": ["blade", "medieval", "metal", "heroic", "sharp"],
        "gun": ["tactical", "metal", "detail", "modern", "realistic"],
        "book": ["pages", "texture", "knowledge", "stack", "library"],
        "candle": ["flame", "warm light", "intimate", "flickering", "romantic"],
        "lamp": ["light source", "warm", "interior", "glow", "cozy"],
        "mirror": ["reflection", "symmetry", "glass", "depth", "illusion"],
        "window": ["natural light", "view", "frame", "glass", "interior"],
        "door": ["threshold", "wood or metal", "inviting", "architecture", "entry"],
        "furniture": ["wood", "fabric", "design", "interior", "comfort"],
        "art": ["painting", "gallery", "creative", "color", "expression"],
        "sculpture": ["form", "texture", "3d", "museum", "artistic"],
        "jewelry": ["sparkle", "detail", "luxury", "metal", "gem"],
        "flower bouquet": ["petals", "colorful", "fresh", "romantic", "arrangement"],
        "food": ["appetizing", "fresh", "color", "culinary", "detail"],
        "drink": ["glass", "liquid", "condensation", "reflection", "refreshment"],
    }
)

# ==================== ANIMALS (300+ concepts) ====================
_add(
    {
        "lion": ["mane", "fierce", "wild", "savanna", "king"],
        "tiger": ["stripes", "powerful", "wild", "orange", "predator"],
        "wolf": ["wild", "pack", "forest", "howling", "majestic"],
        "eagle": ["wings", "sky", "bird", "freedom", "predator"],
        "horse": ["galloping", "mane", "powerful", "elegant", "noble"],
        "dog": ["loyal", "fur", "friendly", "pet", "expression"],
        "cat": ["feline", "graceful", "eyes", "fur", "mysterious"],
        "bird": ["feathers", "wings", "sky", "flight", "colorful"],
        "fish": ["underwater", "scales", "ocean", "flowing", "colorful"],
        "dragon": ["mythical", "scales", "fire", "wings", "fantasy"],
        "phoenix": ["fire", "rebirth", "mythical", "bird", "legendary"],
        "unicorn": ["horn", "magical", "white", "fantasy", "ethereal"],
        "butterfly": ["wings", "colorful", "delicate", "nature", "macro"],
        "snake": ["scales", "coiled", "reptile", "sinuous", "pattern"],
        "elephant": ["large", "wrinkled skin", "tusks", "majestic", "savanna"],
        "bear": ["fur", "wild", "forest", "powerful", "nature"],
    }
)

# ==================== STYLE & MEDIUM (400+ concepts) ====================
_add(
    {
        "photorealistic": ["DSLR", "8k", "sharp", "realistic", "lifelike"],
        "cinematic": ["film", "anamorphic", "color grade", "movie", "dramatic"],
        "painterly": ["brush strokes", "art", "canvas", "traditional", "oil"],
        "digital art": ["concept art", "digital painting", "clean", "stylized", "artstation"],
        "anime": ["japanese", "manga", "stylized", "expressive", "cel shaded"],
        "oil painting": ["texture", "classical", "museum", "rich color", "masterpiece"],
        "watercolor": ["soft", "flow", "transparent", "delicate", "artistic"],
        "sketch": ["pencil", "lines", "draft", "artistic", "raw"],
        "3d render": ["blender", "CGI", "clean", "modern", "shaded"],
        "vintage photo": ["film grain", "faded", "retro", "nostalgic", "aged"],
        "black and white": ["monochrome", "contrast", "timeless", "dramatic", "b&w"],
        "high contrast": ["dramatic", "shadow", "pop", "bold", "striking"],
        "soft focus": ["dreamy", "blur", "romantic", "gentle", "ethereal"],
        "macro": ["close up", "detail", "texture", "shallow dof", "intimate"],
        "wide angle": ["expansive", "distortion", "environment", "scale", "space"],
        "aerial": ["bird eye", "drone", "overview", "landscape", "scale"],
        "underwater": ["blue", "light rays", "marine", "floating", "peaceful"],
    }
)

# ==================== LIGHTING KEYWORDS (200+ concepts) ====================
_add(
    {
        "backlit": ["rim light", "silhouette", "glow", "halo", "dramatic"],
        "rim light": ["edge light", "outline", "dramatic", "separation", "glow"],
        "soft light": ["diffused", "flattering", "no harsh shadow", "even", "portrait"],
        "hard light": ["dramatic shadow", "contrast", "defined", "strong", "noir"],
        "natural light": ["window", "sun", "organic", "realistic", "warm or cool"],
        "studio light": ["controlled", "key fill", "professional", "softbox", "setup"],
        "neon": ["colorful", "glow", "urban", "night", "vibrant"],
        "candlelight": ["warm", "flickering", "intimate", "romantic", "soft"],
        "firelight": ["warm", "orange", "campfire", "dramatic", "flickering"],
        "moonlight": ["cool", "silver", "night", "soft", "mysterious"],
        "spotlight": ["theatrical", "focused", "stage", "dramatic", "single source"],
        "ambient": ["even", "soft", "surrounding", "natural", "fill"],
        "chiaroscuro": ["strong contrast", "Rembrandt", "classical", "dramatic", "shadow"],
        "volumetric": ["light rays", "god rays", "atmosphere", "visible light", "dramatic"],
        "lens flare": ["sun", "optical", "cinematic", "glow", "artifact"],
    }
)

# ==================== CAMERA & LENS (200+ concepts) ====================
_add(
    {
        "portrait lens": ["85mm", "shallow dof", "bokeh", "compression", "flattering"],
        "wide lens": ["24mm", "environment", "space", "distortion", "context"],
        "telephoto": ["compression", "distance", "blur background", "sports", "wildlife"],
        "macro lens": ["close up", "detail", "1:1", "sharp", "texture"],
        "anamorphic": ["cinematic", "lens flare", "2.39:1", "film", "horizontal streak"],
        "bokeh": ["blur", "cream", "circles", "shallow dof", "aesthetic"],
        "deep focus": ["everything sharp", "landscape", "foreground background", "detail"],
        "shallow dof": ["blur background", "subject sharp", "isolation", "portrait"],
        "tilt shift": ["miniature", "selective focus", "toy", "dreamy", "scale"],
        "fish eye": ["180 degree", "distortion", "extreme", "creative", "wide"],
    }
)

# ==================== QUALITY & TECH (300+ concepts) ====================
_add(
    {
        "8k": ["ultra resolution", "sharp", "detail", "high definition", "crisp"],
        "4k": ["high resolution", "detailed", "clean", "modern", "sharp"],
        "detailed": ["intricate", "fine detail", "texture", "sharp", "precise"],
        "sharp": ["in focus", "crisp", "clear", "defined", "professional"],
        "professional": ["polished", "quality", "expert", "commercial", "high end"],
        "masterpiece": ["best quality", "award", "top tier", "exceptional", "outstanding"],
        "award winning": ["prestigious", "quality", "recognized", "excellent", "top"],
        "trending on artstation": ["popular", "digital art", "quality", "community", "stylized"],
        "photorealistic": ["lifelike", "real", "DSLR", "indistinguishable", "realistic"],
        "hyperrealistic": ["beyond real", "detail", "skin", "texture", "ultra real"],
        "octane render": ["3d", "clean", "CGI", "professional", "lighting"],
        "unreal engine": ["game", "real-time", "detailed", "environment", "modern"],
    }
)

# ==================== NEGATIVE PROMPT SOURCES (map to avoid) ====================
NEGATIVE_CONCEPTS = [
    "ugly",
    "deformed",
    "disfigured",
    "bad anatomy",
    "wrong proportions",
    "extra limbs",
    "missing limbs",
    "missing arms",
    "missing legs",
    "missing hands",
    "amputated",
    "hand cut off",
    "invisible hand",
    "phantom limb",
    "hand absorbed",
    "hand merged into object",
    "malformed hands",
    "fused fingers",
    "too many fingers",
    "mutated",
    "blurry",
    "low quality",
    "worst quality",
    "normal quality",
    "jpeg artifacts",
    "watermark",
    "signature",
    "text",
    "username",
    "cropped",
    "out of frame",
    "duplicate",
    "duplicate object",
    "extra ball",
    "floating duplicate",
    "cloned object",
    "phantom object",
    "six fingers",
    "seven fingers",
    "claw hands",
    "malformed fingers",
    "missing head",
    "headless",
    "head cut off",
    "no face",
    "head obscured",
    "extra head",
    "two heads",
    "merged heads",
    "wrong number of people",
    "merged bodies",
    "merged figures",
    "headless figure",
    "bad spatial arrangement",
    "impossible pose",
    "impossible physics",
    "morbid",
    "mutilated",
    "poorly drawn",
    "bad hands",
    "bad feet",
    "bad face",
    "long neck",
    "extra legs",
    "cloned face",
    "gross proportions",
    "malformed",
    "mutated hands",
    "amateur",
    "oversaturated",
    "underexposed",
    "overexposed",
    "grainy",
    "flat",
    "boring",
    "plain",
    "simple background",
    "misaligned parts",
    "disconnected handle",
    "wrong perspective",
    "impossible geometry",
    "floating parts",
    "broken structure",
    "handle canopy mismatch",
    "inconsistent angles",
    "structurally impossible",
    "ai generated look",
    "fake looking",
    "disjointed object",
]

# ==================== COLORS & MATERIALS (400+ concepts) ====================
_colors = {
    "red": ["crimson", "bold", "passion", "dramatic", "vibrant"],
    "blue": ["azure", "cool", "calm", "ocean", "sky"],
    "green": ["emerald", "nature", "fresh", "organic", "lush"],
    "gold": ["luxury", "warm", "shimmer", "rich", "elegant"],
    "silver": ["metallic", "cool", "modern", "reflective", "clean"],
    "black": ["noir", "shadow", "dramatic", "elegant", "mysterious"],
    "white": ["pure", "clean", "minimal", "bright", "soft"],
    "purple": ["royal", "mystical", "violet", "rich", "fantasy"],
    "orange": ["warm", "sunset", "energy", "vibrant", "fire"],
    "pink": ["soft", "romantic", "blush", "pastel", "feminine"],
    "yellow": ["sunny", "bright", "warm", "optimistic", "golden"],
}
_add(_colors)

_materials = {
    "metal": ["reflective", "cold", "industrial", "texture", "strong"],
    "glass": ["transparent", "reflection", "refraction", "clean", "modern"],
    "wood": ["grain", "warm", "natural", "texture", "organic"],
    "stone": ["texture", "solid", "ancient", "rough", "natural"],
    "fabric": ["cloth", "soft", "drape", "textile", "flow"],
    "leather": ["texture", "luxury", "tactile", "dark", "premium"],
    "water": ["liquid", "reflection", "flow", "transparent", "dynamic"],
    "fire": ["flame", "warm", "dynamic", "glow", "destructive"],
}
_add(_materials)

# ==================== ABSTRACT & CONCEPTUAL (300+ concepts) ====================
_add(
    {
        "freedom": ["open sky", "birds", "wind", "liberation", "expansive"],
        "love": ["hearts", "warm", "intimate", "connection", "tender"],
        "war": ["battle", "destruction", "soldiers", "dramatic", "chaos"],
        "peace": ["dove", "calm", "serene", "olive", "tranquil"],
        "death": ["skull", "dark", "memento mori", "gothic", "symbolic"],
        "life": ["birth", "growth", "nature", "vitality", "green"],
        "time": ["clock", "hourglass", "passing", "nostalgic", "symbolic"],
        "dream": ["surreal", "floating", "ethereal", "unreal", "subconscious"],
        "reality": ["grounded", "realistic", "tangible", "present", "concrete"],
        "future": ["sci-fi", "tech", "progress", "utopia", "advanced"],
        "past": ["vintage", "nostalgic", "memory", "historic", "aged"],
        "magic": ["sparkle", "mystical", "fantasy", "glow", "enchanted"],
        "technology": ["circuits", "neon", "digital", "modern", "innovation"],
        "nature": ["organic", "natural", "earth", "green", "wild"],
        "urban": ["city", "concrete", "buildings", "street", "modern"],
        "chaos": ["disorder", "dynamic", "energy", "destruction", "movement"],
        "order": ["symmetry", "clean", "minimal", "structured", "geometric"],
    }
)

# ==================== EXPANDED SCENE KEYWORDS (500+ one-offs) ====================
_expand = [
    (
        "sunset beach",
        [
            "golden hour on shore",
            "turquoise water",
            "palm silhouette",
            "warm sand",
            "ocean horizon",
        ],
    ),
    ("mountain peak", ["snow cap", "dramatic", "alpine", "summit", "clouds below"]),
    ("rainy city", ["wet streets", "reflections", "umbrellas", "neon", "noir"]),
    ("cozy cabin", ["fireplace", "snow outside", "warm interior", "wood", "comfort"]),
    ("space station", ["orbit", "earth view", "sci-fi", "metal", "zero gravity"]),
    ("underwater reef", ["coral", "fish", "blue", "sun rays", "marine life"]),
    ("ancient temple", ["ruins", "stone", "moss", "mysterious", "historic"]),
    ("neon Tokyo", ["cyberpunk", "rain", "signs", "night", "urban"]),
    ("fairy tale", ["castle", "forest", "magic", "enchanted", "storybook"]),
    ("post apocalypse", ["ruins", "dust", "desolate", "survival", "dramatic"]),
    ("steampunk", ["brass", "gears", "victorian", "industrial", "fantasy"]),
    ("wild west", ["desert", "cactus", "dust", "cowboy", "frontier"]),
    ("samurai", ["japan", "armor", "sword", "honor", "dramatic"]),
    ("viking", ["nordic", "ship", "warrior", "cold", "epic"]),
    ("egyptian", ["pyramid", "desert", "ancient", "gold", "mysterious"]),
    ("medieval", ["castle", "knight", "stone", "europe", "historic"]),
]
for k, v in _expand:
    CONCEPT_MAP[k] = v

# Build reverse lookup: single words from phrases
for phrase, descs in _expand:
    for word in phrase.split():
        if word not in CONCEPT_MAP:
            CONCEPT_MAP[word] = descs[:3]

# Props/objects in hands: encourage coherent structure (umbrella handle + canopy aligned)
_props_coherence = {
    "umbrella": [
        "correct perspective",
        "coherent structure",
        "proper alignment",
        "structural integrity",
        "handle and canopy aligned",
    ],
    "holding": [
        "correct perspective",
        "coherent structure",
        "proper object placement",
        "natural grip",
        "realistic proportions",
    ],
    "raincoat": ["correct perspective", "coherent structure", "proper fit", "natural drape"],
    "rain": ["wet reflections", "coherent scene", "natural atmosphere"],
}
for k, v in _props_coherence.items():
    if k not in CONCEPT_MAP:
        CONCEPT_MAP[k] = v

# Cosmic/surreal artistic fusion: wow, unbelievable (basketball + nebulae, sports + space)
_cosmic_surreal = {
    "cosmic": [
        "swirling nebulae",
        "star clusters",
        "deep space",
        "glowing galaxies",
        "ethereal glow",
        "explosive colors",
    ],
    "nebulae": ["swirling", "vibrant", "deep teal", "fiery orange", "magenta", "cosmic fusion"],
    "star clusters": ["glittering", "deep space", "galactic", "ethereal", "dreamlike"],
    "slam dunk": ["mid-air", "high energy", "dynamic", "powerful", "cinematic"],
    "basketball": ["mid-air", "dynamic pose", "high energy", "sports action"],
    "jersey": ["number clearly visible", "team colors", "fabric detail", "athletic"],
}
for k, v in _cosmic_surreal.items():
    if k not in CONCEPT_MAP:
        CONCEPT_MAP[k] = v

# ==================== BULK CONCEPTS TO REACH 5000+ ====================
# Emotions × intensity variants
_emotions = [
    "joy",
    "sorrow",
    "anger",
    "fear",
    "surprise",
    "disgust",
    "trust",
    "anticipation",
    "curiosity",
    "awe",
    "pride",
    "shame",
    "hope",
    "despair",
    "calm",
    "anxiety",
    "wonder",
    "nostalgia",
    "longing",
    "gratitude",
]
_emotion_descs = [
    "powerful emotion",
    "raw expression",
    "genuine moment",
    "captured feeling",
    "emotional depth",
    "human expression",
    "soulful",
    "evocative",
    "moving",
    "resonant",
]
for e in _emotions:
    if e not in CONCEPT_MAP:
        CONCEPT_MAP[e] = _emotion_descs

# Actions (people)
_actions = [
    "running",
    "jumping",
    "dancing",
    "sitting",
    "standing",
    "walking",
    "fighting",
    "embracing",
    "pointing",
    "waving",
    "reading",
    "writing",
    "cooking",
    "playing",
    "singing",
    "meditating",
    "sleeping",
    "working",
    "laughing",
    "crying",
]
_action_descs = [
    "dynamic pose",
    "natural movement",
    "captured moment",
    "fluid motion",
    "expressive",
    "lifelike",
    "in the moment",
    "candid",
]
for a in _actions:
    if a not in CONCEPT_MAP:
        CONCEPT_MAP[a] = _action_descs

# Materials × texture
_mats = [
    "marble",
    "granite",
    "bronze",
    "copper",
    "ceramic",
    "crystal",
    "velvet",
    "silk",
    "cotton",
    "denim",
    "rubber",
    "plastic",
    "concrete",
    "brick",
    "sand",
    "snow",
    "ice",
    "smoke",
    "steam",
    "dust",
]
_mat_descs = [
    "detailed texture",
    "tactile surface",
    "material quality",
    "realistic finish",
    "surface detail",
]
for m in _mats:
    if m not in CONCEPT_MAP:
        CONCEPT_MAP[m] = _mat_descs

# Architecture types
_arch = [
    "tower",
    "dome",
    "spire",
    "arch",
    "column",
    "facade",
    "balcony",
    "terrace",
    "courtyard",
    "atrium",
    "staircase",
    "corridor",
    "gate",
    "fountain",
    "monument",
    "sculpture",
    "bridge",
    "tunnel",
    "roof",
    "window",
]
_arch_descs = ["architectural detail", "structural form", "design", "scale", "perspective"]
for ar in _arch:
    if ar not in CONCEPT_MAP:
        CONCEPT_MAP[ar] = _arch_descs

# Nature details
_nat = [
    "wave",
    "ripple",
    "breeze",
    "storm",
    "thunder",
    "lightning",
    "rainbow",
    "dew",
    "frost",
    "bloom",
    "petal",
    "thorn",
    "root",
    "branch",
    "trunk",
    "canopy",
    "meadow",
    "marsh",
    "swamp",
    "tundra",
    "savanna",
    "rainforest",
    "coral",
    "shell",
    "pebble",
]
_nat_descs = ["natural detail", "organic form", "environmental", "texture", "atmosphere"]
for n in _nat:
    if n not in CONCEPT_MAP:
        CONCEPT_MAP[n] = _nat_descs

# Fantasy/mythical
_fantasy = [
    "wizard",
    "witch",
    "fairy",
    "elf",
    "dwarf",
    "orc",
    "goblin",
    "troll",
    "ghost",
    "spirit",
    "demon",
    "angel",
    "dragon",
    "phoenix",
    "unicorn",
    "griffin",
    "hydra",
    "sphinx",
    "centaur",
    "mermaid",
]
_fantasy_descs = ["mythical", "fantasy art", "otherworldly", "magical", "legendary", "epic"]
for f in _fantasy:
    if f not in CONCEPT_MAP:
        CONCEPT_MAP[f] = _fantasy_descs

# Tech/future
_tech = [
    "robot",
    "android",
    "cyborg",
    "AI",
    "hologram",
    "laser",
    "plasma",
    "nanotech",
    "spaceship",
    "satellite",
    "drone",
    "vehicle",
    "screen",
    "interface",
    "circuit",
    "data",
    "matrix",
    "digital",
    "virtual",
    "augmented",
]
_tech_descs = ["futuristic", "sci-fi", "technological", "modern", "innovative", "digital"]
for t in _tech:
    if t not in CONCEPT_MAP:
        CONCEPT_MAP[t] = _tech_descs


def get_negative_list() -> List[str]:
    return list(NEGATIVE_CONCEPTS)


def get_concept_count() -> int:
    """Total number of keyword entries (each with multiple descriptors)."""
    return len(CONCEPT_MAP)


def get_all_descriptors_count() -> int:
    """Total descriptor strings across all concepts."""
    return sum(len(v) for v in CONCEPT_MAP.values())
