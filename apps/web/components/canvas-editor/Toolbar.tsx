'use client'

import React from 'react'
import {
  Undo2, Redo2, Save, Download, AlignStartHorizontal, AlignCenterHorizontal,
  AlignEndHorizontal, AlignStartVertical, AlignCenterVertical, AlignEndVertical,
  Loader2, Wand2, ZoomIn, ZoomOut, RotateCcw,
} from 'lucide-react'

interface EditorToolbarProps {
  onUndo: () => void
  onRedo: () => void
  onSave: () => void
  onExport: () => void
  onAIAssist: (type: 'copy' | 'recolor' | 'regen_bg' | 'apply_brand') => void
  saving: boolean
  aiLoading: boolean
  canUndo: boolean
  canRedo: boolean
}

export function EditorToolbar({
  onUndo, onRedo, onSave, onExport, onAIAssist,
  saving, aiLoading, canUndo, canRedo,
}: EditorToolbarProps) {
  return (
    <div className="h-11 flex items-center gap-1 px-3 bg-[#0E0E16] border-b border-white/8 shrink-0">
      {/* History */}
      <ToolbarGroup>
        <ToolbarButton
          icon={<Undo2 className="w-3.5 h-3.5" />}
          label="Undo (Ctrl+Z)"
          onClick={onUndo}
          disabled={!canUndo}
        />
        <ToolbarButton
          icon={<Redo2 className="w-3.5 h-3.5" />}
          label="Redo (Ctrl+Y)"
          onClick={onRedo}
          disabled={!canRedo}
        />
      </ToolbarGroup>

      <Divider />

      {/* Save & Export */}
      <ToolbarGroup>
        <button
          onClick={onSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium transition-colors disabled:opacity-60"
        >
          {saving
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Save className="w-3.5 h-3.5" />
          }
          <span>Save</span>
        </button>

        <button
          onClick={onExport}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/8 hover:bg-white/15 text-white/70 hover:text-white text-xs font-medium transition-colors border border-white/10"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export PNG</span>
        </button>
      </ToolbarGroup>

      <Divider />

      {/* AI Assist quick buttons */}
      <ToolbarGroup>
        <button
          onClick={() => onAIAssist('regen_bg')}
          disabled={aiLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-gradient-to-r from-purple-600/30 to-blue-600/30 hover:from-purple-600/50 hover:to-blue-600/50 border border-purple-500/30 text-purple-300 hover:text-white text-xs font-medium transition-all disabled:opacity-50"
        >
          {aiLoading
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Wand2 className="w-3.5 h-3.5" />
          }
          <span>Regen BG</span>
        </button>
      </ToolbarGroup>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Info */}
      <span className="text-xs text-white/20 mr-2 select-none">
        Ctrl+Z undo · Ctrl+S save · Del delete
      </span>
    </div>
  )
}

function ToolbarGroup({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center gap-0.5">{children}</div>
}

function ToolbarButton({
  icon, label, onClick, disabled = false,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="p-1.5 rounded hover:bg-white/10 text-white/50 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
    >
      {icon}
    </button>
  )
}

function Divider() {
  return <div className="w-px h-5 bg-white/10 mx-1" />
}
