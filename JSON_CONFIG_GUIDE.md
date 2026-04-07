# 📁 JSON Configuration Files — Complete Guide

**Location:** `C:\desktop\PhotoGenius AI\apps\api\app\config\`

---

## 🎯 **Quick Answer: Where to Put JSON Files**

**RECOMMENDED PATH:**
```
C:\desktop\PhotoGenius AI\apps\api\app\config\
```

**Files to create:**
1. ✅ `beast_standards.json` — 10 Beast Standard gates (CREATED)
2. `aesthetic_codes.json` — 8 Aesthetic zeitgeist codes
3. `platform_contracts.json` — Platform-specific rules
4. `generational_signals.json` — Gen Z, Millennials, etc.
5. `composition_archetypes.json` — 7 composition types
6. `type_scales.json` — 5 type scale configs
7. `quality_dimensions.json` — 12 quality dimensions

---

## 📂 **Directory Structure Created**

```
apps/api/app/config/
├── __init__.py              ✅ Created (loader utilities)
├── README.md                ✅ Created (documentation)
├── beast_standards.json     ✅ Created (EXAMPLE)
├── aesthetic_codes.json     ⏳ You can create
├── platform_contracts.json  ⏳ You can create
└── ... (other configs)      ⏳ You can create
```

---

## 🔧 **How to Use JSON Configs in Python**

### **Method 1: Using Loader Functions (RECOMMENDED)**
```python
from app.config import load_beast_standards

# Load JSON config
beast_standards = load_beast_standards()

# Use it
for gate in beast_standards["gates"]:
    print(f"{gate['name']}: {gate['description']}")
```

### **Method 2: Direct JSON Import**
```python
import json
from pathlib import Path

config_file = Path(__file__).parent.parent / "config" / "beast_standards.json"
with open(config_file, 'r', encoding='utf-8') as f:
    standards = json.load(f)
```

### **Method 3: One-Time Load at Module Level**
```python
# At top of quality_critic.py
from app.config import load_beast_standards

BEAST_STANDARDS = load_beast_standards()

# Use everywhere in module
class QualityCritic:
    def __init__(self):
        self.gates = BEAST_STANDARDS["gates"]
```

---

## 📝 **Example: Migrating Hardcoded Config**

### **BEFORE (Hardcoded in Python):**
```python
# In cultural_intelligence.py (lines 26-100)
AESTHETIC_ZEITGEIST_2026 = {
    "ai_native": {
        "keywords": ["procedural patterns", "glitch aesthetic"],
        "trend_strength": 9.2,
        "when_to_use": "Tech, AI tools, digital-first brands",
        # ... 50 more lines
    },
    "quiet_luxury_loud": {
        # ... another 50 lines
    }
}
```

### **AFTER (JSON Config):**

**1. Create JSON file:**
`apps/api/app/config/aesthetic_codes.json`
```json
{
  "version": "2026-Q2",
  "aesthetics": {
    "ai_native": {
      "keywords": ["procedural patterns", "glitch aesthetic"],
      "trend_strength": 9.2,
      "when_to_use": "Tech, AI tools, digital-first brands"
    },
    "quiet_luxury_loud": {
      ...
    }
  }
}
```

**2. Update Python file:**
```python
# In cultural_intelligence.py
from app.config import load_aesthetic_codes

