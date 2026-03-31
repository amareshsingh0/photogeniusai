"use client";

import { useEffect, useRef, useState } from "react";
import { io, Socket } from "socket.io-client";

const SOCKET_URL = process.env.NEXT_PUBLIC_SOCKET_URL || process.env.NEXT_PUBLIC_WS_URL?.replace(/^ws/, "http") || "";

export function useSocket(): { socket: Socket | null; connected: boolean } {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!SOCKET_URL) return;
    const s = io(SOCKET_URL, { transports: ["websocket"], autoConnect: true });
    setSocket(s);
    s.on("connect", () => setConnected(true));
    s.on("disconnect", () => setConnected(false));
    return () => {
      s.removeAllListeners();
      s.disconnect();
      setSocket(null);
      setConnected(false);
    };
  }, []);

  return { socket, connected };
}

export function useGenerationUpdates(onProgress?: (data: unknown) => void) {
  const { socket, connected } = useSocket();
  const onProgressRef = useRef(onProgress);
  onProgressRef.current = onProgress;

  useEffect(() => {
    if (!socket || !onProgressRef.current) return;
    socket.on("generation:progress", (data) => onProgressRef.current?.(data));
    return () => {
      socket.off("generation:progress");
    };
  }, [socket]);

  return { connected };
}

export function useTrainingUpdates(
  identityId: string | null,
  onProgress?: (data: { identity_id: string; progress: number; message: string }) => void
) {
  const { socket, connected } = useSocket();
  const onProgressRef = useRef(onProgress);
  onProgressRef.current = onProgress;

  useEffect(() => {
    if (!socket || !identityId || !onProgressRef.current) return;
    
    const handler = (data: { identity_id: string; progress: number; message: string }) => {
      if (data.identity_id === identityId) {
        onProgressRef.current?.(data);
      }
    };
    
    socket.on("training:progress", handler);
    return () => {
      socket.off("training:progress", handler);
    };
  }, [socket, identityId]);

  return { connected };
}
