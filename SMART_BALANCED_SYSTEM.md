# 🎨 PhotoGenius AI - Smart Balanced System

**Perfect Balance**: User Control + AI Intelligence

**Date**: February 5, 2026
**Status**: 📋 Final Design

---

## 🎯 User Controls vs AI Decides

### 👤 User Controls (3 inputs)

1. **Prompt** (Required)
   - User describes what they want
   - Example: "sunset over mountains"

2. **Quality Tier** (User selects)
   - FAST - Quick preview (3-5 seconds)
   - STANDARD - Good quality (25 seconds)
   - PREMIUM - Best quality (50 seconds)

3. **Dimensions** (User chooses)
   - Default presets (1:1, 9:16, 16:9, etc.)
   - OR Custom (any height x width)

### 🤖 AI Decides (Automatic)

1. **Mode Detection**
   - AI analyzes prompt
   - Auto-selects: REALISM, CINEMATIC, CREATIVE, etc.

2. **Prompt Enhancement**
   - AI adds quality keywords
   - Optimizes for better results
   - User sees original + enhanced

3. **Technical Settings**
   - Steps, guidance scale, negative prompts
   - All optimized automatically

---

## 🎛️ User Interface Design

### Simple 3-Step Interface

```typescript
// apps/web/components/SmartGenerateForm.tsx

export function SmartGenerateForm() {
  const [prompt, setPrompt] = useState('')
  const [quality, setQuality] = useState('STANDARD')
  const [dimensions, setDimensions] = useState('default')
  const [customSize, setCustomSize] = useState({ width: 1024, height: 1024 })

  return (
    <div className="generate-form">
      {/* STEP 1: Prompt Input */}
      <div className="prompt-section">
        <label>What do you want to create?</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe your image... (e.g., sunset over mountains)"
          className="w-full h-32 p-4 text-lg border rounded-lg"
        />
      </div>

      {/* STEP 2: Quality Selection */}
      <div className="quality-section">
        <label>Select Quality</label>
        <div className="grid grid-cols-3 gap-4">
          <QualityCard
            name="FAST"
            time="3-5 seconds"
            description="Quick preview"
            selected={quality === 'FAST'}
            onClick={() => setQuality('FAST')}
          />
          <QualityCard
            name="STANDARD"
            time="~25 seconds"
            description="Good quality"
            selected={quality === 'STANDARD'}
            onClick={() => setQuality('STANDARD')}
            badge="Recommended"
          />
          <QualityCard
            name="PREMIUM"
            time="~50 seconds"
            description="Best quality"
            selected={quality === 'PREMIUM'}
            onClick={() => setQuality('PREMIUM')}
          />
        </div>
      </div>

      {/* STEP 3: Dimensions */}
      <div className="dimensions-section">
        <label>Image Size</label>

        {/* Preset options */}
        <div className="preset-options grid grid-cols-4 gap-2 mb-4">
          <PresetButton
            name="Square"
            ratio="1:1"
            icon="⬜"
            dimensions={{ width: 1024, height: 1024 }}
            selected={dimensions === 'square'}
            onClick={() => setDimensions('square')}
          />
          <PresetButton
            name="Portrait"
            ratio="3:4"
            icon="📱"
            dimensions={{ width: 768, height: 1024 }}
            selected={dimensions === 'portrait'}
            onClick={() => setDimensions('portrait')}
          />
          <PresetButton
            name="Landscape"
            ratio="16:9"
            icon="🖼️"
            dimensions={{ width: 1920, height: 1080 }}
            selected={dimensions === 'landscape'}
            onClick={() => setDimensions('landscape')}
          />
          <PresetButton
            name="Story"
            ratio="9:16"
            icon="📲"
            dimensions={{ width: 1080, height: 1920 }}
            selected={dimensions === 'story'}
            onClick={() => setDimensions('story')}
          />
        </div>

        {/* Custom dimensions */}
        <div className="custom-dimensions">
          <label className="flex items-center gap-2 mb-2">
            <input
              type="checkbox"
              checked={dimensions === 'custom'}
              onChange={(e) => setDimensions(e.target.checked ? 'custom' : 'default')}
            />
            <span>Custom Dimensions</span>
          </label>

          {dimensions === 'custom' && (
            <div className="flex gap-4 items-center">
              <div>
                <label className="text-sm text-gray-500">Width (px)</label>
                <input
                  type="number"
                  value={customSize.width}
                  onChange={(e) => setCustomSize({...customSize, width: parseInt(e.target.value)})}
                  min="512"
                  max="2048"
                  step="8"
                  className="w-32 p-2 border rounded"
                />
              </div>
              <span className="text-2xl text-gray-400">×</span>
              <div>
                <label className="text-sm text-gray-500">Height (px)</label>
                <input
                  type="number"
                  value={customSize.height}
                  onChange={(e) => setCustomSize({...customSize, height: parseInt(e.target.value)})}
                  min="512"
                  max="2048"
                  step="8"
                  className="w-32 p-2 border rounded"
                />
              </div>
              <div className="text-sm text-gray-500">
                Aspect: {(customSize.width / customSize.height).toFixed(2)}:1
              </div>
            </div>
          )}
        </div>
      </div>

      {/* AI Preview (shows what AI detected) */}
      {prompt && (
        <div className="ai-preview bg-blue-50 p-4 rounded-lg border border-blue-200">
          <h3 className="font-semibold mb-2">🤖 AI Analysis</h3>
          <div className="space-y-1 text-sm">
            <div>
              <span className="text-gray-600">Detected Mode:</span>
              <span className="ml-2 font-semibold text-blue-600">
                {detectMode(prompt)}
              </span>
            </div>
            <div>
              <span className="text-gray-600">Category:</span>
              <span className="ml-2 font-semibold">
                {detectCategory(prompt)}
              </span>
            </div>
            <div className="mt-2">
              <details>
                <summary className="cursor-pointer text-gray-600">
                  Enhanced Prompt (AI-generated)
                </summary>
                <p className="mt-2 text-gray-700 bg-white p-2 rounded">
                  {enhancePrompt(prompt)}
                </p>
              </details>
            </div>
          </div>
        </div>
      )}

      {/* Generate Button */}
      <Button
        onClick={handleGenerate}
        disabled={!prompt}
        className="w-full h-14 text-lg font-semibold bg-gradient-to-r from-purple-500 to-pink-500"
      >
        Generate Image
      </Button>

      {/* Generation Progress */}
      {isGenerating && (
        <GenerationProgress
          quality={quality}
          stages={getStagesForQuality(quality)}
        />
      )}
    </div>
  )
}

// Quality Card Component
function QualityCard({ name, time, description, selected, onClick, badge }) {
  return (
    <div
      onClick={onClick}
      className={`
        relative p-4 border-2 rounded-lg cursor-pointer transition-all
        ${selected
          ? 'border-purple-500 bg-purple-50 shadow-lg'
          : 'border-gray-200 hover:border-purple-300'
        }
      `}
    >
      {badge && (
        <span className="absolute -top-2 -right-2 bg-green-500 text-white text-xs px-2 py-1 rounded-full">
          {badge}
        </span>
      )}
      <h3 className="font-bold text-lg mb-1">{name}</h3>
      <p className="text-sm text-gray-600">{time}</p>
      <p className="text-xs text-gray-500 mt-1">{description}</p>
    </div>
  )
}

// Preset Button Component
function PresetButton({ name, ratio, icon, dimensions, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`
        p-3 border-2 rounded-lg transition-all
        ${selected
          ? 'border-purple-500 bg-purple-50'
          : 'border-gray-200 hover:border-purple-300'
        }
      `}
    >
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-sm font-semibold">{name}</div>
      <div className="text-xs text-gray-500">{ratio}</div>
      <div className="text-xs text-gray-400 mt-1">
        {dimensions.width}×{dimensions.height}
      </div>
    </button>
  )
}
```