AESTHETIC_ZEITGEIST_2026 = load_aesthetic_codes()["aesthetics"]
```

**Benefits:**
- ✅ Update aesthetics without touching Python code
- ✅ Version control JSON separately
- ✅ Easier for non-programmers to update
- ✅ Can hot-reload in future

---

## 📋 **JSON File Templates**

### **Template 1: aesthetic_codes.json**
```json
{
  "version": "2026-Q2",
  "updated_at": "2026-04-07",
  "aesthetics": {
    "ai_native": {
      "trend_strength": 9.2,
      "keywords": ["procedural patterns", "generative textures", "glitch aesthetic"],
      "signal": "I understand the tools of the future",
      "when_to_use": "Tech, AI tools, crypto, digital-first brands",
      "avoid_with": "Traditional finance, healthcare, legacy brands",
      "color_palette": ["#00D4FF", "#FF00FF", "#00FF94", "#1A1A2E"],
      "typography": "Mono fonts, glitch effects, digital natives",
      "composition": "Grid-logic made visible, data-as-design"
    },
    "quiet_luxury_loud": {
      "trend_strength": 9.0,
      "keywords": ["understated until it isn't", "subtle flex", "stealth wealth"],
      "signal": "This doesn't need to explain itself",
      "when_to_use": "Premium fashion, luxury goods, high-end services",
      "avoid_with": "Mass market, youth brands",
      "color_palette": ["#F5F5DC", "#8B7355", "#2C2C2C", "#D4C5B9"],
      "typography": "Refined serifs, minimal sans, generous spacing",
      "composition": "White space as status signal"
    }
  }
}
```

### **Template 2: platform_contracts.json**
```json
{
  "version": "1.0",
  "platforms": {
    "instagram": {
      "text_max_pct": 20,
      "min_contrast_ratio": 4.5,
      "recommended_formats": ["portrait 4:5", "square 1:1"],
      "attention_window": "1.5s",
      "aesthetic": "editorial quality, color story, curated grids",
      "forbidden": ["low-res", "text-heavy", "pixelated"]
    },
    "tiktok": {
      "text_max_pct": 30,
      "min_contrast_ratio": 7.0,
      "recommended_formats": ["vertical 9:16"],
      "attention_window": "0.5s",
      "aesthetic": "text-forward, meme-fluent, raw edges",
      "forbidden": ["horizontal layouts", "small text", "corporate polish"]
    }
  }
}
```

### **Template 3: quality_dimensions.json**
```json
{
  "version": "1.0",
  "dimensions": {
    "composition": {
      "weight": 0.12,
      "criteria": "Rule of thirds, visual hierarchy, balance, negative space mastery",
      "min_threshold": 7.0
    },
    "color_authority": {
      "weight": 0.10,
      "criteria": "60-30-10 rule, palette sophistication, color psychology",
      "min_threshold": 7.0
    },
    "typography": {
      "weight": 0.10,
      "criteria": "Hierarchy clarity, readability, font pairing, scale",
      "min_threshold": 7.0
    },
    "scroll_stop_power": {
      "weight": 0.10,
      "criteria": "Attention capture in <1.5s, thumb-stopping quality",
      "min_threshold": 7.5
    }
  }
}
```

---

## 🚀 **Quick Start: Create Your JSON Files**

### **Step 1: Copy Existing Data**
Look at these Python files for data to extract:
- `cultural_intelligence.py` (lines 26-200) → `aesthetic_codes.json`
- `design_director.py` (lines 32-134) → `composition_archetypes.json` + `type_scales.json`
- `quality_critic.py` (lines 45-160) → `quality_dimensions.json`

### **Step 2: Create JSON Files**
```bash
cd "C:\desktop\PhotoGenius AI\apps\api\app\config"

# Create empty files
touch aesthetic_codes.json
touch platform_contracts.json
touch generational_signals.json
touch composition_archetypes.json
touch type_scales.json
touch quality_dimensions.json
```

### **Step 3: Copy Data from Python to JSON**
Example: Extract from `cultural_intelligence.py`:
```python
# BEFORE (in Python file)
AESTHETIC_ZEITGEIST_2026 = {
    "ai_native": {
        "keywords": ["..."],
        # ...
    }
}

# Copy this dict to aesthetic_codes.json
# Wrap in {"version": "2026-Q2", "aesthetics": {...}}
```

### **Step 4: Update Python Files to Load JSON**
```python
# Add import
from app.config import load_aesthetic_codes

