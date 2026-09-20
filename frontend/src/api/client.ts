const API_BASE = "";

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
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
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

export function wsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  return `${proto}//${host}${path}`;
}