---

## 🚀 Quality Tier Breakdown

### FAST ⚡ (3-5 seconds)

**Engine**: SDXL-Turbo
**Steps**: 4
**Best for**: Quick previews, testing prompts

```json
{
  "quality": "FAST",
  "engine": "SDXL-Turbo",
  "steps": 4,
  "guidance_scale": 1.0,
  "time": "3-5 seconds",
  "use_cases": [
    "Quick preview",
    "Prompt testing",
    "Rough concept",
    "Iteration speed"
  ]
}
```

### STANDARD 📊 (25 seconds) - Recommended

**Engine**: SDXL-Base
**Steps**: 30
**Best for**: Most use cases, good balance

```json
{
  "quality": "STANDARD",
  "engine": "SDXL-Base-1.0",
  "steps": 30,
  "guidance_scale": 7.5,
  "time": "~25 seconds",
  "use_cases": [
    "Social media",
    "Personal projects",
    "General use",
    "Good quality"
  ]
}
```

### PREMIUM ⭐ (50 seconds)

**Engine**: SDXL-Base + Refiner
**Steps**: 30 (base) + 20 (refiner)
**Best for**: Professional work, commercial use

```json
{
  "quality": "PREMIUM",
  "engine": "SDXL-Base + Refiner",
  "steps": 50,
  "guidance_scale": 8.5,
  "quality_scoring": true,
  "best_of_n": 3,
  "time": "~50 seconds",
  "use_cases": [
    "Professional work",
    "Commercial projects",
    "Print quality",
    "Portfolio pieces"
  ]
}
```

