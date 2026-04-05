/**
 * canvas-bridge.ts — DesignBrief JSON → Fabric.js canvas objects
 *
 * This module converts a DesignBrief (from the backend agent chain) into
 * a set of Fabric.js objects that can be loaded onto the canvas editor.
 *
 * Usage:
 *   import { briefToFabricObjects, FabricLayerSpec } from '@/lib/canvas-bridge'
 *   const layers = briefToFabricObjects(designBrief, canvasWidth, canvasHeight)
 *   layers.forEach(spec => addLayerToCanvas(canvas, spec))
 */

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DesignBriefElement {
  id: string
  type: 'text' | 'image' | 'shape' | 'group'
  content: string
  bounds: { x: number; y: number; w: number; h: number }  // normalized 0-1
  style: {
    font_family?: string
    font_size_vw?: number
    font_weight?: string
    color?: string
    bg_color?: string
    border_radius?: number
    opacity?: number
    z_index?: number
    text_align?: string
    padding?: number
    shadow?: string
    letter_spacing?: string
    line_height?: number
    text_transform?: string
  }
  locked?: boolean
  editable?: boolean
  visible?: boolean
  features?: Array<{ icon: string; title: string; desc: string }>
  accent_color?: string
}

export interface DesignBrief {
  brief_id?: string
  triage?: { creative_type: string; platform: string; goal: string }
  brand?: {
    primary_color: string
    secondary_color: string
    accent_color: string
    bg_color: string
    text_primary: string
    text_secondary: string
    font_personality: string
    brand_name: string
    tone: string
  }
  creative?: {
    layout_archetype: string
    mood: string
    atmosphere: string
    visual_style: string
  }
  copy?: {
    headline: string
    subheadline: string
    body: string
    cta_text: string
    tagline: string
    brand_name: string
    features: Array<{ icon: string; title: string; desc: string }>
  }
  layout?: {
    elements: DesignBriefElement[]
    canvas_width: number
    canvas_height: number
    font_min_vw: number
    safe_zones: { top: number; bottom: number; left: number; right: number }
  }
  image_prompt?: { prompt: string; model_hint: string }
  meta?: { confidence: number; warnings: string[] }
  // Legacy fields from old Gemini brief
  ad_copy?: {
    headline?: string; subheadline?: string; body?: string
    cta?: string; cta_url?: string; tagline?: string; brand_name?: string
    features?: Array<{ icon: string; title: string; desc: string }>
  }
  poster_design?: {
    accent_color?: string; bg_color?: string; font_style?: string
    text_color_primary?: string; text_color_secondary?: string
    layout?: string; hero_occupies?: string
    has_feature_grid?: boolean; has_cta_button?: boolean
  }
  hero_url?: string
}

