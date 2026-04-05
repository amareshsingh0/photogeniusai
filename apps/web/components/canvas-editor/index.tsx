'use client'

/**
 * CanvasEditor — Fabric.js powered design editor
 *
 * Layout:
 *   ┌──────────────────────────────────────────────┐
 *   │  Toolbar (top bar — align, undo/redo, export) │
 *   ├───────────┬──────────────────────┬────────────┤
 *   │ LayerPanel│   Canvas (center)    │ Properties │
 *   │ (left)    │                      │ Panel(right│
 *   └───────────┴──────────────────────┴────────────┘
 *
 * Props:
 *   designBrief   — from backend (agent chain or legacy Gemini)
 *   heroImageSrc  — generated image URL or data URI
 *   projectId     — PosterProject.id (null = unsaved)
 *   onSave        — called with { canvasState, thumbnail }
 *   onExport      — called with PNG blob
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { DesignBrief, FabricLayerSpec } from '@/lib/canvas-bridge'
import { briefToFabricObjects, getLayerDisplayName } from '@/lib/canvas-bridge'
import { LayerPanel } from './LayerPanel'
import { PropertiesPanel } from './PropertiesPanel'
import { EditorToolbar } from './Toolbar'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface CanvasEditorProps {
  designBrief: DesignBrief
  heroImageSrc: string
  projectId?: string | null
  canvasWidth?: number
  canvasHeight?: number
  onSave?: (state: { canvasJson: object; thumbnailDataUrl: string }) => void
  onExport?: (blob: Blob) => void
  className?: string
}

export interface LayerItem {
  id: string
  displayName: string
  visible: boolean
  locked: boolean
  selected: boolean
  fabricType: string
  zIndex: number
}

// ── Feature grid renderer (PIL-side does it, Fabric needs a placeholder) ──────

function renderFeatureGrid(
  canvas: any,  // fabric.Canvas
  spec: FabricLayerSpec,
): void {
  if (!spec._meta.features?.length) return
  const features = spec._meta.features
  const accent = spec._meta.accentColor ?? '#F59E0B'
  const bg = spec._meta.bgColor ?? '#0F172A'

  const colCount = Math.min(features.length, 2)
  const cellW = Math.floor(spec.width / colCount) - 8
  const cellH = Math.floor(spec.height / Math.ceil(features.length / colCount)) - 6

  features.forEach((feat, i) => {
    const col = i % colCount
    const row = Math.floor(i / colCount)
    const x = spec.left + col * (cellW + 8) + 4
    const y = spec.top + row * (cellH + 6) + 3

    // Card background
    const rect = new (window as any).fabric.Rect({
      left: x, top: y, width: cellW, height: cellH,
      fill: bg + 'CC', rx: 8, ry: 8,
      selectable: false, evented: false,
      opacity: 0.85,
      data: { groupId: spec.id },
    })
    canvas.add(rect)

    // Icon + title text
    const label = new (window as any).fabric.Textbox(`${feat.icon} ${feat.title}`, {
      left: x + 8, top: y + 6, width: cellW - 16,
      fontSize: Math.max(12, Math.floor(cellH * 0.28)),
      fontWeight: '700', fill: '#FFFFFF',
      fontFamily: 'Inter, sans-serif',
      selectable: false, evented: false,
      data: { groupId: spec.id },
    })
    canvas.add(label)

    // Description text
    const desc = new (window as any).fabric.Textbox(feat.desc, {
      left: x + 8, top: y + 6 + Math.floor(cellH * 0.36), width: cellW - 16,
      fontSize: Math.max(9, Math.floor(cellH * 0.20)),
      fontWeight: '400', fill: '#CBD5E1',
      fontFamily: 'Inter, sans-serif',
      selectable: false, evented: false,
      data: { groupId: spec.id },
    })
    canvas.add(desc)
  })
}

// ── Main component ─────────────────────────────────────────────────────────────

export function CanvasEditor({
  designBrief,
  heroImageSrc,
  projectId,
  canvasWidth = 1080,
  canvasHeight = 1080,
  onSave,
  onExport,
  className = '',
}: CanvasEditorProps) {
  const canvasRef  = useRef<HTMLCanvasElement>(null)
  const fabricRef  = useRef<any>(null)   // fabric.Canvas instance
  const historyRef = useRef<string[]>([])
  const histPosRef = useRef<number>(-1)

  const [ready, setReady]             = useState(false)
  const [loading, setLoading]         = useState(true)
  const [layers, setLayers]           = useState<LayerItem[]>([])
  const [selectedId, setSelectedId]   = useState<string | null>(null)
  const [selectedProps, setSelectedProps] = useState<any>(null)
  const [saving, setSaving]           = useState(false)
  const [aiLoading, setAiLoading]     = useState(false)

  // Responsive scale factor (editor preview at ~50-60% of actual canvas size)
  const PREVIEW_WIDTH = 520
  const scale = PREVIEW_WIDTH / canvasWidth

  // ── Init Fabric.js canvas ────────────────────────────────────────────────

  useEffect(() => {
    if (!canvasRef.current || fabricRef.current) return

    // Fabric.js is loaded via CDN script tag (see EditorPage)
    const checkFabric = () => {
      if (!(window as any).fabric) {
        setTimeout(checkFabric, 100)
        return
      }
      initCanvas()
    }
    checkFabric()

    return () => {
      if (fabricRef.current) {
        fabricRef.current.dispose()
        fabricRef.current = null
      }
    }
  }, [])

  const initCanvas = useCallback(async () => {
    const fabric = (window as any).fabric
    const canvas = new fabric.Canvas(canvasRef.current, {
      width:              canvasWidth * scale,
      height:             canvasHeight * scale,
      backgroundColor:    '#0F172A',
      selection:          true,
      preserveObjectStacking: true,
    })
    fabricRef.current = canvas

    // Selection events
    canvas.on('selection:created',  (e: any) => onObjectSelected(e.selected?.[0]))
    canvas.on('selection:updated',  (e: any) => onObjectSelected(e.selected?.[0]))
    canvas.on('selection:cleared',  ()        => { setSelectedId(null); setSelectedProps(null) })
    canvas.on('object:modified',    ()        => { saveHistory(); syncLayers() })
    canvas.on('object:added',       ()        => syncLayers())
    canvas.on('object:removed',     ()        => syncLayers())

    await loadDesignBrief(canvas)
    setReady(true)
    setLoading(false)
    saveHistory()
  }, [designBrief, heroImageSrc, canvasWidth, canvasHeight, scale])

  // ── Load DesignBrief layers ────────────────────────────────────────────────

  const loadDesignBrief = useCallback(async (canvas: any) => {
    const fabric = (window as any).fabric
    const specs: FabricLayerSpec[] = briefToFabricObjects(
      designBrief, canvasWidth, canvasHeight, heroImageSrc,
    )

    for (const spec of specs) {
      await addSpecToCanvas(canvas, fabric, spec)
    }

    canvas.renderAll()
    syncLayers()
  }, [designBrief, heroImageSrc, canvasWidth, canvasHeight])

  const addSpecToCanvas = async (canvas: any, fabric: any, spec: FabricLayerSpec): Promise<void> => {
    const scaledSpec = {
      ...spec,
      left:   spec.left * scale,
      top:    spec.top  * scale,
      width:  spec.width  * scale,
      height: spec.height * scale,
      fontSize: spec.fontSize ? spec.fontSize * scale : undefined,
    }

    if (spec.fabricType === 'image') {
      const src = spec._meta.content || heroImageSrc
      if (!src || src === '__hero_image__') return

      return new Promise<void>((resolve) => {
        fabric.Image.fromURL(src, (img: any) => {
          if (!img) { resolve(); return }
          img.set({
            left:       scaledSpec.left,
            top:        scaledSpec.top,
            scaleX:     scaledSpec.width  / img.width,
            scaleY:     scaledSpec.height / img.height,
            selectable: false,
            lockMovementX: true,
            lockMovementY: true,
            opacity:    spec.opacity ?? 1,
            data:       { ...spec._meta, elementId: spec.id },
          })
          canvas.add(img)
          canvas.sendToBack(img)
          resolve()
        }, { crossOrigin: 'anonymous' })
      })
    }

    if (spec.fabricType === 'textbox') {
      const obj = new fabric.Textbox(scaledSpec.text ?? '', {
        left:       scaledSpec.left,
        top:        scaledSpec.top,
        width:      scaledSpec.width,
        fontSize:   scaledSpec.fontSize ?? 48,
        fontFamily: spec.fontFamily ?? 'Inter, sans-serif',
        fontWeight: spec.fontWeight ?? '700',
        fill:       spec.fill ?? '#FFFFFF',
        textAlign:  spec.textAlign ?? 'center',
        charSpacing: spec.charSpacing ?? 0,
        lineHeight: spec.lineHeight ?? 1.2,
        opacity:    spec.opacity ?? 1,
        selectable: spec.selectable !== false,
        lockMovementX: spec._meta.locked ?? false,
        lockMovementY: spec._meta.locked ?? false,
        shadow:     spec.shadow,
        data:       { ...spec._meta, elementId: spec.id },
      })
      canvas.add(obj)
      return
    }

    if (spec.fabricType === 'rect') {
      const obj = new fabric.Rect({
        left:       scaledSpec.left,
        top:        scaledSpec.top,
        width:      scaledSpec.width,
        height:     scaledSpec.height,
        fill:       spec.fill ?? '#0F172A',
        rx:         (spec.rx ?? 0) * scale,
        ry:         (spec.ry ?? 0) * scale,
        opacity:    spec.opacity ?? 1,
        selectable: spec.selectable !== false,
        shadow:     spec.shadow,
        data:       { ...spec._meta, elementId: spec.id },
      })
      canvas.add(obj)

      // CTA button label
      if (spec.id === 'cta_btn' && spec._meta.content) {
        const btnText = new fabric.Textbox(spec._meta.content, {
          left:       scaledSpec.left + 12,
          top:        scaledSpec.top + scaledSpec.height * 0.22,
          width:      scaledSpec.width - 24,
          fontSize:   Math.round((spec.fontSize ?? 28) * scale),
          fontFamily: 'Montserrat, sans-serif',
          fontWeight: '800',
          fill:       '#FFFFFF',
          textAlign:  'center',
          charSpacing: 50,
          selectable: false,
          data:       { elementId: `${spec.id}_text`, locked: true },
        })
        canvas.add(btnText)
      }
      return
    }

    if (spec.fabricType === 'group' && spec.id === 'feature_grid') {
      renderFeatureGrid(canvas, { ...spec, left: scaledSpec.left, top: scaledSpec.top, width: scaledSpec.width, height: scaledSpec.height })
    }
  }

  // ── Layer panel sync ────────────────────────────────────────────────────────

  const syncLayers = useCallback(() => {
    if (!fabricRef.current) return
    const objs: any[] = fabricRef.current.getObjects()
    const layerItems: LayerItem[] = objs
      .filter((o: any) => o.data?.elementId)
      .map((o: any, i: number) => ({
        id:          o.data.elementId,
        displayName: getLayerDisplayName(o.data.elementId),
        visible:     o.visible !== false,
        locked:      o.lockMovementX && o.lockMovementY,
        selected:    o === fabricRef.current?.getActiveObject(),
        fabricType:  o.type,
        zIndex:      i,
      }))
      .reverse() // top-most first in layer panel
    setLayers(layerItems)
  }, [])

  // ── Selection handler ───────────────────────────────────────────────────────

  const onObjectSelected = useCallback((obj: any) => {
    if (!obj) return
    const elementId = obj.data?.elementId ?? null
    setSelectedId(elementId)
    setSelectedProps({
      elementId,
      fabricType:  obj.type,
      text:        obj.text,
      fontFamily:  obj.fontFamily,
      fontSize:    obj.fontSize ? Math.round(obj.fontSize / scale) : null,
      fontWeight:  obj.fontWeight,
      fill:        obj.fill,
      textAlign:   obj.textAlign,
      opacity:     obj.opacity,
      rx:          obj.rx ? Math.round(obj.rx / scale) : null,
      editable:    obj.data?.editable !== false,
      locked:      obj.data?.locked ?? false,
    })
  }, [scale])

  // ── History (undo/redo) ─────────────────────────────────────────────────────

  const saveHistory = useCallback(() => {
    if (!fabricRef.current) return
    const json = JSON.stringify(fabricRef.current.toJSON(['data']))
    historyRef.current = historyRef.current.slice(0, histPosRef.current + 1)
    historyRef.current.push(json)
    histPosRef.current = historyRef.current.length - 1
  }, [])

  const undo = useCallback(() => {
    if (histPosRef.current <= 0 || !fabricRef.current) return
    histPosRef.current -= 1
    const json = historyRef.current[histPosRef.current]
    fabricRef.current.loadFromJSON(json, () => { fabricRef.current.renderAll(); syncLayers() })
  }, [syncLayers])

  const redo = useCallback(() => {
    if (histPosRef.current >= historyRef.current.length - 1 || !fabricRef.current) return
    histPosRef.current += 1
    const json = historyRef.current[histPosRef.current]
    fabricRef.current.loadFromJSON(json, () => { fabricRef.current.renderAll(); syncLayers() })
  }, [syncLayers])

  // ── Layer panel actions ─────────────────────────────────────────────────────

  const handleLayerToggleVisible = useCallback((id: string) => {
    if (!fabricRef.current) return
    const obj = fabricRef.current.getObjects().find((o: any) => o.data?.elementId === id)
    if (!obj) return
    obj.visible = !obj.visible
    fabricRef.current.renderAll()
    syncLayers()
  }, [syncLayers])

  const handleLayerSelect = useCallback((id: string) => {
    if (!fabricRef.current) return
    const obj = fabricRef.current.getObjects().find((o: any) => o.data?.elementId === id)
    if (!obj) return
    fabricRef.current.setActiveObject(obj)
    fabricRef.current.renderAll()
    onObjectSelected(obj)
  }, [onObjectSelected])

  const handleLayerDelete = useCallback((id: string) => {
    if (!fabricRef.current) return
    const objs = fabricRef.current.getObjects().filter((o: any) => o.data?.elementId === id)
    objs.forEach((o: any) => fabricRef.current.remove(o))
    fabricRef.current.renderAll()
    saveHistory()
    syncLayers()
  }, [saveHistory, syncLayers])

  // ── Properties panel update ─────────────────────────────────────────────────

  const handlePropChange = useCallback((prop: string, value: any) => {
    if (!fabricRef.current) return
    const obj = fabricRef.current.getActiveObject()
    if (!obj) return
    obj.set(prop, prop === 'fontSize' ? value * scale : value)
    fabricRef.current.renderAll()
    saveHistory()
    setSelectedProps((prev: any) => ({ ...prev, [prop]: value }))
  }, [scale, saveHistory])

  // ── AI Assist ───────────────────────────────────────────────────────────────

  const handleAIImprove = useCallback(async (type: 'copy' | 'recolor' | 'regen_bg' | 'apply_brand') => {
    if (!fabricRef.current) return
    setAiLoading(true)
    try {
      if (type === 'copy') {
        const obj = fabricRef.current.getActiveObject()
        if (!obj || obj.type !== 'textbox') return
        const res = await fetch('/api/canvas/improve-copy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text:    obj.text,
            context: designBrief.triage?.goal ?? 'brand_awareness',
          }),
        })
        const data = await res.json()
        if (data.improved_text) {
          obj.set('text', data.improved_text)
          fabricRef.current.renderAll()
          saveHistory()
        }
      } else if (type === 'regen_bg') {
        // Trigger background regeneration — parent handles this
        onSave?.({
          canvasJson: fabricRef.current.toJSON(['data']),
          thumbnailDataUrl: fabricRef.current.toDataURL({ format: 'jpeg', quality: 0.6, multiplier: 0.25 }),
        })
      } else if (type === 'apply_brand') {
        const brand = designBrief.brand
        if (!brand) return
        fabricRef.current.getObjects().forEach((obj: any) => {
          if (obj.type === 'textbox' && obj.data?.elementType === 'text') {
            const eid = obj.data.elementId
            if (eid === 'headline') obj.set('fill', brand.text_primary)
            else obj.set('fill', brand.text_secondary)
          }
        })
        fabricRef.current.renderAll()
        saveHistory()
      }
    } finally {
      setAiLoading(false)
    }
  }, [fabricRef, designBrief, onSave, saveHistory])

  // ── Save & Export ───────────────────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    if (!fabricRef.current) return
    setSaving(true)
    try {
      const canvasJson = fabricRef.current.toJSON(['data'])
      const thumbnailDataUrl = fabricRef.current.toDataURL({
        format: 'jpeg', quality: 0.7, multiplier: 0.25,
      })
      await onSave?.({ canvasJson, thumbnailDataUrl })
    } finally {
      setSaving(false)
    }
  }, [onSave])

  const handleExportPNG = useCallback(() => {
    if (!fabricRef.current) return
    // Export at full resolution (multiplier = 1/scale)
    const dataUrl = fabricRef.current.toDataURL({
      format: 'png', multiplier: 1 / scale,
    })
    const link = document.createElement('a')
    link.download = 'photogenius-poster.png'
    link.href = dataUrl
    link.click()
  }, [scale])

  // ── Keyboard shortcuts ──────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === 'z') { e.preventDefault(); undo() }
        if (e.key === 'y') { e.preventDefault(); redo() }
        if (e.key === 's') { e.preventDefault(); handleSave() }
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const active = fabricRef.current?.getActiveObject()
        if (active && active.data?.editable && document.activeElement?.tagName !== 'INPUT') {
          fabricRef.current.remove(active)
          fabricRef.current.renderAll()
          saveHistory()
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [undo, redo, handleSave, saveHistory])

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className={`flex flex-col h-full bg-[#0A0A0F] text-white ${className}`}>
      {/* Top Toolbar */}
      <EditorToolbar
        onUndo={undo}
        onRedo={redo}
        onSave={handleSave}
        onExport={handleExportPNG}
        onAIAssist={handleAIImprove}
        saving={saving}
        aiLoading={aiLoading}
        canUndo={histPosRef.current > 0}
        canRedo={histPosRef.current < historyRef.current.length - 1}
      />

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Layer Panel */}
        <LayerPanel
          layers={layers}
          selectedId={selectedId}
          onSelect={handleLayerSelect}
          onToggleVisible={handleLayerToggleVisible}
          onDelete={handleLayerDelete}
        />

        {/* Center: Canvas */}
        <div className="flex-1 flex items-center justify-center bg-[#111118] overflow-auto p-6">
          <div className="relative" style={{ boxShadow: '0 0 60px rgba(0,0,0,0.8)' }}>
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-[#0F172A]/80 z-50 rounded">
                <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
              </div>
            )}
            <canvas
              ref={canvasRef}
              style={{
                width:  canvasWidth  * scale,
                height: canvasHeight * scale,
                display: 'block',
              }}
            />
          </div>
        </div>

        {/* Right: Properties Panel */}
        <PropertiesPanel
          selectedId={selectedId}
          selectedProps={selectedProps}
          designBrief={designBrief}
          onChange={handlePropChange}
          onAIAssist={handleAIImprove}
          aiLoading={aiLoading}
        />
      </div>
    </div>
  )
}

export default CanvasEditor