---

## 📐 Dimension Presets

### Default Presets (Quick Select)

```javascript
const DIMENSION_PRESETS = {
  // Social Media
  square: {
    name: "Square",
    width: 1024,
    height: 1024,
    ratio: "1:1",
    icon: "⬜",
    description: "Instagram, Profile pics",
    useCase: "social_media"
  },

  portrait: {
    name: "Portrait",
    width: 768,
    height: 1024,
    ratio: "3:4",
    icon: "📱",
    description: "Portraits, vertical photos",
    useCase: "portrait"
  },

  story: {
    name: "Story",
    width: 1080,
    height: 1920,
    ratio: "9:16",
    icon: "📲",
    description: "Instagram/TikTok Stories",
    useCase: "story"
  },

  // Landscape & Wide
  landscape: {
    name: "Landscape",
    width: 1920,
    height: 1080,
    ratio: "16:9",
    icon: "🖼️",
    description: "Desktop wallpapers, videos",
    useCase: "landscape"
  },

  wide: {
    name: "Wide",
    width: 1920,
    height: 1080,
    ratio: "16:9",
    icon: "🖥️",
    description: "Presentations, screens",
    useCase: "wide"
  },

  // Special
  banner: {
    name: "Banner",
    width: 1920,
    height: 512,
    ratio: "15:4",
    icon: "🎪",
    description: "Web banners, headers",
    useCase: "banner"
  },

  poster: {
    name: "Poster",
    width: 768,
    height: 1366,
    ratio: "9:16",
    icon: "🎬",
    description: "Movie posters, prints",
    useCase: "poster"
  }
}
```

### Custom Dimensions

**Rules**:
- Minimum: 512px (width or height)
- Maximum: 2048px (width or height)
- Must be multiple of 8 (SDXL requirement)
- Any aspect ratio supported

**Examples**:
```javascript
// User can create:
{ width: 500, height: 700 }   // 500×700px
{ width: 1234, height: 890 }  // 1234×890px (will round to 1232×888)
{ width: 2000, height: 1500 } // 2000×1500px
```

**Validation**:
```javascript
function validateCustomDimensions(width, height) {
  // Clamp to valid range
  width = Math.max(512, Math.min(width, 2048))
  height = Math.max(512, Math.min(height, 2048))

  // Round to multiple of 8
  width = Math.round(width / 8) * 8
  height = Math.round(height / 8) * 8

  return { width, height }
}
```

