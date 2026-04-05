'use client'

import React from 'react'
import { Eye, EyeOff, Lock, Trash2, Layers } from 'lucide-react'
import type { LayerItem } from './index'

interface LayerPanelProps {
  layers: LayerItem[]
  selectedId: string | null
  onSelect: (id: string) => void
  onToggleVisible: (id: string) => void
  onDelete: (id: string) => void
}

const LOCKED_IDS = new Set(['hero_image'])

export function LayerPanel({ layers, selectedId, onSelect, onToggleVisible, onDelete }: LayerPanelProps) {
  return (
    <div className="w-52 bg-[#13131A] border-r border-white/8 flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/8">
        <Layers className="w-3.5 h-3.5 text-purple-400" />
        <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">Layers</span>
        <span className="ml-auto text-xs text-white/30">{layers.length}</span>
      </div>

      {/* Layer list */}
      <div className="flex-1 overflow-y-auto py-1">
        {layers.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-white/30">
            No layers yet
          </div>
        )}
        {layers.map((layer) => {
          const isSelected = selectedId === layer.id
          const isLocked = LOCKED_IDS.has(layer.id) || layer.locked
          return (
            <div
              key={layer.id}
              onClick={() => !isLocked && onSelect(layer.id)}
              className={[
                'group flex items-center gap-1.5 px-2 py-1.5 cursor-pointer select-none',
                'transition-colors text-xs',
                isSelected
                  ? 'bg-purple-500/20 text-white'
                  : 'text-white/60 hover:bg-white/5 hover:text-white/80',
                !layer.visible && 'opacity-40',
              ].join(' ')}
            >
              {/* Visibility toggle */}
              <button
                onClick={(e) => { e.stopPropagation(); onToggleVisible(layer.id) }}
                className="shrink-0 p-0.5 rounded hover:bg-white/10 text-white/40 hover:text-white/70"
              >
                {layer.visible ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
              </button>

              {/* Lock indicator */}
              {isLocked && (
                <Lock className="w-3 h-3 shrink-0 text-white/25" />
              )}

              {/* Layer name */}
              <span className="flex-1 truncate font-medium">{layer.displayName}</span>

              {/* Delete (only editable, non-locked layers) */}
              {!isLocked && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(layer.id) }}
                  className="shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-white/30 hover:text-red-400 transition-opacity"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          )
        })}
      </div>

      {/* Add layer hint */}
      <div className="px-3 py-2 border-t border-white/8 text-xs text-white/25 text-center">
        Click layer to select
      </div>
    </div>
  )
}
