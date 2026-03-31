import { create } from "zustand"

interface User {
  id: string
  email: string
  name?: string
  avatar?: string
  credits: number
  plan: "free" | "pro" | "business"
}

interface UserState {
  user: User | null
  loading: boolean
  error: string | null

  fetchUser: () => Promise<void>
  updateUser: (data: Partial<User>) => Promise<void>
  updateCredits: (credits: number) => void
  logout: () => void
}

export const useUserStore = create<UserState>((set) => ({
  user: null,
  loading: false,
  error: null,

  fetchUser: async () => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 1000))
      set({
        user: {
          id: "user_1",
          email: "user@example.com",
          name: "John Doe",
          credits: 147,
          plan: "free",
        },
        loading: false,
      })
    } catch (error) {
      set({ error: "Failed to load user", loading: false })
    }
  },

  updateUser: async (data: Partial<User>) => {
    set({ loading: true, error: null })
    try {
      // API call would go here
      await new Promise((resolve) => setTimeout(resolve, 500))
      set((state) => ({
        user: state.user ? { ...state.user, ...data } : null,
        loading: false,
      }))
    } catch (error) {
      set({ error: "Failed to update user", loading: false })
    }
  },

  updateCredits: (credits: number) => {
    set((state) => ({
      user: state.user ? { ...state.user, credits } : state.user,
    }))
  },

  logout: () => {
    set({ user: null })
  },
}))