# Replace hardcoded dict
AESTHETIC_ZEITGEIST_2026 = load_aesthetic_codes()["aesthetics"]
```

### **Step 5: Test**
```bash
cd apps/api
python -c "from app.config import load_aesthetic_codes; print('OK')"
```

---

## 🔧 **Modifying JSON Files**

### **Updating Aesthetic Codes (Quarterly)**
```bash
# 1. Open JSON file
code "C:\desktop\PhotoGenius AI\apps\api\app\config\aesthetic_codes.json"

# 2. Update version
"version": "2026-Q3",  # Q2 → Q3
"updated_at": "2026-07-01",

# 3. Add new aesthetic or update trend_strength
"aesthetics": {
  "ai_native": {
    "trend_strength": 9.5,  # Updated from 9.2
    ...
  },
  "new_aesthetic_code": {  # New entry
    "trend_strength": 8.0,
    ...
  }
}

# 4. Restart API
# Config auto-loads on startup
```

### **Tuning Quality Thresholds**
```bash
# 1. Open beast_standards.json
code "C:\desktop\PhotoGenius AI\apps\api\app\config\beast_standards.json"

# 2. Adjust gate thresholds
"gates": [
  {
    "id": "scroll_stop_test",
    "threshold": 8.0,  # Raised from 7.5
    ...
  }
]

# 3. Restart API
```

---

## 🎯 **Which Files Should You Create?**

### **Priority 1: MUST CREATE (Core Beast Mode)**
1. ✅ `beast_standards.json` — Already created (10 gates)
2. `quality_dimensions.json` — For Quality Critic
3. `aesthetic_codes.json` — For Cultural Intelligence

### **Priority 2: SHOULD CREATE (Enhanced Features)**
4. `platform_contracts.json` — For Design Director
5. `composition_archetypes.json` — For Design Director
6. `type_scales.json` — For Design Director

### **Priority 3: NICE TO HAVE (Future)**
7. `generational_signals.json` — For Cultural Intelligence

---

## ✅ **Validation**

### **Check JSON Syntax**
```bash
# Use Python to validate
python -c "import json; json.load(open('apps/api/app/config/beast_standards.json'))"
# No error = valid JSON
```

### **Check Loader Works**
```bash
cd apps/api
python -c "from app.config import load_beast_standards; print(load_beast_standards()['version'])"
# Should output: 1.0
```

---

## 📊 **Current vs Future State**

### **Current (After Our Implementation)**
```
Python files: 70% config hardcoded
JSON files: 30% config externalized
  ✅ beast_standards.json created
  ⏳ 6 more JSON files to create
```

### **Future (Full Migration)**
```
Python files: 10% config (complex logic only)
JSON files: 90% config externalized
  ✅ All 7 JSON files created
  ✅ Easy to update without code changes
  ✅ Version controlled
```

---

## 🎬 **NEXT ACTIONS**

### **Option 1: Use Existing Python Dicts (Quick)**
- ✅ Everything works as-is
- ❌ Harder to update (need to edit Python)

### **Option 2: Migrate to JSON (Recommended)**
1. Create remaining 6 JSON files
2. Copy data from Python to JSON
3. Update Python to load from JSON
4. Test thoroughly
5. Delete old hardcoded dicts

### **Option 3: Hybrid (Current State)**
- ✅ Use JSON for frequently updated data (aesthetics, platforms)
- ✅ Keep Python for complex logic (scoring algorithms, etc.)

---

## 📝 **Summary**

**Path:** `C:\desktop\PhotoGenius AI\apps\api\app\config\`

**Files Created Today:**
- ✅ `__init__.py` (loader utilities)
- ✅ `README.md` (documentation)
- ✅ `beast_standards.json` (example config)

**Files You Can Create:**
- `aesthetic_codes.json`
- `platform_contracts.json`
- `generational_signals.json`
- `composition_archetypes.json`
- `type_scales.json`
- `quality_dimensions.json`

**How to Use:**
```python
from app.config import load_beast_standards
config = load_beast_standards()
```

**YOU'RE ALL SET! 🚀**