export interface FabricLayerSpec {
  id: string
  fabricType: 'image' | 'textbox' | 'rect' | 'group'
  // Pixel bounds on canvas
  left: number
  top: number
  width: number
  height: number
  // Fabric-specific props
  text?: string
  fontFamily?: string
  fontSize?: number
  fontWeight?: string
  fill?: string
  backgroundColor?: string
  textAlign?: string
  charSpacing?: number
  lineHeight?: number
  textTransform?: string  // stored as custom prop — applied on render
  rx?: number  // border radius
  ry?: number
  opacity?: number
  selectable?: boolean
  lockMovementX?: boolean
  lockMovementY?: boolean
  lockScalingX?: boolean
  lockScalingY?: boolean
  shadow?: string
  zIndex: number
  // Custom metadata
  _meta: {
    elementId: string
    elementType: string
    editable: boolean
    locked: boolean
    isHeroImage: boolean
    content: string
    features?: Array<{ icon: string; title: string; desc: string }>
    accentColor?: string
    bgColor?: string
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function parseShadow(shadowStr: string | undefined): string | undefined {
  if (!shadowStr || shadowStr === 'none') return undefined
  // CSS shadow "0 2px 20px rgba(0,0,0,0.5)" → Fabric shadow string
  return shadowStr
}

function vwToPx(vw: number, canvasWidth: number): number {
  return Math.round((vw / 100) * canvasWidth)
}

function boundsToPixels(
  bounds: { x: number; y: number; w: number; h: number },
  canvasWidth: number,
  canvasHeight: number,
): { left: number; top: number; width: number; height: number } {
  return {
    left:   Math.round(bounds.x * canvasWidth),
    top:    Math.round(bounds.y * canvasHeight),
    width:  Math.round(bounds.w * canvasWidth),
    height: Math.round(bounds.h * canvasHeight),
  }
}

function hexToRgba(hex: string, alpha: number = 1): string {
  if (hex.startsWith('rgba') || hex.startsWith('rgb')) return hex
  const clean = hex.replace('#', '')
  if (clean.length === 6) {
    const r = parseInt(clean.slice(0, 2), 16)
    const g = parseInt(clean.slice(2, 4), 16)
    const b = parseInt(clean.slice(4, 6), 16)
    return alpha < 1 ? `rgba(${r},${g},${b},${alpha})` : `rgb(${r},${g},${b})`
  }
  return hex
}

// ── Main converter ─────────────────────────────────────────────────────────────

/**
 * Convert a DesignBrief into Fabric.js layer specs.
 * Sorted by z_index so the caller can add them in the right order.
 */
export function briefToFabricObjects(
  brief: DesignBrief,
  canvasWidth: number,
  canvasHeight: number,
  heroImageSrc?: string,  // data URI or URL of the generated hero image
): FabricLayerSpec[] {
  const layers: FabricLayerSpec[] = []

  // Use layout.elements if from new agent chain, else build from legacy fields
  const elements: DesignBriefElement[] = brief.layout?.elements ?? buildLegacyElements(brief, canvasWidth, canvasHeight)

  for (const el of elements) {
    const px = boundsToPixels(el.bounds, canvasWidth, canvasHeight)
    const style = el.style || {}
    const zIndex = style.z_index ?? 10

    if (el.type === 'image' || el.id === 'hero_image') {
      layers.push({
        id:          el.id,
        fabricType:  'image',
        ...px,
        opacity:     style.opacity ?? 1,
        selectable:  false,
        lockMovementX: true,
        lockMovementY: true,
        lockScalingX:  false,
        lockScalingY:  false,
        zIndex,
        _meta: {
          elementId:   el.id,
          elementType: 'image',
          editable:    false,
          locked:      true,
          isHeroImage: true,
          content:     heroImageSrc ?? el.content,
        },
      })
      continue
    }

    if (el.type === 'text') {
      const fontSizePx = el.style.font_size_vw
        ? vwToPx(el.style.font_size_vw, canvasWidth)
        : 48

      // charSpacing in Fabric = letter-spacing in 1/1000 em
      const lsStr  = (style.letter_spacing || '0em').replace('em', '')
      const lsEm   = parseFloat(lsStr) || 0
      const charSpacing = Math.round(lsEm * 1000)

      layers.push({
        id:          el.id,
        fabricType:  'textbox',
        ...px,
        text:        el.content || '',
        fontFamily:  style.font_family ?? 'Inter, sans-serif',
        fontSize:    fontSizePx,
        fontWeight:  style.font_weight ?? '700',
        fill:        style.color ?? '#FFFFFF',
        backgroundColor: style.bg_color === 'transparent' ? undefined : style.bg_color,
        textAlign:   (style.text_align ?? 'center') as any,
        charSpacing,
        lineHeight:  style.line_height ?? 1.2,
        textTransform: undefined,
        opacity:     style.opacity ?? 1,
        selectable:  el.editable !== false,
        shadow:      parseShadow(style.shadow),
        rx:          style.border_radius ?? 0,
        ry:          style.border_radius ?? 0,
        zIndex,
        _meta: {
          elementId:   el.id,
          elementType: 'text',
          editable:    el.editable !== false,
          locked:      el.locked ?? false,
          isHeroImage: false,
          content:     el.content,
        },
      })
      continue
    }

    if (el.type === 'shape') {
      // CTA button or bg panel or overlay
      const bgColor = style.bg_color ?? '#F59E0B'
      // Handle gradient strings (e.g. "linear-gradient(to top, #0F172AFF, #0F172A00)")
      const fabricFill = bgColor.startsWith('linear') ? parseGradientForFabric(bgColor) : bgColor

      layers.push({
        id:          el.id,
        fabricType:  'rect',
        ...px,
        fill:        fabricFill,
        opacity:     style.opacity ?? 1,
        rx:          style.border_radius ?? 0,
        ry:          style.border_radius ?? 0,
        selectable:  el.editable !== false,
        shadow:      parseShadow(style.shadow),
        zIndex,
        _meta: {
          elementId:   el.id,
          elementType: 'shape',
          editable:    el.editable !== false,
          locked:      el.locked ?? false,
          isHeroImage: false,
          content:     el.content,
        },
      })

      // For CTA button: add text on top
      if (el.id === 'cta_btn' && el.content) {
        const fontSizePx = el.style.font_size_vw
          ? vwToPx(el.style.font_size_vw, canvasWidth)
          : 32
        layers.push({
          id:         `${el.id}_text`,
          fabricType: 'textbox',
          left:       px.left + (style.padding ?? 0),
          top:        px.top + Math.round(px.height * 0.2),
          width:      px.width - (style.padding ?? 0) * 2,
          height:     Math.round(px.height * 0.6),
          text:       el.content,
          fontFamily: style.font_family ?? 'Montserrat, sans-serif',
          fontSize:   fontSizePx,
          fontWeight: '800',
          fill:       '#FFFFFF',
          textAlign:  'center',
          charSpacing: 50,
          lineHeight: 1.0,
          selectable: false,
          zIndex:     zIndex + 1,
          _meta: {
            elementId:   `${el.id}_text`,
            elementType: 'text',
            editable:    false,
            locked:      true,
            isHeroImage: false,
            content:     el.content,
          },
        })
      }
      continue
    }

    // feature_grid → rendered as a group spec (canvas editor handles rendering)
    if (el.id === 'feature_grid' && el.features) {
      layers.push({
        id:          el.id,
        fabricType:  'group',
        ...px,
        opacity:     1,
        selectable:  false,
        zIndex,
        _meta: {
          elementId:   el.id,
          elementType: 'group',
          editable:    false,
          locked:      false,
          isHeroImage: false,
          content:     '',
          features:    el.features,
          accentColor: el.accent_color,
          bgColor:     el.bg_color,
        },
      })
    }
  }

  // Sort by zIndex ascending
  return layers.sort((a, b) => a.zIndex - b.zIndex)
}

/**
 * Build legacy element list from old Gemini brief (poster_design + ad_copy).
 * Produces the same shape as briefToFabricObjects expects.
 */
function buildLegacyElements(
  brief: DesignBrief,
  canvasWidth: number,
  canvasHeight: number,
): DesignBriefElement[] {
  const pd = brief.poster_design || {}
  const ac = brief.ad_copy || {}
  const accent = pd.accent_color || '#F59E0B'
  const bgColor = pd.bg_color || '#0F172A'
  const textPrimary = pd.text_color_primary || '#FFFFFF'
  const textSecondary = pd.text_color_secondary || '#CBD5E1'

  const heroOccupies = pd.hero_occupies || 'top_60'
  const heroH = heroOccupies === 'top_60' ? 0.58
               : heroOccupies === 'top_55' ? 0.53
               : heroOccupies === 'top_40' ? 0.38
               : 0.58

  const elements: DesignBriefElement[] = [
    {
      id: 'hero_image', type: 'image', content: '__hero__',
      bounds: { x: 0, y: 0, w: 1, h: heroH },
      style: { z_index: 0, opacity: 1 },
      locked: true, editable: false,
    },
    {
      id: 'bg_panel', type: 'shape', content: '',
      bounds: { x: 0, y: heroH, w: 1, h: 1 - heroH },
      style: { z_index: 1, bg_color: bgColor, opacity: 0.97 },
      locked: false, editable: false,
    },
    {
      id: 'headline', type: 'text', content: ac.headline || 'HEADLINE',
      bounds: { x: 0.04, y: heroH + 0.01, w: 0.92, h: 0.10 },
      style: {
        z_index: 20, color: textPrimary, font_size_vw: 8.5, font_weight: '900',
        text_align: 'center', letter_spacing: '-0.02em', shadow: '0 2px 20px rgba(0,0,0,0.5)',
      },
      locked: false, editable: true,
    },
    {
      id: 'subheadline', type: 'text', content: ac.subheadline || '',
      bounds: { x: 0.04, y: heroH + 0.12, w: 0.92, h: 0.07 },
      style: {
        z_index: 20, color: textSecondary, font_size_vw: 4.0, font_weight: '500',
        text_align: 'center', letter_spacing: '0.01em',
      },
      locked: false, editable: true,
    },
    {
      id: 'cta_btn', type: 'shape', content: ac.cta || 'GET STARTED',
      bounds: { x: 0.10, y: heroH + 0.20, w: 0.80, h: 0.07 },
      style: {
        z_index: 30, bg_color: accent, border_radius: 50, opacity: 1,
        font_size_vw: 4.0, font_weight: '800', shadow: `0 4px 24px ${accent}66`,
      },
      locked: false, editable: true,
    },
  ]

  if (pd.has_feature_grid !== false && ac.features?.length) {
    elements.push({
      id: 'feature_grid', type: 'group', content: '',
      bounds: { x: 0.03, y: heroH + 0.28, w: 0.94, h: 0.14 },
      style: { z_index: 20 },
      locked: false, editable: false,
      features: ac.features,
      accent_color: accent,
      bg_color: bgColor,
    })
  }

  if (ac.tagline) {
    elements.push({
      id: 'tagline', type: 'text', content: ac.tagline,
      bounds: { x: 0.04, y: heroH + 0.43, w: 0.92, h: 0.05 },
      style: { z_index: 20, color: `${textSecondary}AA`, font_size_vw: 2.8, font_weight: '400', text_align: 'center' },
      locked: false, editable: true,
    })
  }

  return elements
}

function parseGradientForFabric(gradient: string): string {
  // Fabric can't handle CSS gradients — use the solid end color as fallback
  const colorMatch = gradient.match(/#[0-9A-Fa-f]{6}/)
  return colorMatch ? colorMatch[0] : '#0F172A'
}

/**
 * Serialize canvas layers back to a DesignBrief-compatible format.
 * Called before saving to DB (PosterProject.canvasState).
 */
export function fabricObjectsToCanvasState(fabricJson: object): object {
  // Fabric's canvas.toJSON() is the canonical state — just pass through
  return fabricJson
}

/**
 * Check if a DesignBrief is from the new agent chain or legacy Gemini engine.
 */
export function isBriefFromAgentChain(brief: DesignBrief): boolean {
  return !!(brief.layout?.elements?.length && brief.brand)
}

/**
 * Get the display name for a layer element.
 */
export function getLayerDisplayName(elementId: string): string {
  const names: Record<string, string> = {
    hero_image:    '🖼️ Hero Image',
    bg_panel:      '▬ Background Panel',
    overlay:       '◻ Overlay',
    gradient_bar:  '▽ Gradient Bar',
    left_panel:    '◧ Left Panel',
    headline:      'Aa Headline',
    subheadline:   'Aa Subheadline',
    body:          'Aa Body Text',
    cta_btn:       '▶ CTA Button',
    cta_btn_text:  'Aa CTA Text',
    feature_grid:  '⊞ Feature Grid',
    tagline:       'Aa Tagline',
    logo:          '◎ Logo',
    badge:         '⬡ Badge',
  }
  return names[elementId] ?? elementId
}