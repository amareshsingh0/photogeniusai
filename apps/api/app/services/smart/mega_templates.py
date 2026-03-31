"""
Mega Prompt Templates - 50+ Domain-Specific Templates for World-Class Image Generation

Each template contains:
- prefix: Mode-specific prompt prefix
- quality_boost: Keywords that dramatically improve quality for this mode
- technical: Technical parameters and details
- negative: Mode-specific negative prompt (CRITICAL for quality)
- camera: Recommended camera settings string
- lighting: Best lighting for this mode

These templates are the SECRET WEAPON - the difference between average and world-class output.
PixArt-Sigma responds extremely well to structured, keyword-rich prompts.
"""

from typing import Dict, Optional


# ============================================================
# MASTER TEMPLATE DATABASE (50+ templates)
# ============================================================

MEGA_TEMPLATES: Dict[str, Dict[str, str]] = {

    # ============================================================
    # REALISM (Photorealistic)
    # ============================================================
    "REALISM": {
        "prefix": "RAW photo, ",
        "quality_boost": "professional photography, photorealistic, 8k uhd, dslr, sharp focus, natural lighting, film grain, Fujifilm XT3, detailed skin texture",
        "technical": "highly detailed, subsurface scattering, perfect exposure, depth of field, natural colors, realistic proportions, accurate anatomy",
        "negative": "cartoon, 3d render, anime, drawing, painting, illustration, disfigured, bad art, deformed, extra limbs, mutation, ugly, bad anatomy, blurry, duplicate, lowres, watermark, text, worst quality, oversaturated, underexposed, overexposed",
        "camera": "85mm lens, f/1.8, shallow depth of field",
        "lighting": "natural lighting, soft shadows",
    },
    "REALISM_PORTRAIT": {
        "prefix": "RAW photo, professional portrait, ",
        "quality_boost": "studio portrait photography, 85mm lens, f/1.4, bokeh background, sharp eyes, facial details, skin pores visible, professional headshot",
        "technical": "Rembrandt lighting, catchlights in eyes, natural skin texture, subsurface scattering, shallow depth of field, perfectly focused on eyes",
        "negative": "cartoon, painting, blurry eyes, asymmetric face, extra fingers, deformed, ugly, bad anatomy, poorly drawn face, mutation, disfigured, worst quality, lowres, watermark",
        "camera": "85mm f/1.4, Canon EOS R5, eye-level",
        "lighting": "Rembrandt lighting, softbox key light, fill light",
    },
    "REALISM_GROUP": {
        "prefix": "RAW photo, group photograph, ",
        "quality_boost": "professional group photography, multiple people, well-arranged, sharp focus on all subjects, natural poses, genuine expressions",
        "technical": "f/5.6 for depth, 35mm lens, everyone in focus, balanced composition, natural interaction, candid moments",
        "negative": "blurry faces, extra limbs, merged bodies, deformed, bad anatomy, clone faces, identical faces, worst quality, lowres",
        "camera": "35mm lens, f/5.6, medium shot",
        "lighting": "even lighting, natural outdoor light",
    },
    "REALISM_FASHION": {
        "prefix": "RAW photo, fashion editorial, ",
        "quality_boost": "high fashion photography, Vogue magazine quality, editorial style, designer clothing, model pose, fashion shoot",
        "technical": "dramatic lighting, color grading, high contrast, fashion magazine, runway quality, perfect styling, haute couture",
        "negative": "amateur, casual, low quality, blurry, bad pose, wrinkled clothes, ugly, deformed, worst quality",
        "camera": "70-200mm lens, fashion photography setup",
        "lighting": "studio flash, beauty dish, rim light",
    },
    "REALISM_WEDDING": {
        "prefix": "RAW photo, wedding photography, ",
        "quality_boost": "professional wedding photograph, romantic, elegant, beautiful couple, wedding dress, ceremony, celebration, love",
        "technical": "soft focus, dreamy atmosphere, golden hour light, bokeh, emotional moment, candid wedding photography",
        "negative": "ugly, bad anatomy, deformed, blurry, low quality, amateur, dark, overexposed, worst quality",
        "camera": "70-200mm f/2.8, full frame",
        "lighting": "golden hour, backlit, warm tones",
    },
    "REALISM_STREET": {
        "prefix": "RAW photo, street photography, ",
        "quality_boost": "candid street photography, urban life, authentic moment, decisive moment, Henri Cartier-Bresson style, documentary",
        "technical": "35mm lens, natural light, high contrast, grain, authentic, unposed, real life, urban environment",
        "negative": "staged, fake, artificial, blurry, low quality, deformed, ugly, worst quality, watermark",
        "camera": "35mm lens, f/8, zone focus",
        "lighting": "available light, harsh shadows, natural",
    },

    # ============================================================
    # CINEMATIC
    # ============================================================
    "CINEMATIC": {
        "prefix": "cinematic still, ",
        "quality_boost": "anamorphic lens, film grain, dramatic lighting, movie scene, blockbuster quality, Hollywood production, 4k cinematography",
        "technical": "35mm film, color grading, atmospheric, volumetric lighting, lens flare, shallow depth of field, epic composition, widescreen aspect ratio",
        "negative": "flat, boring, amateur, low quality, blurry, bad anatomy, deformed, ugly, worst quality, overexposed, cartoon, anime, drawing, bright, cheerful",
        "camera": "anamorphic lens, 2.39:1 aspect ratio",
        "lighting": "dramatic volumetric lighting, atmospheric haze",
    },
    "CINEMATIC_NOIR": {
        "prefix": "film noir still, ",
        "quality_boost": "classic film noir, black and white, high contrast, dramatic shadows, 1940s atmosphere, detective movie, moody",
        "technical": "chiaroscuro lighting, venetian blinds shadows, smoke, rain, wet streets, fedora, dramatic angles, low key lighting",
        "negative": "colorful, bright, cheerful, modern, cartoon, anime, low quality, blurry, deformed, ugly",
        "camera": "wide angle lens, dutch angle, low angle",
        "lighting": "single hard light source, deep shadows, silhouette",
    },
    "CINEMATIC_SCIFI": {
        "prefix": "science fiction movie still, ",
        "quality_boost": "sci-fi blockbuster, futuristic, advanced technology, space, alien world, cybernetic, holographic displays",
        "technical": "volumetric lighting, lens flare, anamorphic, particle effects, neon accents, metallic surfaces, blade runner atmosphere",
        "negative": "medieval, old-fashioned, cartoon, amateur, low quality, blurry, deformed, ugly, worst quality",
        "camera": "anamorphic widescreen, extreme wide shot",
        "lighting": "neon lighting, holographic, volumetric fog",
    },
    "CINEMATIC_ACTION": {
        "prefix": "action movie still, ",
        "quality_boost": "high octane action scene, explosive, dynamic, intense, blockbuster, Michael Bay style, fast-paced",
        "technical": "motion blur, dramatic angle, debris, fire, smoke, extreme close-up, slow motion freeze frame, adrenaline",
        "negative": "static, boring, calm, peaceful, cartoon, anime, low quality, blurry, deformed, ugly",
        "camera": "handheld camera, dynamic angle, wide lens",
        "lighting": "explosive lighting, fire glow, practical lights",
    },
    "CINEMATIC_HORROR": {
        "prefix": "horror movie still, ",
        "quality_boost": "psychological horror, terrifying, unsettling, eerie, dark atmosphere, dread, suspense, nightmare",
        "technical": "desaturated colors, deep shadows, fog, mist, distorted perspective, uncomfortable framing, blood red accents",
        "negative": "bright, happy, colorful, cartoon, anime, cheerful, low quality, blurry, deformed, ugly",
        "camera": "wide angle distortion, low angle, extreme close-up",
        "lighting": "underexposed, single light source, flickering, cold blue",
    },

    # ============================================================
    # ART (Traditional)
    # ============================================================
    "ART": {
        "prefix": "fine art, ",
        "quality_boost": "masterpiece, museum quality, gallery exhibition, fine art, professional artwork, exceptional detail",
        "technical": "perfect technique, rich colors, detailed, luminous, classical composition, art historical significance",
        "negative": "amateur, ugly, low quality, blurry, deformed, bad proportions, childish, worst quality",
        "camera": "",
        "lighting": "gallery lighting, natural light",
    },
    "ART_OIL_PAINTING": {
        "prefix": "oil painting, ",
        "quality_boost": "masterpiece oil painting, museum quality, thick impasto brushstrokes, rich oil colors, canvas texture, classical technique",
        "technical": "glazing technique, chiaroscuro, luminous skin tones, visible brushwork, layered paint, Old Master technique, gallery quality",
        "negative": "photo, realistic, digital, flat, amateur, blurry, low quality, cartoon, anime, sketch, pencil, watercolor",
        "camera": "",
        "lighting": "Rembrandt lighting, warm golden light, chiaroscuro",
    },
    "ART_WATERCOLOR": {
        "prefix": "watercolor painting, ",
        "quality_boost": "beautiful watercolor, wet on wet technique, delicate washes, transparent layers, paper texture visible, artistic",
        "technical": "soft edges, color bleeding, white paper highlights, granulation, fluid brushstrokes, loose style, professional watercolor",
        "negative": "photo, realistic, digital, oil painting, thick paint, cartoon, anime, blurry, low quality, muddy colors",
        "camera": "",
        "lighting": "soft natural light, white paper showing through",
    },
    "ART_PENCIL_SKETCH": {
        "prefix": "pencil sketch, ",
        "quality_boost": "detailed pencil drawing, graphite on paper, cross-hatching, fine lines, artistic sketch, professional illustration",
        "technical": "varied line weight, shading gradients, paper texture, precise hatching, tonal range, white highlights, charcoal accents",
        "negative": "color, painted, digital, blurry, low quality, amateur, messy, cartoon, photo, realistic",
        "camera": "",
        "lighting": "side lighting to show texture and form",
    },
    "ART_INK_DRAWING": {
        "prefix": "ink drawing, ",
        "quality_boost": "professional ink illustration, black ink on white paper, detailed linework, pen and ink, stippling, cross-hatching",
        "technical": "precise lines, high contrast black and white, varied line weight, negative space, clean edges, editorial illustration quality",
        "negative": "color, painted, blurry, messy, amateur, photo, realistic, low quality, cartoon",
        "camera": "",
        "lighting": "",
    },
    "ART_CHARCOAL": {
        "prefix": "charcoal drawing, ",
        "quality_boost": "expressive charcoal artwork, dramatic contrast, rich blacks, soft gradients, textured paper, museum quality",
        "technical": "smudging technique, dramatic tonal range, gestural marks, atmospheric depth, conte crayon accents, fixative finish",
        "negative": "color, digital, cartoon, anime, photo, low quality, blurry, amateur, ugly",
        "camera": "",
        "lighting": "dramatic side lighting, strong contrast",
    },
    "ART_PASTEL": {
        "prefix": "pastel artwork, ",
        "quality_boost": "soft pastel painting, vibrant pigments, textured paper surface, blended colors, luminous, gallery quality",
        "technical": "layered pastels, finger blending, fixative layers, rich saturation, velvety texture, impressionist technique",
        "negative": "photo, digital, cartoon, anime, oil painting, watercolor, blurry, low quality, muddy",
        "camera": "",
        "lighting": "soft diffused light, warm tones",
    },

    # ============================================================
    # DIGITAL ART
    # ============================================================
    "DIGITAL_ART": {
        "prefix": "digital art, ",
        "quality_boost": "trending on artstation, award winning digital art, highly detailed, 4k, 8k, intricate details, professional illustration",
        "technical": "perfect lighting, vibrant colors, dynamic composition, cinematic color grading, concept art quality, clean edges",
        "negative": "ugly, poorly drawn, out of frame, mutation, mutated, extra limbs, disfigured, deformed, text, watermark, worst quality, low quality, amateur",
        "camera": "",
        "lighting": "dramatic digital lighting, rim light, ambient occlusion",
    },
    "DIGITAL_ART_CONCEPT": {
        "prefix": "concept art, ",
        "quality_boost": "professional concept art, AAA game studio quality, environment design, character design, detailed worldbuilding",
        "technical": "painterly style, atmospheric perspective, color keys, mood painting, production quality, art direction",
        "negative": "amateur, ugly, bad proportions, low quality, blurry, photo, realistic, cartoon, anime",
        "camera": "",
        "lighting": "dramatic concept art lighting, atmospheric",
    },
    "DIGITAL_ART_MATTE": {
        "prefix": "matte painting, ",
        "quality_boost": "epic matte painting, VFX quality, cinematic environment, vast landscape, fantasy world, photorealistic background",
        "technical": "hyper detailed, atmospheric depth, volumetric lighting, god rays, scale reference, panoramic vista, film production quality",
        "negative": "flat, amateur, low quality, blurry, ugly, cartoon, simple, minimal",
        "camera": "extreme wide shot, panoramic",
        "lighting": "golden hour, god rays, atmospheric haze",
    },
    "DIGITAL_ART_3D_RENDER": {
        "prefix": "3D render, ",
        "quality_boost": "photorealistic 3D render, Octane render, Unreal Engine 5, ray tracing, global illumination, PBR materials",
        "technical": "subsurface scattering, caustics, volumetric fog, ambient occlusion, physically based rendering, studio lighting setup",
        "negative": "flat, 2D, hand drawn, sketch, low poly, wireframe, untextured, low quality, amateur",
        "camera": "rendered camera, f/2.8, depth of field",
        "lighting": "HDRI lighting, three-point setup, ray traced shadows",
    },
    "DIGITAL_ART_CLAY_RENDER": {
        "prefix": "clay render, ",
        "quality_boost": "smooth clay material, matte finish, sculptural quality, Blender clay render, ambient occlusion, soft shadows",
        "technical": "single color material, no texture, smooth surface, studio lighting, minimal, clean, 3D sculpt quality",
        "negative": "textured, colorful, realistic, photo, hand drawn, low quality, rough, ugly",
        "camera": "studio camera, even lighting",
        "lighting": "soft studio lighting, even illumination, subtle shadows",
    },
    "DIGITAL_ART_LOW_POLY": {
        "prefix": "low poly art, ",
        "quality_boost": "geometric low poly style, faceted surfaces, clean edges, minimalist 3D, modern digital art, crisp triangles",
        "technical": "flat shading, geometric shapes, triangulated mesh, pastel colors, clean background, isometric perspective option",
        "negative": "realistic, photo, smooth, organic, blurry, ugly, detailed texture, high poly",
        "camera": "",
        "lighting": "flat lighting, gradient background",
    },
    "DIGITAL_ART_ISOMETRIC": {
        "prefix": "isometric art, ",
        "quality_boost": "isometric view, diorama style, miniature world, detailed isometric illustration, pixel perfect edges, clean design",
        "technical": "30-degree angle, no perspective distortion, detailed interiors visible, cutaway view, game asset quality, tile-based",
        "negative": "perspective, realistic, photo, blurry, ugly, messy, low quality, amateur",
        "camera": "isometric camera, 30-degree angle, orthographic",
        "lighting": "even top-down lighting, soft shadows",
    },

    # ============================================================
    # ANIME & MANGA
    # ============================================================
    "ANIME": {
        "prefix": "anime illustration, ",
        "quality_boost": "anime style, manga aesthetic, vibrant colors, cel shading, clean lineart, detailed illustration, high quality anime",
        "technical": "Japanese anime art, expressive eyes, dynamic pose, clean lines, detailed hair, professional illustration",
        "negative": "realistic, 3d render, western cartoon, ugly, bad anatomy, poorly drawn, low quality, blurry, deformed, extra fingers",
        "camera": "",
        "lighting": "anime lighting, bright colors, dynamic shadows",
    },
    "ANIME_MANGA": {
        "prefix": "manga panel, black and white manga, ",
        "quality_boost": "professional manga illustration, detailed lineart, screen tones, dynamic composition, manga panel layout",
        "technical": "high contrast black and white, speed lines, screentone shading, dramatic angles, professional manga artist",
        "negative": "color, painted, 3D, realistic, blurry, low quality, amateur, ugly, deformed",
        "camera": "",
        "lighting": "dramatic manga lighting, high contrast",
    },
    "ANIME_CHIBI": {
        "prefix": "chibi character, ",
        "quality_boost": "adorable chibi style, super deformed, big head small body, cute anime, kawaii, colorful, expressive",
        "technical": "2:3 head to body ratio, simple features, round face, big sparkly eyes, pastel colors, clean lineart",
        "negative": "realistic, scary, dark, horror, ugly, deformed, low quality, blurry, bad anatomy",
        "camera": "",
        "lighting": "bright, cheerful, soft pastel lighting",
    },
    "ANIME_GHIBLI": {
        "prefix": "Studio Ghibli style, ",
        "quality_boost": "Hayao Miyazaki style, hand-painted background, lush nature, whimsical, warm atmosphere, nostalgic",
        "technical": "watercolor backgrounds, detailed environments, soft character design, European countryside influence, magical realism",
        "negative": "dark, gritty, horror, realistic, 3D render, low quality, ugly, deformed, sharp edges, digital",
        "camera": "",
        "lighting": "warm natural light, soft clouds, golden afternoon",
    },

    # ============================================================
    # FANTASY
    # ============================================================
    "FANTASY": {
        "prefix": "fantasy art, ",
        "quality_boost": "epic fantasy, magical, ethereal lighting, enchanted, mystical atmosphere, otherworldly, legendary",
        "technical": "high fantasy, vivid colors, atmospheric depth, dramatic lighting, intricate details, magical glow, ancient runes",
        "negative": "realistic, boring, plain, amateur, low quality, blurry, ugly, deformed, bad anatomy, mundane, modern",
        "camera": "",
        "lighting": "magical ethereal glow, volumetric light, aurora",
    },
    "FANTASY_EPIC": {
        "prefix": "epic fantasy scene, ",
        "quality_boost": "grand scale, legendary, Lord of the Rings quality, vast landscapes, epic battle, heroic, monumental",
        "technical": "sweeping vista, dramatic sky, army in background, castle on mountain, god rays, scale reference, cinematic composition",
        "negative": "small, intimate, modern, cartoon, anime, blurry, low quality, amateur, ugly",
        "camera": "extreme wide angle, epic establishing shot",
        "lighting": "dramatic stormy sky, rays of light breaking through, volumetric",
    },
    "FANTASY_DARK": {
        "prefix": "dark fantasy art, ",
        "quality_boost": "dark souls inspired, gothic fantasy, foreboding, ominous, dark and moody, ancient evil, cursed",
        "technical": "desaturated colors, deep shadows, twisted architecture, fog, embers, decay, eldritch horror, grimdark",
        "negative": "bright, cheerful, colorful, cute, cartoon, low quality, blurry, ugly, amateur",
        "camera": "",
        "lighting": "dim torchlight, ember glow, moonlight, deep shadows",
    },

    # ============================================================
    # PRODUCT PHOTOGRAPHY
    # ============================================================
    "PRODUCT": {
        "prefix": "professional product photography, ",
        "quality_boost": "commercial quality, studio setup, clean background, advertisement ready, sharp focus, high-end product shot",
        "technical": "studio lighting, reflections controlled, gradient background, product hero shot, perfect white balance, color accurate",
        "negative": "blurry, dark, amateur, low quality, dirty, damaged, scratched, ugly, deformed, noisy, grainy, worst quality",
        "camera": "100mm macro lens, product photography setup",
        "lighting": "softbox lighting, controlled reflections, gradient background",
    },
    "PRODUCT_LUXURY": {
        "prefix": "luxury product photography, ",
        "quality_boost": "premium brand, high-end luxury, elegant presentation, prestige, exclusive, sophisticated, advertisement quality",
        "technical": "marble surface, velvet background, golden accents, crystal clarity, perfect reflections, premium materials visible",
        "negative": "cheap, plastic, blurry, amateur, low quality, dirty, dark, ugly, deformed, worst quality",
        "camera": "macro lens, tilt-shift for miniature effect",
        "lighting": "dramatic studio lighting, accent lights, rim light",
    },
    "PRODUCT_FOOD": {
        "prefix": "professional food photography, ",
        "quality_boost": "appetizing food photo, gourmet presentation, food styling, fresh ingredients, delicious, mouth-watering",
        "technical": "shallow depth of field, steam rising, fresh herbs garnish, rustic wooden surface, natural props, food magazine quality",
        "negative": "unappetizing, messy, cold food, blurry, dark, amateur, low quality, ugly, artificial looking, worst quality",
        "camera": "90mm macro, f/2.8, overhead or 45-degree angle",
        "lighting": "natural window light, backlit, warm tones, steam visible",
    },

    # ============================================================
    # ARCHITECTURE
    # ============================================================
    "ARCHITECTURE": {
        "prefix": "architectural photography, ",
        "quality_boost": "professional architecture photo, symmetrical, sharp details, structural beauty, modern architecture, design magazine quality",
        "technical": "perspective correction, tilt-shift lens, golden ratio composition, leading lines, geometric patterns, structural clarity",
        "negative": "blurry, tilted, distorted, amateur, low quality, ugly, cluttered, messy, worst quality",
        "camera": "24mm tilt-shift lens, architectural photography",
        "lighting": "blue hour, dramatic sky, architectural lighting",
    },
    "ARCHITECTURE_INTERIOR": {
        "prefix": "interior design photography, ",
        "quality_boost": "luxury interior, architectural digest quality, spacious, elegant design, designer furniture, home staging",
        "technical": "wide angle, HDR, ambient lighting, architectural details, material textures, cozy atmosphere, decluttered space",
        "negative": "cluttered, messy, dark, blurry, amateur, low quality, ugly, cramped, worst quality",
        "camera": "14-24mm wide angle, interior photography",
        "lighting": "mixed ambient and accent lighting, warm and inviting",
    },
    "ARCHITECTURE_RENDER": {
        "prefix": "architectural visualization, ",
        "quality_boost": "photorealistic architectural render, V-Ray quality, modern building, exterior visualization, presentation quality",
        "technical": "ray tracing, global illumination, PBR materials, landscaping, human scale figures, blue sky, professional arch-viz",
        "negative": "flat, cartoon, unrealistic, low poly, amateur, blurry, ugly, low quality",
        "camera": "eye-level perspective, wide angle",
        "lighting": "daylight, soft shadows, realistic sun position",
    },

    # ============================================================
    # NATURE & LANDSCAPE
    # ============================================================
    "NATURE": {
        "prefix": "nature photography, ",
        "quality_boost": "breathtaking landscape, National Geographic quality, dramatic scenery, pristine nature, awe-inspiring",
        "technical": "wide angle, HDR, golden hour, dramatic sky, perfect exposure, foreground interest, leading lines",
        "negative": "boring, flat, hazy, blurry, amateur, low quality, ugly, deformed, artificial, worst quality",
        "camera": "16-35mm wide angle, landscape photography",
        "lighting": "golden hour, dramatic clouds, natural light",
    },
    "NATURE_WILDLIFE": {
        "prefix": "wildlife photography, ",
        "quality_boost": "National Geographic wildlife, sharp focus on animal, natural habitat, behavioral moment, perfect timing, documentary quality",
        "technical": "telephoto lens compression, eye-level with subject, catchlight in animal eyes, natural behavior, detailed fur or feathers",
        "negative": "blurry, out of focus, captive, zoo, staged, amateur, low quality, ugly, deformed, worst quality",
        "camera": "600mm telephoto, f/4, fast shutter speed",
        "lighting": "natural golden hour, backlit rim light",
    },
    "NATURE_MACRO": {
        "prefix": "macro photography, ",
        "quality_boost": "extreme close-up, incredible detail, tiny world, dewdrops, insect detail, flower petals, professional macro",
        "technical": "focus stacking, shallow depth of field, water droplets, pollen detail, wing venation, iridescence",
        "negative": "blurry, out of focus, boring, low detail, amateur, low quality, ugly, worst quality",
        "camera": "100mm macro lens, f/8, focus stacking",
        "lighting": "diffused natural light, ring flash",
    },
    "NATURE_UNDERWATER": {
        "prefix": "underwater photography, ",
        "quality_boost": "professional underwater photo, coral reef, marine life, crystal clear water, National Geographic quality",
        "technical": "underwater housing, strobe lighting, blue water, sunbeams through water, vivid coral colors, marine biodiversity",
        "negative": "murky, dark, blurry, green water, amateur, low quality, ugly, worst quality",
        "camera": "wide angle underwater housing, fisheye lens",
        "lighting": "underwater strobe, sunlight from above, caustics",
    },

    # ============================================================
    # DESIGN & GRAPHICS
    # ============================================================
    "DESIGN": {
        "prefix": "professional graphic design, ",
        "quality_boost": "clean modern design, professional layout, typography, brand quality, print ready, high resolution",
        "technical": "balanced composition, visual hierarchy, color theory, whitespace, bold graphics, eye-catching",
        "negative": "cluttered, messy, amateur, ugly, blurry, low quality, unprofessional, hard to read, worst quality",
        "camera": "",
        "lighting": "",
    },
    "DESIGN_POSTER": {
        "prefix": "professional poster design, ",
        "quality_boost": "eye-catching poster, modern typography, bold colors, clean layout, print quality, impactful design",
        "technical": "visual hierarchy, focal point, negative space, balanced composition, high contrast, professional typography",
        "negative": "cluttered, unreadable, messy, amateur, ugly, blurry, low quality, crowded, worst quality",
        "camera": "",
        "lighting": "dramatic design lighting",
    },
    "DESIGN_SOCIAL_MEDIA": {
        "prefix": "social media post design, ",
        "quality_boost": "Instagram-worthy, viral content, modern aesthetic, clean design, engaging, scroll-stopping, brand quality",
        "technical": "square or story format, bold typography, gradient background, minimalist layout, trendy colors, engaging composition",
        "negative": "cluttered, boring, amateur, ugly, low quality, hard to read, blurry, worst quality",
        "camera": "",
        "lighting": "",
    },
    "DESIGN_YOUTUBE_THUMBNAIL": {
        "prefix": "YouTube thumbnail, ",
        "quality_boost": "click-worthy thumbnail, bold text, expressive face, bright colors, high contrast, attention grabbing, viral quality",
        "technical": "large bold text, face close-up, bright saturated colors, arrows or circles highlighting, clean readable at small size",
        "negative": "blurry, dark, cluttered, unreadable, boring, amateur, low quality, worst quality",
        "camera": "",
        "lighting": "bright even lighting, no shadows on face",
    },
    "DESIGN_INFOGRAPHIC": {
        "prefix": "professional infographic design, ",
        "quality_boost": "clean infographic, data visualization, icons, charts, modern flat design, information design, print quality",
        "technical": "visual hierarchy, clear data flow, consistent icons, color coded sections, readable at all sizes, professional typography",
        "negative": "cluttered, confusing, messy, amateur, ugly, hard to read, worst quality",
        "camera": "",
        "lighting": "",
    },
    "DESIGN_GREETING_CARD": {
        "prefix": "beautiful greeting card design, ",
        "quality_boost": "elegant card design, festive, heartfelt, professional quality, celebration, ornamental border, premium cardstock feel",
        "technical": "balanced layout, decorative elements, warm colors, elegant typography, border design, centered composition",
        "negative": "ugly, amateur, cluttered, cheap looking, blurry, low quality, worst quality",
        "camera": "",
        "lighting": "warm, festive, golden accents",
    },
    "DESIGN_INVITATION": {
        "prefix": "elegant invitation design, ",
        "quality_boost": "premium invitation card, sophisticated, formal design, luxury paper texture, gold foil accents, calligraphy",
        "technical": "serif typography, centered layout, decorative border, RSVP details, elegant flourishes, embossed effect",
        "negative": "cheap, amateur, cluttered, ugly, informal, blurry, low quality, worst quality",
        "camera": "",
        "lighting": "soft, warm, luxurious golden tones",
    },
    "DESIGN_BUSINESS_CARD": {
        "prefix": "professional business card design, ",
        "quality_boost": "premium business card, minimalist, modern, corporate identity, brand design, luxury finish, spot UV",
        "technical": "clean typography, logo placement, contact info layout, standard card dimensions, embossed or foil effect",
        "negative": "cluttered, cheap, amateur, ugly, hard to read, too many colors, worst quality",
        "camera": "",
        "lighting": "",
    },

    # ============================================================
    # SCIENTIFIC & EDUCATIONAL
    # ============================================================
    "SCIENTIFIC": {
        "prefix": "scientific illustration, ",
        "quality_boost": "professional scientific diagram, educational, anatomically correct, labeled, textbook quality, detailed",
        "technical": "clear labels, accurate proportions, clean lines, informative, color coded, professional illustration",
        "negative": "artistic, abstract, inaccurate, blurry, amateur, low quality, ugly, misleading, worst quality",
        "camera": "",
        "lighting": "clean even lighting for clarity",
    },
    "SCIENTIFIC_BIOLOGY": {
        "prefix": "biological illustration, ",
        "quality_boost": "detailed biology diagram, medical textbook quality, anatomically accurate, cell structure, organism detail",
        "technical": "cross-section view, labeled parts, magnified detail, accurate coloring, educational annotation",
        "negative": "inaccurate, abstract, artistic interpretation, blurry, amateur, low quality, worst quality",
        "camera": "",
        "lighting": "even clinical lighting",
    },
    "SCIENTIFIC_CHEMISTRY": {
        "prefix": "chemistry illustration, ",
        "quality_boost": "molecular visualization, 3D molecule render, chemical structure, crystallography, orbital diagram",
        "technical": "ball and stick model, space-filling model, electron cloud, bond angles, atomic radii, CPK coloring",
        "negative": "inaccurate, artistic, blurry, amateur, low quality, worst quality",
        "camera": "",
        "lighting": "clean studio lighting, no shadows",
    },
    "SCIENTIFIC_SPACE": {
        "prefix": "space illustration, astronomical, ",
        "quality_boost": "NASA quality, space photography style, cosmic, galaxy, nebula, stars, planetary, astronomical beauty",
        "technical": "Hubble telescope style, deep field, star formation, cosmic dust, electromagnetic spectrum colors, scientific accuracy",
        "negative": "cartoon, amateur, flat, unrealistic colors, blurry, low quality, worst quality",
        "camera": "space telescope, extreme long range",
        "lighting": "starlight, nebula glow, solar illumination",
    },

    # ============================================================
    # CYBERPUNK & SPECIAL EFFECTS
    # ============================================================
    "CYBERPUNK": {
        "prefix": "cyberpunk, ",
        "quality_boost": "neon-lit cyberpunk city, blade runner atmosphere, dystopian future, rain-slicked streets, holographic advertisements",
        "technical": "neon pink and cyan, chrome reflections, augmented reality overlays, megacorp buildings, flying vehicles, steam vents",
        "negative": "bright daylight, nature, medieval, cartoon, anime style, amateur, blurry, low quality, worst quality",
        "camera": "wide angle, low angle, street level",
        "lighting": "neon lights, rain reflections, holographic glow",
    },
    "CYBERPUNK_NEON": {
        "prefix": "neon art, ",
        "quality_boost": "vivid neon lights, glowing tubes, electric colors, night scene, neon sign, synthwave aesthetic, retrowave",
        "technical": "neon pink, electric blue, hot purple, chrome reflections, dark background, light trails, fluorescent glow",
        "negative": "daylight, natural, muted colors, cartoon, blurry, low quality, worst quality",
        "camera": "",
        "lighting": "neon tube lighting, colored gels, blacklight",
    },
    "CYBERPUNK_GLITCH": {
        "prefix": "glitch art, ",
        "quality_boost": "digital glitch aesthetic, data corruption, pixel sorting, chromatic aberration, VHS artifacts, broken display",
        "technical": "RGB color separation, scan lines, noise, distortion, databending, corrupted data, matrix code, digital decay",
        "negative": "clean, perfect, natural, traditional art, boring, worst quality",
        "camera": "",
        "lighting": "screen glow, digital artifacts lighting",
    },
    "CYBERPUNK_VAPORWAVE": {
        "prefix": "vaporwave aesthetic, ",
        "quality_boost": "retro-futuristic, 80s/90s nostalgia, pastel pink and cyan, Roman busts, palm trees, sunset grid, lo-fi",
        "technical": "gradient sky, geometric shapes, retro computer graphics, VHS grain, japanese text, marble statues, pixel sunset",
        "negative": "modern, realistic, dark, horror, blurry, worst quality",
        "camera": "",
        "lighting": "sunset gradient, pastel neon, soft glow",
    },
    "CYBERPUNK_STEAMPUNK": {
        "prefix": "steampunk, ",
        "quality_boost": "Victorian steampunk, brass gears, clockwork mechanism, steam-powered, copper pipes, vintage technology, goggles",
        "technical": "intricate mechanical detail, brass and copper, steam vents, ornate Victorian design, leather straps, aged patina",
        "negative": "modern, digital, futuristic, plastic, cartoon, anime, blurry, low quality, worst quality",
        "camera": "",
        "lighting": "warm gaslight, candle glow, amber tones",
    },
    "CYBERPUNK_HOLOGRAPHIC": {
        "prefix": "holographic art, ",
        "quality_boost": "iridescent holographic, rainbow reflections, prismatic, futuristic, chrome, liquid metal, ethereal technology",
        "technical": "holographic foil effect, prismatic light, rainbow spectrum, reflective surface, translucent layers, futuristic UI",
        "negative": "matte, flat, boring, traditional, cartoon, blurry, low quality, worst quality",
        "camera": "",
        "lighting": "holographic light dispersion, prismatic rainbow",
    },

    # ============================================================
    # VINTAGE & RETRO
    # ============================================================
    "VINTAGE": {
        "prefix": "vintage photograph, ",
        "quality_boost": "retro aesthetic, nostalgic, old-fashioned, timeless, classic, aged, historical charm",
        "technical": "film grain, faded colors, warm tones, vignette, light leaks, aged paper texture, sepia undertones",
        "negative": "modern, digital, sharp, clean, futuristic, cartoon, anime, worst quality",
        "camera": "vintage camera, manual focus, film",
        "lighting": "natural available light, warm golden",
    },
    "VINTAGE_POLAROID": {
        "prefix": "polaroid photo, ",
        "quality_boost": "instant camera photo, polaroid frame, washed out colors, nostalgic moment, casual snapshot, retro Polaroid",
        "technical": "square format, white border frame, slightly overexposed, warm color shift, soft focus, casual framing, light leak",
        "negative": "sharp, digital, modern, professional, HDR, cartoon, anime, worst quality",
        "camera": "Polaroid camera, instant film",
        "lighting": "flash pop, daylight, candid lighting",
    },
    "VINTAGE_FILM": {
        "prefix": "35mm film photograph, ",
        "quality_boost": "shot on Kodak Portra 400, analog film, natural film grain, warm tones, nostalgic, golden hour, film photography",
        "technical": "Kodak color science, halation, soft highlights, natural skin tones, gentle contrast, light leaks possible",
        "negative": "digital, sharp, clinical, HDR, cartoon, anime, worst quality",
        "camera": "35mm SLR, manual lens, Kodak film",
        "lighting": "natural golden hour, warm ambient light",
    },

    # ============================================================
    # GEOMETRIC & PATTERN
    # ============================================================
    "GEOMETRIC": {
        "prefix": "geometric art, ",
        "quality_boost": "precise geometric design, mathematical beauty, symmetrical, clean lines, modern geometric art, satisfying pattern",
        "technical": "perfect symmetry, mathematical precision, color theory, repetition, tessellation, golden ratio, clean edges",
        "negative": "organic, messy, irregular, blurry, amateur, low quality, ugly, worst quality",
        "camera": "",
        "lighting": "flat even lighting for geometric clarity",
    },
    "GEOMETRIC_FRACTAL": {
        "prefix": "fractal art, ",
        "quality_boost": "mathematical fractal, infinite detail, self-similar patterns, Mandelbrot set, Julia set, recursive beauty",
        "technical": "vivid colors, infinite zoom, complex mathematics, recursive patterns, psychedelic, ultra detailed at every scale",
        "negative": "simple, flat, boring, blurry, low quality, ugly, worst quality",
        "camera": "",
        "lighting": "self-illuminating, glowing, radiant colors",
    },
    "GEOMETRIC_MANDALA": {
        "prefix": "mandala design, ",
        "quality_boost": "intricate mandala, sacred geometry, symmetrical, meditative, spiritual, detailed ornamental pattern",
        "technical": "perfect radial symmetry, fine details, gold and jewel tones, lotus petals, concentric circles, zen quality",
        "negative": "asymmetric, messy, simple, blurry, amateur, low quality, ugly, worst quality",
        "camera": "",
        "lighting": "even lighting, golden accents",
    },
    "GEOMETRIC_SACRED": {
        "prefix": "sacred geometry, ",
        "quality_boost": "flower of life, Metatron's cube, golden ratio, Fibonacci spiral, Platonic solids, cosmic geometry",
        "technical": "precise geometric construction, golden tones, cosmic background, spiritual symbolism, mathematical perfection",
        "negative": "organic, messy, inaccurate, blurry, amateur, low quality, worst quality",
        "camera": "",
        "lighting": "ethereal golden light, cosmic glow",
    },

    # ============================================================
    # GAME & FANTASY CONTENT
    # ============================================================
    "GAME_CHARACTER": {
        "prefix": "game character design, ",
        "quality_boost": "AAA game character, detailed armor, RPG hero, character concept art, game-ready design, epic warrior",
        "technical": "front view, detailed equipment, material texture, character sheet potential, stylized realism, weapon detail",
        "negative": "amateur, ugly, bad anatomy, disproportionate, blurry, low quality, worst quality",
        "camera": "full body, slight low angle for heroic feel",
        "lighting": "dramatic rim light, colored accent lighting",
    },
    "GAME_ENVIRONMENT": {
        "prefix": "game environment art, ",
        "quality_boost": "AAA game level design, explorable environment, atmospheric, game world, immersive setting, environmental storytelling",
        "technical": "environmental detail, vegetation, weather effects, mood lighting, level design principles, points of interest",
        "negative": "flat, empty, boring, amateur, low quality, blurry, ugly, worst quality",
        "camera": "third-person game camera perspective",
        "lighting": "atmospheric game lighting, volumetric fog",
    },
    "GAME_CREATURE": {
        "prefix": "creature design, monster concept art, ",
        "quality_boost": "terrifying creature design, detailed anatomy, fantasy monster, beast, unique design, professional concept",
        "technical": "believable anatomy, texture detail, scale reference, multiple views potential, creature silhouette, threat display",
        "negative": "cute, friendly, cartoon, amateur, blurry, ugly, low quality, worst quality",
        "camera": "dynamic angle, slight low angle",
        "lighting": "dramatic backlighting, atmospheric fog",
    },

    # ============================================================
    # CREATIVE & SURREAL
    # ============================================================
    "CREATIVE": {
        "prefix": "creative art, ",
        "quality_boost": "artistic, creative composition, unique perspective, imaginative, award winning, expressive, thought-provoking",
        "technical": "original concept, unusual angle, metaphorical imagery, conceptual art, gallery quality, conversation piece",
        "negative": "boring, generic, unoriginal, poorly executed, messy, amateur, low quality, worst quality",
        "camera": "",
        "lighting": "creative artistic lighting",
    },
    "CREATIVE_SURREAL": {
        "prefix": "surrealist art, ",
        "quality_boost": "Salvador Dali inspired, dreamlike, impossible architecture, melting reality, surreal landscape, mind-bending",
        "technical": "impossible physics, dreamscape, floating objects, unexpected scale, juxtaposition, hyper-real details in surreal context",
        "negative": "normal, boring, realistic, plain, amateur, low quality, ugly, worst quality",
        "camera": "",
        "lighting": "dreamlike lighting, multiple light sources, impossible shadows",
    },
    "CREATIVE_ABSTRACT": {
        "prefix": "abstract art, ",
        "quality_boost": "bold abstract composition, color field, gestural marks, modern art museum quality, expressive, dynamic",
        "technical": "color theory, composition balance, texture variety, layered paint, drips, splashes, emotional expression",
        "negative": "realistic, figurative, photo, boring, amateur, low quality, worst quality",
        "camera": "",
        "lighting": "gallery lighting",
    },
    "CREATIVE_MINIMALIST": {
        "prefix": "minimalist art, ",
        "quality_boost": "clean minimalist design, negative space, simple forms, elegant simplicity, modern aesthetic, less is more",
        "technical": "single focal point, vast empty space, subtle color palette, precise geometry, intentional simplicity, zen aesthetic",
        "negative": "cluttered, busy, complex, detailed, messy, ugly, low quality, worst quality",
        "camera": "",
        "lighting": "soft even lighting, minimal shadows",
    },
    "CREATIVE_POP_ART": {
        "prefix": "pop art, ",
        "quality_boost": "Andy Warhol style, bold colors, halftone dots, comic style, Roy Lichtenstein, Ben-Day dots, iconic",
        "technical": "flat bold colors, thick outlines, screen print aesthetic, repetition, commercial art, bright primary colors",
        "negative": "realistic, subtle, muted, dark, blurry, low quality, worst quality",
        "camera": "",
        "lighting": "flat even lighting, no shadows",
    },

    # ============================================================
    # FOOD PHOTOGRAPHY
    # ============================================================
    "FOOD": {
        "prefix": "food photography, ",
        "quality_boost": "appetizing, gourmet presentation, food styling, fresh ingredients, mouth-watering, Michelin star quality",
        "technical": "shallow depth of field, steam rising, fresh garnish, rustic props, warm tones, food magazine quality",
        "negative": "unappetizing, cold food, messy, blurry, dark, amateur, artificial looking, low quality, worst quality",
        "camera": "90mm macro, f/2.8, overhead or 45-degree",
        "lighting": "natural window light, backlit, warm tones",
    },
    "FOOD_GOURMET": {
        "prefix": "fine dining food photography, ",
        "quality_boost": "Michelin star presentation, chef's table, artistic plating, haute cuisine, gastronomic art, food art",
        "technical": "negative space on plate, sauce drizzle, microgreens, tweezered garnish, smoke/steam, dark moody background",
        "negative": "messy, amateur plating, fast food, blurry, low quality, ugly, worst quality",
        "camera": "close-up, slightly above, macro detail",
        "lighting": "dramatic side lighting, dark background, highlight on food",
    },

    # ============================================================
    # IMPRESSIONISM & CLASSICAL ART STYLES
    # ============================================================
    "ART_IMPRESSIONISM": {
        "prefix": "impressionist painting, ",
        "quality_boost": "Claude Monet style, light and color study, visible brushstrokes, plein air, atmospheric, garden scene",
        "technical": "broken color technique, optical mixing, natural light effects, soft edges, pastel palette, outdoor scene",
        "negative": "photo, realistic, sharp, digital, dark, cartoon, anime, low quality, worst quality",
        "camera": "",
        "lighting": "natural daylight, dappled sunlight, golden hour",
    },
    "ART_RENAISSANCE": {
        "prefix": "Renaissance painting, ",
        "quality_boost": "Old Master painting, Leonardo da Vinci technique, classical composition, sfumato, museum masterpiece",
        "technical": "oil on panel, classical proportions, golden ratio, sfumato technique, religious or mythological theme, chiaroscuro",
        "negative": "modern, digital, cartoon, anime, photo, blurry, amateur, low quality, worst quality",
        "camera": "",
        "lighting": "Rembrandt lighting, warm golden light, dramatic shadows",
    },
    "ART_CUBISM": {
        "prefix": "cubist art, ",
        "quality_boost": "Pablo Picasso style, fragmented forms, multiple viewpoints, geometric deconstruction, analytical cubism",
        "technical": "overlapping planes, muted earth tones, deconstructed form, multiple perspectives simultaneously, collage elements",
        "negative": "realistic, photo, smooth, blurry, low quality, worst quality",
        "camera": "",
        "lighting": "flat lighting, no single light source",
    },
}