---

## 🤖 AI Auto-Detection System

### Mode Detection (AI Decides)

```python
class ModeDetector:
    """AI automatically detects best mode from prompt"""

    MODES = {
        'REALISM': [
            'realistic', 'photorealistic', 'photo', 'portrait',
            'professional', 'headshot', 'real', 'natural'
        ],
        'CINEMATIC': [
            'cinematic', 'movie', 'film', 'dramatic', 'epic',
            'hollywood', 'scene', 'shot'
        ],
        'CREATIVE': [
            'artistic', 'creative', 'imaginative', 'surreal',
            'abstract', 'unique', 'experimental'
        ],
        'FANTASY': [
            'fantasy', 'magical', 'mythical', 'dragon', 'wizard',
            'fairy', 'enchanted', 'mystical'
        ],
        'ANIME': [
            'anime', 'manga', 'cartoon', 'animated', 'character',
            'kawaii', 'chibi'
        ]
    }

    def detect_mode(self, prompt: str) -> str:
        """
        Analyze prompt and auto-select best mode

        Returns: REALISM, CINEMATIC, CREATIVE, FANTASY, or ANIME
        """
        prompt_lower = prompt.lower()

        # Score each mode
        scores = {}
        for mode, keywords in self.MODES.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            scores[mode] = score

        # Get highest scoring mode
        best_mode = max(scores, key=scores.get)

        # If no keywords matched, default to REALISM
        if scores[best_mode] == 0:
            return 'REALISM'

        return best_mode
```

### Category Detection

```python
class CategoryDetector:
    """Detect image category for better prompting"""

    CATEGORIES = {
        'portrait': ['person', 'face', 'portrait', 'headshot', 'selfie'],
        'landscape': ['landscape', 'scenery', 'nature', 'outdoor', 'mountain'],
        'product': ['product', 'object', 'item', 'commercial', 'showcase'],
        'architecture': ['building', 'architecture', 'house', 'structure'],
        'food': ['food', 'meal', 'dish', 'cuisine', 'cooking'],
        'animal': ['animal', 'pet', 'dog', 'cat', 'wildlife'],
        'abstract': ['abstract', 'pattern', 'geometric', 'design']
    }

    def detect_category(self, prompt: str) -> str:
        """Detect image category"""
        prompt_lower = prompt.lower()

        for category, keywords in self.CATEGORIES.items():
            if any(kw in prompt_lower for kw in keywords):
                return category

        return 'general'
```

### Smart Prompt Enhancement

```python
class SmartPromptEnhancer:
    """AI enhances prompts based on mode and category"""

    def enhance(
        self,
        user_prompt: str,
        mode: str,
        category: str,
        quality: str
    ) -> dict:
        """
        Enhance user's prompt with quality keywords

        User sees: Original + Enhanced
        AI uses: Enhanced for generation
        """

        # Base enhancements by mode
        mode_enhancements = {
            'REALISM': 'professional photography, photorealistic, sharp focus, natural lighting',
            'CINEMATIC': 'cinematic lighting, film grain, dramatic, movie quality, volumetric lighting',
            'CREATIVE': 'artistic, creative composition, unique perspective, imaginative',
            'FANTASY': 'fantasy art, magical, ethereal lighting, enchanted, mystical atmosphere',
            'ANIME': 'anime style, manga aesthetic, vibrant colors, cell shading'
        }

        # Category-specific enhancements
        category_enhancements = {
            'portrait': 'professional portrait, shallow depth of field, bokeh background',
            'landscape': 'wide angle, golden hour, high dynamic range, dramatic sky',
            'product': 'product photography, studio lighting, clean background, commercial quality',
            'architecture': 'architectural photography, symmetrical, sharp details',
            'food': 'food photography, appetizing, macro details, natural lighting'
        }

        # Quality boosters
        quality_keywords = {
            'FAST': 'good quality',
            'STANDARD': 'high quality, detailed, 8k uhd',
            'PREMIUM': 'masterpiece, best quality, ultra detailed, 8k uhd, award winning'
        }

        # Build enhanced prompt
        enhanced = f"{user_prompt}, "
        enhanced += mode_enhancements.get(mode, '')
        enhanced += f", {category_enhancements.get(category, '')}"
        enhanced += f", {quality_keywords.get(quality, '')}"

        return {
            'original': user_prompt,
            'enhanced': enhanced,
            'mode': mode,
            'category': category,
            'quality': quality
        }
```

