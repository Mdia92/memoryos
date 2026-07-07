"use client";

// Live notifications from the backend over Server-Sent Events.

import { useEffect, useRef, useState } from "react";
import { API_URL } from "./api";

export interface Notification {
  ts: string;
  type: string;
  [key: string]: unknown;
}

export function useStream(onNotification?: (n: Notification) => void) {
  const [connected, setConnected] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const handlerRef = useRef(onNotification);
  handlerRef.current = onNotification;

  useEffect(() => {
    const source = new EventSource(`${API_URL}/api/stream`);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("notification", (e) => {
      try {
        const n = JSON.parse((e as MessageEvent).data) as Notification;
        setNotifications((prev) => [n, ...prev].slice(0, 50));
        handlerRef.current?.(n);
      } catch {
        // ignore malformed payloads
      }
    });
    return () => source.close();
  }, []);

  return { connected, notifications };
}
