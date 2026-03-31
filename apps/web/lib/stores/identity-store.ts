import { create } from "zustand"

interface Identity {
  id: string
  name?: string
  imageUrls: string[]
  status: "PENDING" | "TRAINING" | "READY" | "FAILED"
  createdAt: string
  progress?: number
}

interface IdentityState {
  identities: Identity[]
  loading: boolean
  error: string | null
  selectedIdentity: string | null

  fetchIdentities: () => Promise<void>
  createIdentity: (data: { name?: string; imageUrls: string[] }) => Promise<Identity>
  startTraining: (identityId: string) => Promise<void>
  updateIdentityProgress: (identityId: string, progress: number) => void
  deleteIdentity: (identityId: string) => Promise<void>
  selectIdentity: (identityId: string | null) => void
}

export const useIdentityStore = create<IdentityState>((set, get) => ({
  identities: [],
  loading: false,
  error: null,
  selectedIdentity: null,

  fetchIdentities: async () => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 1000))
      set({ loading: false })
    } catch (error) {
      set({ error: "Failed to load identities", loading: false })
    }
  },

  createIdentity: async (data) => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 1000))
      const newIdentity: Identity = {
        id: `identity_${Date.now()}`,
        ...data,
        status: "PENDING",
        createdAt: new Date().toISOString(),
      }
      set((state) => ({
        identities: [...state.identities, newIdentity],
        loading: false,
      }))
      return newIdentity
    } catch (error) {
      set({ error: "Failed to create identity", loading: false })
      throw error
    }
  },

  startTraining: async (identityId: string) => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 1000))
      set((state) => ({
        identities: state.identities.map((id) =>
          id.id === identityId ? { ...id, status: "TRAINING", progress: 0 } : id
        ),
        loading: false,
      }))
    } catch (error) {
      set({ error: "Failed to start training", loading: false })
    }
  },

  updateIdentityProgress: (identityId: string, progress: number) => {
    set((state) => ({
      identities: state.identities.map((id) =>
        id.id === identityId ? { ...id, progress } : id
      ),
    }))
  },

  deleteIdentity: async (identityId: string) => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 500))
      set((state) => ({
        identities: state.identities.filter((id) => id.id !== identityId),
        selectedIdentity:
          state.selectedIdentity === identityId ? null : state.selectedIdentity,
        loading: false,
      }))
    } catch (error) {
      set({ error: "Failed to delete identity", loading: false })
    }
  },

  selectIdentity: (identityId: string | null) => {
    set({ selectedIdentity: identityId })
  },
}))