# ============================================================
# TEMPLATE LOOKUP FUNCTIONS
# ============================================================

def get_template(mode: str, sub_mode: Optional[str] = None) -> Dict[str, str]:
    """
    Get the best template for a mode/sub-mode combination.

    Lookup order:
    1. "{MODE}_{SUB_MODE}" (e.g., "REALISM_PORTRAIT")
    2. "{MODE}" (e.g., "REALISM")
    3. Default REALISM template

    Args:
        mode: Master mode (e.g., "REALISM", "CINEMATIC", "ART")
        sub_mode: Sub-mode (e.g., "portrait", "noir", "oil_painting")

    Returns:
        Template dict with prefix, quality_boost, technical, negative, camera, lighting
    """
    # Try specific sub-mode first
    if sub_mode:
        key = f"{mode}_{sub_mode}".upper()
        if key in MEGA_TEMPLATES:
            return MEGA_TEMPLATES[key]

    # Try master mode
    if mode.upper() in MEGA_TEMPLATES:
        return MEGA_TEMPLATES[mode.upper()]

    # Default fallback
    return MEGA_TEMPLATES["REALISM"]


def get_all_modes() -> list:
    """Get all available template keys"""
    return sorted(MEGA_TEMPLATES.keys())


def get_master_modes() -> list:
    """Get only master mode names (no sub-modes)"""
    master_modes = set()
    for key in MEGA_TEMPLATES:
        parts = key.split("_", 1)
        master_modes.add(parts[0])
    return sorted(master_modes)


