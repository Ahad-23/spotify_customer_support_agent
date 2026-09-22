import { useCallback, useEffect, useRef, useState } from "react";

type WsMessage = Record<string, unknown>;

export function useWebSocket(url: string | null, onMessage: (data: WsMessage) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const send = useCallback((payload: WsMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  useEffect(() => {
    if (!url) return;

    let alive = true;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const ws = new WebSocket(url as string);
      wsRef.current = ws;

      ws.onopen = () => {
        if (alive) setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessageRef.current(data);
        } catch {
          /* ignore malformed */
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (alive) reconnectTimer = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    const ping = setInterval(() => send({ type: "ping" }), 25000);

    return () => {
      alive = false;
      clearInterval(ping);
      clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [url, send]);

  return { connected, send };
}
