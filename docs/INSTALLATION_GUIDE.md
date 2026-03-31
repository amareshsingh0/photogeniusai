# 📦 Installation Guide - PhotoGenius AI

## 🐍 Python Dependencies (sentencepiece)

### ❌ DON'T Install in Root

**Wrong:**
```powershell
# Root directory - DON'T DO THIS
cd "C:\desktop\PhotoGenius AI"
pip install sentencepiece
```

### ✅ DO Install in API Service Directory

**Correct:**
```powershell
# Navigate to API service
cd "C:\desktop\PhotoGenius AI\apps\api"

# Option 1: If using virtual environment
python -m venv .venv
.venv\Scripts\activate
pip install sentencepiece

# Option 2: Install all requirements (recommended)
pip install -r requirements.txt
```

**Why?**
- Python dependencies belong to the API service
- `requirements.txt` is in `apps/api/`
- Root directory is for Node.js/pnpm, not Python

---

## 📦 Node.js Dependencies (pnpm install)

### Issue: pnpm install Taking Too Long

If `pnpm install` is hanging or taking too long:

#### Solution 1: Cancel and Retry with Clean Install

```powershell
# Cancel current install (Ctrl+C)

# Clean install
cd "C:\desktop\PhotoGenius AI"
Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
Remove-Item -Force pnpm-lock.yaml -ErrorAction SilentlyContinue

# Retry
pnpm install
```

#### Solution 2: Install Only Essential Packages

```powershell
# Install only turbo (needed for dev script)
pnpm add -D turbo --save-exact

# Then try dev command
pnpm run dev
```

#### Solution 3: Use npm Instead (Temporary)

```powershell
# If pnpm is too slow, use npm temporarily
npm install
npm run dev
```

#### Solution 4: Check Network/Proxy

```powershell
# Check if behind proxy
$env:HTTP_PROXY
$env:HTTPS_PROXY

# If needed, configure pnpm registry
pnpm config set registry https://registry.npmjs.org/
```

---

## 🚀 Quick Start (Recommended)

### Step 1: Install Python Dependencies

```powershell
# Navigate to API
cd "C:\desktop\PhotoGenius AI\apps\api"

# Install all Python packages (includes sentencepiece)
pip install -r requirements.txt
```

### Step 2: Install Node.js Dependencies (If Needed)

```powershell
# Go to root
cd "C:\desktop\PhotoGenius AI"

# Quick install (only turbo)
pnpm add -D turbo --save-exact

# OR full install (if you have time)
pnpm install
```

### Step 3: Start Services

```powershell
# Option 1: Use run script (recommended)
.\scripts\run-all-services.ps1

# Option 2: Manual start
# Terminal 1: Web
pnpm --filter @photogenius/web dev

# Terminal 2: API
pnpm --filter @photogenius/api dev
```

---

## ✅ Verification

### Check Python Dependencies

```powershell
cd "C:\desktop\PhotoGenius AI\apps\api"
python -c "import sentencepiece; print('✅ sentencepiece installed')"
python -c "import transformers; print('✅ transformers installed')"
python -c "import insightface; print('✅ insightface installed')"
```

### Check Node.js Dependencies

```powershell
cd "C:\desktop\PhotoGenius AI"
Test-Path "node_modules\turbo\bin\turbo.js"
# Should return: True
```

---

## 🆘 Troubleshooting

### pnpm install Hanging?

1. **Check disk space**: `Get-PSDrive C`
2. **Check network**: `Test-NetConnection registry.npmjs.org -Port 443`
3. **Try different registry**: `pnpm config set registry https://registry.npmjs.org/`
4. **Clear cache**: `pnpm store prune`

### Python Package Not Found?

1. **Check virtual environment**: `python --version`
2. **Check installation location**: `pip show sentencepiece`
3. **Reinstall**: `pip install --force-reinstall sentencepiece`

---

## 📝 Summary

| Dependency | Location | Command |
|------------|----------|---------|
| **sentencepiece** | `apps/api/` | `cd apps/api && pip install -r requirements.txt` |
| **turbo** | Root | `pnpm add -D turbo` (or `pnpm install`) |
| **All Python** | `apps/api/` | `cd apps/api && pip install -r requirements.txt` |
| **All Node** | Root | `pnpm install` |

---

**Remember**: 
- ✅ Python packages → `apps/api/`
- ✅ Node packages → Root directory
- ❌ Don't mix them!
