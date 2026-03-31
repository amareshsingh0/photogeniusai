import { create } from "zustand"

interface GalleryState {
  images: any[]
  loading: boolean
  error: string | null

  fetchImages: () => Promise<void>
  deleteImage: (imageId: string) => Promise<void>
  toggleLike: (imageId: string) => Promise<void>
}

export const useGalleryStore = create<GalleryState>((set) => ({
  images: [],
  loading: false,
  error: null,

  fetchImages: async () => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 1000))
      set({ loading: false })
    } catch (error) {
      set({ error: "Failed to load images", loading: false })
    }
  },

  deleteImage: async (imageId: string) => {
    try {
      // API call would go here
      set((state) => ({
        images: state.images.filter((img) => img.id !== imageId),
      }))
    } catch (error) {
      set({ error: "Failed to delete image" })
    }
  },

  toggleLike: async (imageId: string) => {
    try {
      // API call would go here
      set((state) => ({
        images: state.images.map((img) =>
          img.id === imageId ? { ...img, liked: !img.liked } : img
        ),
      }))
    } catch (error) {
      set({ error: "Failed to update like" })
    }
  },
}))