---

## 🎨 Backend API Implementation

### Main Generation Endpoint

```python
# apps/api/app/api/v2/endpoints/generate.py

from fastapi import APIRouter, BackgroundTasks
from app.services.smart import ModeDetector, CategoryDetector, SmartPromptEnhancer
from app.services.generation import GenerationService

router = APIRouter()

mode_detector = ModeDetector()
category_detector = CategoryDetector()
prompt_enhancer = SmartPromptEnhancer()
generation_service = GenerationService()

class GenerateRequest(BaseModel):
    prompt: str
    quality: str = 'STANDARD'  # FAST, STANDARD, PREMIUM
    dimensions: dict = {'preset': 'square'}  # or {'custom': {'width': 1024, 'height': 1024}}

@router.post("/generate")
async def generate_image(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    Smart Generation Endpoint

    User provides:
    - prompt (required)
    - quality (FAST/STANDARD/PREMIUM)
    - dimensions (preset or custom)

    AI decides:
    - Mode (REALISM, CINEMATIC, etc.)
    - Category (portrait, landscape, etc.)
    - Prompt enhancement
    - Technical settings
    """

    # Step 1: AI detects mode and category
    mode = mode_detector.detect_mode(request.prompt)
    category = category_detector.detect_category(request.prompt)

    print(f"🤖 AI detected: mode={mode}, category={category}")

    # Step 2: AI enhances prompt
    enhanced = prompt_enhancer.enhance(
        user_prompt=request.prompt,
        mode=mode,
        category=category,
        quality=request.quality
    )

    print(f"✨ Enhanced prompt: {enhanced['enhanced']}")

    # Step 3: Get dimensions
    if 'preset' in request.dimensions:
        dimensions = DIMENSION_PRESETS[request.dimensions['preset']]
        width, height = dimensions['width'], dimensions['height']
    else:
        custom = request.dimensions['custom']
        width, height = validate_custom_dimensions(custom['width'], custom['height'])

    print(f"📐 Dimensions: {width}x{height}")

    # Step 4: Generate based on quality tier
    if request.quality == 'FAST':
        # SDXL-Turbo (4 steps, ~3s)
        result = await generation_service.generate_fast(
            prompt=enhanced['enhanced'],
            width=width,
            height=height
        )

    elif request.quality == 'STANDARD':
        # SDXL-Base (30 steps, ~25s)
        result = await generation_service.generate_standard(
            prompt=enhanced['enhanced'],
            width=width,
            height=height,
            mode=mode
        )

    elif request.quality == 'PREMIUM':
        # SDXL-Base + Refiner (50 steps, ~50s)
        result = await generation_service.generate_premium(
            prompt=enhanced['enhanced'],
            width=width,
            height=height,
            mode=mode
        )

    return {
        'image_url': result.image_url,
        'metadata': {
            'original_prompt': request.prompt,
            'enhanced_prompt': enhanced['enhanced'],
            'mode': mode,
            'category': category,
            'quality': request.quality,
            'dimensions': f"{width}x{height}",
            'generation_time': result.generation_time,
            'ai_analysis': {
                'detected_mode': mode,
                'detected_category': category,
                'enhancements_applied': enhanced['enhanced']
            }
        }
    }

def validate_custom_dimensions(width: int, height: int) -> tuple:
    """Validate and fix custom dimensions"""
    # Clamp to valid range
    width = max(512, min(width, 2048))
    height = max(512, min(height, 2048))

    # Round to multiple of 8
    width = (width // 8) * 8
    height = (height // 8) * 8

    return width, height

DIMENSION_PRESETS = {
    'square': {'width': 1024, 'height': 1024},
    'portrait': {'width': 768, 'height': 1024},
    'landscape': {'width': 1920, 'height': 1080},
    'story': {'width': 1080, 'height': 1920},
    'banner': {'width': 1920, 'height': 512},
    'poster': {'width': 768, 'height': 1366}
}
```