def build_enhanced_prompt(
    user_prompt: str,
    template: Dict[str, str],
    quality: str = "STANDARD"
) -> str:
    """
    Build the final enhanced prompt using a template.

    Args:
        user_prompt: Original user prompt
        template: Template dict from get_template()
        quality: FAST, STANDARD, or PREMIUM

    Returns:
        Fully enhanced prompt string
    """
    parts = []

    # Add prefix
    prefix = template.get("prefix", "")
    if prefix:
        parts.append(prefix)

    # Add user prompt
    parts.append(user_prompt.strip())

    # Add quality boost (always)
    qb = template.get("quality_boost", "")
    if qb:
        parts.append(qb)

    # Add technical details for STANDARD and PREMIUM
    if quality in ("STANDARD", "PREMIUM"):
        tech = template.get("technical", "")
        if tech:
            parts.append(tech)

    # Add camera for PREMIUM
    if quality == "PREMIUM":
        cam = template.get("camera", "")
        if cam:
            parts.append(cam)
        lit = template.get("lighting", "")
        if lit:
            parts.append(lit)

    return ", ".join(filter(None, parts))


def get_negative_prompt(template: Dict[str, str]) -> str:
    """Get negative prompt from template"""
    return template.get("negative", "low quality, blurry, ugly, deformed, worst quality")
