# PhotoGenius Frontend (v2)

World-class production UI with advanced controls (P1).

## File

- **photogenius-ui-v2.jsx** – Standalone React component with:
  - **Quality tier slider**: STANDARD / PREMIUM / PERFECT
  - **Physics toggles**: Wetness, Lighting, Gravity
  - **Iteration count selector**: 1, 2, or 4 images
  - **Real-time progress** with optional preview image
  - **"Surprise Me" mode**: Boosts surprise/creativity (MAX_SURPRISE)

## Usage

- **In a React app**: `import PhotogeniusUIv2 from './frontend/photogenius-ui-v2.jsx'` and pass `onSubmit`, optional `progress`, `currentStep`, `previewImage`, `error`, `resultImages`, `disabled`.
- **In PhotoGenius Next.js app**: The same controls are integrated in `apps/web`: Generate page uses `QualityTierSlider`, `PhysicsToggles`, `IterationSelector`, and Surprise Me; progress shows a preview when the two-pass API returns one.

## Success metric

95%+ user satisfaction, &lt;1% confusion rate (clear labels, accessible controls).
