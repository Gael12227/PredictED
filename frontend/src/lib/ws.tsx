import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { FullPayload } from "./types";

interface SocketState {
  payload: FullPayload | null;
  connected: boolean;
  lastMessageAt: number | null;
}

const SocketContext = createContext<SocketState>({
  payload: null,
  connected: false,
  lastMessageAt: null,
});

export function SocketProvider({ children }: { children: ReactNode }) {
  const [payload, setPayload] = useState<FullPayload | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const aliveRef = useRef(true);

  const connect = useCallback(() => {
    if (!aliveRef.current) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/dashboard`);
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const scheduleRetry = () => {
      if (!closed && aliveRef.current) {
        retryTimer = setTimeout(connect, 2000);
      }
    };

    ws.onopen = () => setConnected(true);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string);
        if (data && data.contexts) {
          setPayload(data as FullPayload);
          setLastMessageAt(Date.now());
        }
      } catch {
        /* ignore non-payload frames (pong etc.) */
      }
    };
    ws.onclose = () => {
      setConnected(false);
      if (!closed) scheduleRetry();
    };
    ws.onerror = () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
    // keepalive ping (server replies with a pong frame we ignore)
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 10000);

    return () => {
      closed = true;
      clearInterval(ping);
      if (retryTimer) clearTimeout(retryTimer);
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    const cleanup = connect();
    return () => {
      aliveRef.current = false;
      cleanup?.();
    };
  }, [connect]);

  return (
    <SocketContext.Provider value={{ payload, connected, lastMessageAt }}>
      {children}
    </SocketContext.Provider>
  );
}

export function useSocket(): SocketState {
  return useContext(SocketContext);
}
