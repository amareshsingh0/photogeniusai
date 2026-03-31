/**
 * Enhanced WebSocket Integration
 * - Socket.io client setup
 * - Real-time training progress
 * - Real-time generation progress
 * - Connection management
 * - Reconnection logic
 */

import { io, Socket } from "socket.io-client"
import { useEffect, useRef, useState, useCallback } from "react"

// Types
export interface TrainingProgress {
  identity_id: string
  progress: number
  message: string
  status: "PENDING" | "TRAINING" | "READY" | "FAILED"
}

export interface GenerationProgress {
  generation_id: string
  progress: number
  current_step: string
  status: "PENDING" | "GENERATING" | "COMPLETED" | "FAILED"
  output_urls?: string[]
  error?: string
}

export interface SocketConfig {
  url?: string
  autoConnect?: boolean
  reconnection?: boolean
  reconnectionDelay?: number
  reconnectionDelayMax?: number
  reconnectionAttempts?: number
}

// Default configuration
const DEFAULT_CONFIG: Required<SocketConfig> = {
  url: process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000",
  autoConnect: true,
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  reconnectionAttempts: 5,
}

/**
 * Create socket instance
 */
export function createSocket(config: SocketConfig = {}): Socket {
  const finalConfig = { ...DEFAULT_CONFIG, ...config }

  return io(finalConfig.url, {
    transports: ["websocket", "polling"],
    autoConnect: finalConfig.autoConnect,
    reconnection: finalConfig.reconnection,
    reconnectionDelay: finalConfig.reconnectionDelay,
    reconnectionDelayMax: finalConfig.reconnectionDelayMax,
    reconnectionAttempts: finalConfig.reconnectionAttempts,
    withCredentials: true,
  })
}

/**
 * Hook for socket connection
 */
export function useSocket(config: SocketConfig = {}) {
  const [socket, setSocket] = useState<Socket | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const socketRef = useRef<Socket | null>(null)

  useEffect(() => {
    if (socketRef.current) {
      return // Socket already created
    }

    const s = createSocket(config)
    socketRef.current = s
    setSocket(s)

    // Connection events
    s.on("connect", () => {
      setConnected(true)
      setError(null)
      console.log("Socket connected:", s.id)
    })

    s.on("disconnect", (reason) => {
      setConnected(false)
      console.log("Socket disconnected:", reason)
    })

    s.on("connect_error", (err) => {
      setError(err)
      console.error("Socket connection error:", err)
    })

    s.on("reconnect", (attemptNumber) => {
      console.log("Socket reconnected after", attemptNumber, "attempts")
      setConnected(true)
      setError(null)
    })

    s.on("reconnect_attempt", (attemptNumber) => {
      console.log("Socket reconnection attempt:", attemptNumber)
    })

    s.on("reconnect_error", (err) => {
      console.error("Socket reconnection error:", err)
      setError(err)
    })

    s.on("reconnect_failed", () => {
      console.error("Socket reconnection failed")
      setError(new Error("Failed to reconnect"))
    })

    // Cleanup
    return () => {
      if (socketRef.current) {
        socketRef.current.removeAllListeners()
        socketRef.current.disconnect()
        socketRef.current = null
        setSocket(null)
        setConnected(false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.url]) // Only recreate if URL changes

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.disconnect()
    }
  }, [])

  const reconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.connect()
    }
  }, [])

  return {
    socket,
    connected,
    error,
    disconnect,
    reconnect,
  }
}

/**
 * Hook for training progress updates
 */
export function useTrainingProgress(
  identityId: string | null,
  onProgress?: (data: TrainingProgress) => void
) {
  const { socket, connected } = useSocket()
  const onProgressRef = useRef(onProgress)
  onProgressRef.current = onProgress

  useEffect(() => {
    if (!socket || !identityId || !onProgressRef.current) return

    const handler = (data: TrainingProgress) => {
      if (data.identity_id === identityId) {
        onProgressRef.current?.(data)
      }
    }

    socket.on("training:progress", handler)

    // Subscribe to this identity's training updates
    socket.emit("training:subscribe", { identity_id: identityId })

    return () => {
      socket.off("training:progress", handler)
      socket.emit("training:unsubscribe", { identity_id: identityId })
    }
  }, [socket, identityId])

  return { connected }
}

/**
 * Hook for generation progress updates
 */
export function useGenerationProgress(
  generationId: string | null,
  onProgress?: (data: GenerationProgress) => void
) {
  const { socket, connected } = useSocket()
  const onProgressRef = useRef(onProgress)
  onProgressRef.current = onProgress

  useEffect(() => {
    if (!socket || !generationId || !onProgressRef.current) return

    const handler = (data: GenerationProgress) => {
      if (data.generation_id === generationId) {
        onProgressRef.current?.(data)
      }
    }

    socket.on("generation:progress", handler)

    // Subscribe to this generation's updates
    socket.emit("generation:subscribe", { generation_id: generationId })

    return () => {
      socket.off("generation:progress", handler)
      socket.emit("generation:unsubscribe", { generation_id: generationId })
    }
  }, [socket, generationId])

  return { connected }
}

/**
 * Hook for multiple training progress updates
 */
export function useMultipleTrainingProgress(
  identityIds: string[],
  onProgress?: (data: TrainingProgress) => void
) {
  const { socket, connected } = useSocket()
  const onProgressRef = useRef(onProgress)
  onProgressRef.current = onProgress

  useEffect(() => {
    if (!socket || identityIds.length === 0 || !onProgressRef.current) return

    const handler = (data: TrainingProgress) => {
      if (identityIds.includes(data.identity_id)) {
        onProgressRef.current?.(data)
      }
    }

    socket.on("training:progress", handler)

    // Subscribe to all identities
    identityIds.forEach((id) => {
      socket.emit("training:subscribe", { identity_id: id })
    })

    return () => {
      socket.off("training:progress", handler)
      identityIds.forEach((id) => {
        socket.emit("training:unsubscribe", { identity_id: id })
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socket, identityIds.join(",")]) // Re-run when identity IDs change

  return { connected }
}