---

## 🎯 User Flow Example

### Example 1: Simple Portrait

**User Input**:
```json
{
  "prompt": "professional headshot of a businessman",
  "quality": "STANDARD",
  "dimensions": { "preset": "portrait" }
}
```

**AI Processing**:
```python
# Step 1: Mode detection
mode = "REALISM"  # Detected from "professional headshot"

# Step 2: Category detection
category = "portrait"  # Detected from "headshot"

# Step 3: Prompt enhancement
enhanced = "professional headshot of a businessman, professional photography, photorealistic, sharp focus, natural lighting, professional portrait, shallow depth of field, bokeh background, high quality, detailed, 8k uhd"

# Step 4: Generation
result = generate_standard(
  prompt=enhanced,
  width=768,
  height=1024
)
```

**User Receives**:
```json
{
  "image_url": "https://...",
  "metadata": {
    "original_prompt": "professional headshot of a businessman",
    "enhanced_prompt": "professional headshot...(enhanced)",
    "mode": "REALISM",
    "category": "portrait",
    "quality": "STANDARD",
    "dimensions": "768x1024",
    "generation_time": 24.5
  }
}
```

### Example 2: Custom Dimensions

**User Input**:
```json
{
  "prompt": "sunset over mountains",
  "quality": "PREMIUM",
  "dimensions": {
    "custom": {
      "width": 1500,
      "height": 900
    }
  }
}
```

**AI Processing**:
```python
# Step 1: Mode detection
mode = "CINEMATIC"  # Detected from "sunset"

# Step 2: Validate dimensions
width = 1500 → 1496 (rounded to multiple of 8)
height = 900 → 896 (rounded to multiple of 8)

# Step 3: Generate with PREMIUM quality
result = generate_premium(
  prompt=enhanced,
  width=1496,
  height=896
)
```

---

## 📊 Summary Table

| Feature | User Controls | AI Decides |
|---------|---------------|------------|
| **Prompt** | ✅ User writes | ❌ |
| **Quality** | ✅ User selects (FAST/STANDARD/PREMIUM) | ❌ |
| **Dimensions** | ✅ User chooses (preset or custom) | ❌ |
| **Mode** | ❌ | ✅ AI detects (REALISM, CINEMATIC, etc.) |
| **Category** | ❌ | ✅ AI detects (portrait, landscape, etc.) |
| **Prompt Enhancement** | ❌ | ✅ AI adds quality keywords |
| **Technical Settings** | ❌ | ✅ AI optimizes (steps, guidance, etc.) |

---

## 🚀 Implementation Steps

### Phase 1: Core System (Week 1)

**Day 1-3**: Deploy SageMaker endpoints
- SDXL-Turbo (FAST)
- SDXL-Base (STANDARD)
- SDXL-Refiner (PREMIUM)

**Day 4-5**: Build AI detection
- Mode detector
- Category detector
- Prompt enhancer

**Day 6-7**: Build generation service
- Quality tier routing
- Dimension validation
- API integration

### Phase 2: Frontend (Week 2)

**Day 8-10**: Build UI components
- Quality selector cards
- Dimension presets
- Custom dimension input
- AI preview panel

**Day 11-12**: Integration
- Connect to API
- Real-time preview
- Progress tracking

**Day 13-14**: Testing & Polish
- End-to-end testing
- Bug fixes
- Performance optimization

---

**Status**: 📋 **Perfect Balanced System Ready!**

**User gets**: Full control over prompt, quality, and dimensions
**AI handles**: Mode detection, enhancements, technical optimization

**Ready to implement?** 🚀
