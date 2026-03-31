import { create } from "zustand"

interface Settings {
  notifications: {
    email: {
      trainingComplete: boolean
      generationComplete: boolean
      creditLow: boolean
      weeklyDigest: boolean
      productUpdates: boolean
    }
    push: {
      trainingComplete: boolean
      generationComplete: boolean
      creditLow: boolean
    }
  }
  generation: {
    defaultMode: string
    defaultIdentity: string
    qualityPreference: number
    autoSaveToGallery: boolean
    autoDownload: boolean
    watermark: boolean
  }
}

interface SettingsState {
  settings: Settings
  loading: boolean
  error: string | null

  updateSettings: (updates: Partial<Settings>) => Promise<void>
  resetSettings: () => void
}

const defaultSettings: Settings = {
  notifications: {
    email: {
      trainingComplete: true,
      generationComplete: true,
      creditLow: true,
      weeklyDigest: false,
      productUpdates: true,
    },
    push: {
      trainingComplete: true,
      generationComplete: true,
      creditLow: false,
    },
  },
  generation: {
    defaultMode: "REALISM",
    defaultIdentity: "auto",
    qualityPreference: 80,
    autoSaveToGallery: true,
    autoDownload: false,
    watermark: false,
  },
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: defaultSettings,
  loading: false,
  error: null,

  updateSettings: async (updates) => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 500))
      set((state) => ({
        settings: {
          ...state.settings,
          ...updates,
        },
        loading: false,
      }))
      // Persist to localStorage
      if (typeof window !== "undefined") {
        localStorage.setItem("photogenius-settings", JSON.stringify({
          ...defaultSettings,
          ...updates,
        }))
      }
    } catch (error) {
      set({ error: "Failed to update settings", loading: false })
    }
  },

  resetSettings: () => {
    set({ settings: defaultSettings })
    if (typeof window !== "undefined") {
      localStorage.removeItem("photogenius-settings")
    }
  },
}))
