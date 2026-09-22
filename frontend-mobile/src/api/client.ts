import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import { Platform } from "react-native";

export const CUSTOM_API_BASE_KEY = "custom_support_api_base_url";
const DEFAULT_PORT = 8000;

export function getDetectedHost(): string {
  if (Platform.OS === "web" && typeof window !== "undefined" && window.location) {
    return window.location.hostname || "localhost";
  }

  const hostUri =
    Constants.expoConfig?.hostUri ??
    (Constants as any).manifest2?.extra?.expoClient?.hostUri ??
    (Constants as any).manifest?.debuggerHost;

  if (hostUri) {
    const host = hostUri.split(":")[0];
    if (host && host.trim()) {
      return host.trim();
    }
  }

  if (Platform.OS === "android") {
    return "10.0.2.2";
  }

  return "localhost";
}

export function computeDefaultBase(): string {
  const envUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (envUrl && envUrl.trim()) {
    return envUrl.trim().replace(/\/$/, "");
  }

  const host = getDetectedHost();
  return `http://${host}:${DEFAULT_PORT}`;
}

let activeApiBase = computeDefaultBase();

export async function initApiClient(): Promise<string> {
  try {
    const saved = await AsyncStorage.getItem(CUSTOM_API_BASE_KEY);
    if (saved && saved.trim()) {
      activeApiBase = saved.trim().replace(/\/$/, "");
    } else {
      activeApiBase = computeDefaultBase();
    }
  } catch {
    activeApiBase = computeDefaultBase();
  }
  return activeApiBase;
}

export function getActiveApiBase(): string {
  return activeApiBase;
}

export async function setCustomApiBase(url: string): Promise<void> {
  const cleaned = url.trim().replace(/\/$/, "");
  activeApiBase = cleaned;
  await AsyncStorage.setItem(CUSTOM_API_BASE_KEY, cleaned);
}

export async function resetCustomApiBase(): Promise<string> {
  await AsyncStorage.removeItem(CUSTOM_API_BASE_KEY);
  activeApiBase = computeDefaultBase();
  return activeApiBase;
}

export type SessionStatus = "active_ai" | "hitl_pending" | "human_active" | "closed";
export type MessageRole = "customer" | "agent" | "human_agent" | "system";
export type TicketStatus = "pending" | "claimed" | "resolved";

export interface Message {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface Session {
  id: string;
  customer_name: string | null;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  messages?: Message[];
  hitl_ticket?: HitlTicket | null;
}

export interface HitlTicket {
  id: string;
  session_id: string;
  ticket_id: string;
  priority: string;
  status: TicketStatus;
  handoff_data: Record<string, unknown>;
  claimed_by: string | null;
  claimed_at: string | null;
  created_at: string;
  customer_name?: string | null;
  last_message?: string | null;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const base = getActiveApiBase();
  const fullUrl = `${base}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);

  try {
    const res = await fetch(fullUrl, {
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...options?.headers },
      ...options,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Server error ${res.status}`);
    }
    return res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    const isTimeout = err.name === "AbortError";
    const message = isTimeout
      ? `Connection timed out connecting to ${base}`
      : err.message || "Network request failed";
    console.warn(`[API] Failed ${options?.method || "GET"} ${fullUrl}: ${message}`);
    throw new Error(message);
  }
}

export const api = {
  healthCheck: () => request<{ status: string }>("/api/health"),

  createSession: (customerName?: string) =>
    request<Session>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ customer_name: customerName || null }),
    }),

  getSession: (id: string) => request<Session>(`/api/sessions/${id}`),

  sendMessage: (sessionId: string, content: string) =>
    request<Message>(`/api/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  listTickets: (status?: TicketStatus) =>
    request<HitlTicket[]>(`/api/agents/tickets${status ? `?status=${status}` : ""}`),

  claimTicket: (ticketId: string, agentName: string) =>
    request<HitlTicket>(`/api/agents/tickets/${ticketId}/claim`, {
      method: "POST",
      body: JSON.stringify({ agent_name: agentName }),
    }),

  resolveTicket: (ticketId: string) =>
    request<HitlTicket>(`/api/agents/tickets/${ticketId}/resolve`, { method: "POST" }),

  getAgentSession: (sessionId: string) =>
    request<Session>(`/api/agents/sessions/${sessionId}`),

  sendAgentMessage: (sessionId: string, content: string, agentName: string) =>
    request<Message>(
      `/api/agents/sessions/${sessionId}/messages?agent_name=${encodeURIComponent(agentName)}`,
      { method: "POST", body: JSON.stringify({ content }) }
    ),
};

/** Returns the WebSocket URL using the currently active base URL */
export function wsUrl(path: string): string {
  const base = getActiveApiBase().replace(/^http/, "ws");
  return `${base}${path}`;
}
