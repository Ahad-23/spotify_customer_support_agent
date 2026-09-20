import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, HitlTicket, Message, wsUrl } from "../api/client";
import ChatInput from "../components/ChatInput";
import MessageBubble from "../components/MessageBubble";
import TicketCard from "../components/TicketCard";
import { useWebSocket } from "../hooks/useWebSocket";

const AGENT_NAME_KEY = "support_agent_name";

export default function AgentDashboard() {
  const [agentName, setAgentName] = useState(() => localStorage.getItem(AGENT_NAME_KEY) || "");
  const [nameInput, setNameInput] = useState(agentName);
  const [tickets, setTickets] = useState<HitlTicket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<HitlTicket | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadTickets = useCallback(async () => {
    const data = await api.listTickets();
    setTickets(data);
  }, []);

  const loadSession = useCallback(async (sessionId: string) => {
    const session = await api.getAgentSession(sessionId);
    setMessages(session.messages || []);
  }, []);

  const handleWsMessage = useCallback(
    (data: Record<string, unknown>) => {
      if (data.type === "hitl_new") {
        const ticket = data.ticket as HitlTicket;
        setTickets((prev) => [ticket, ...prev.filter((t) => t.id !== ticket.id)]);
        setNotification(`New handoff: ${ticket.ticket_id}`);
        setTimeout(() => setNotification(null), 5000);
      }
      if (data.type === "hitl_claimed") {
        loadTickets();
      }
      if (data.type === "hitl_resolved") {
        loadTickets();
        if (selectedTicket && data.ticket_id === selectedTicket.id) {
          setSelectedTicket(null);
          setMessages([]);
        }
      }
      if (data.type === "customer_message" && selectedTicket) {
        if (data.session_id === selectedTicket.session_id && data.message) {
          const msg = data.message as Message;
          setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
        }
        loadTickets();
      }
    },
    [loadTickets, selectedTicket]
  );

  useWebSocket(agentName ? wsUrl("/ws/agents") : null, handleWsMessage);

  useEffect(() => {
    if (agentName) loadTickets();
  }, [agentName, loadTickets]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (selectedTicket) loadSession(selectedTicket.session_id);
  }, [selectedTicket, loadSession]);

  function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    const name = nameInput.trim();
    if (!name) return;
    localStorage.setItem(AGENT_NAME_KEY, name);
    setAgentName(name);
  }

  async function handleClaim(ticket: HitlTicket) {
    try {
      const updated = await api.claimTicket(ticket.id, agentName);
      setSelectedTicket(updated);
      await loadTickets();
      await loadSession(updated.session_id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not claim ticket");
      loadTickets();
    }
  }

  async function handleSend(content: string) {
    if (!selectedTicket || loading) return;
    setLoading(true);
    try {
      const msg = await api.sendAgentMessage(selectedTicket.session_id, content, agentName);
      setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
    } finally {
      setLoading(false);
    }
  }

  async function handleResolve() {
    if (!selectedTicket) return;
    await api.resolveTicket(selectedTicket.id);
    setSelectedTicket(null);
    setMessages([]);
    loadTickets();
  }

  if (!agentName) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#121212] px-4">
        <form
          onSubmit={handleSignIn}
          className="w-full max-w-sm rounded-2xl border border-[#2e2e2e] bg-[#181818] p-8 shadow-xl"
        >
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-[#1db954] text-black">
            <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.498 17.306c-.217.355-.678.47-1.033.253-2.83-1.728-6.392-2.119-10.588-1.161-.403.093-.807-.16-.899-.562-.093-.404.16-.807.562-.899 4.593-1.05 8.528-.604 11.705 1.336.355.217.47.678.253 1.033zm1.468-3.26c-.273.444-.852.587-1.296.314-3.24-1.99-8.178-2.565-12.01-1.401-.497.151-1.026-.134-1.177-.63-.151-.496.134-1.026.63-1.177 4.383-1.33 9.818-.69 13.539 1.6-.444.272-.587.852-.314 1.294zm.14-3.4c-3.886-2.308-10.298-2.52-14.008-1.393-.596.182-1.229-.163-1.411-.758-.182-.596.163-1.229.758-1.411 4.258-1.293 11.33-1.05 15.795 1.6.535.318.71 1.011.393 1.545-.318.536-1.011.71-1.527.417z" />
            </svg>
          </div>
          <h1 className="mb-1 text-xl font-bold text-white">Agent Workspace</h1>
          <p className="mb-6 text-sm text-[#a7a7a7]">Sign in to manage escalated support requests</p>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-[#b3b3b3]">
            Agent Name
          </label>
          <input
            type="text"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            className="mb-5 w-full rounded-xl border border-[#333333] bg-[#222222] px-3.5 py-2.5 text-sm text-white outline-none transition focus:border-[#1db954]"
            placeholder="e.g. Alex"
            autoFocus
          />
          <button
            type="submit"
            className="w-full rounded-full bg-[#1db954] py-3 text-sm font-semibold text-black transition hover:bg-[#1ed760]"
          >
            Open Console
          </button>
          <Link
            to="/"
            className="mt-4 block text-center text-xs text-[#8e8e8e] transition hover:text-white"
          >
            ← Back to customer chat
          </Link>
        </form>
      </div>
    );
  }

  const canChat =
    selectedTicket &&
    (selectedTicket.status === "claimed" || selectedTicket.claimed_by === agentName);
  const pendingCount = tickets.filter((t) => t.status === "pending").length;

  return (
    <div className="flex h-screen flex-col bg-[#121212] text-white">
      {notification && (
        <div className="bg-[#1db954] px-4 py-2 text-center text-xs font-semibold text-black">
          {notification}
        </div>
      )}

      <header className="border-b border-[#242424] bg-[#181818] px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#1db954] text-black text-xs font-bold">
              ♫
            </div>
            <div>
              <h1 className="text-sm font-semibold text-white">Spotify Support Console</h1>
              <p className="text-xs text-[#a0a0a0]">
                Logged in as <span className="text-white font-medium">{agentName}</span>
                {pendingCount > 0 && (
                  <span className="ml-2 rounded-full bg-red-950/70 border border-red-800/60 px-2 py-0.5 text-xs text-red-400 font-semibold">
                    {pendingCount} pending
                  </span>
                )}
              </p>
            </div>
          </div>
          <Link
            to="/"
            className="rounded-full border border-[#333333] px-3 py-1 text-xs text-[#cccccc] transition hover:border-[#555555] hover:text-white"
          >
            Customer view
          </Link>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-80 shrink-0 overflow-y-auto border-r border-[#242424] bg-[#141414] p-3">
          <h2 className="mb-3 px-1 text-xs font-semibold uppercase tracking-wider text-[#8e8e8e]">
            Handoff Queue
          </h2>
          {tickets.length === 0 ? (
            <p className="px-1 text-sm text-[#777777]">No active handoffs</p>
          ) : (
            <div className="space-y-2.5">
              {tickets.map((ticket) => (
                <TicketCard
                  key={ticket.id}
                  ticket={ticket}
                  selected={selectedTicket?.id === ticket.id}
                  onSelect={() => setSelectedTicket(ticket)}
                  onClaim={ticket.status === "pending" ? () => handleClaim(ticket) : undefined}
                />
              ))}
            </div>
          )}
        </aside>

        <main className="flex flex-1 flex-col bg-[#121212]">
          {!selectedTicket ? (
            <div className="flex flex-1 items-center justify-center text-sm text-[#777777]">
              Select a customer ticket to view conversation
            </div>
          ) : (
            <>
              <div className="border-b border-[#242424] bg-[#181818] px-4 py-3.5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {selectedTicket.customer_name || "Spotify User"} · {selectedTicket.ticket_id}
                    </p>
                    <p className="text-xs text-[#a0a0a0]">
                      {(selectedTicket.handoff_data.escalation_reason as string) || "Escalation requested"}
                    </p>
                  </div>
                  {canChat && (
                    <button
                      type="button"
                      onClick={handleResolve}
                      className="rounded-full border border-[#3e3e3e] bg-[#242424] px-3.5 py-1.5 text-xs font-medium text-[#cccccc] transition hover:border-[#1db954] hover:text-white"
                    >
                      Resolve ticket
                    </button>
                  )}
                </div>

                {selectedTicket.status === "pending" && (
                  <button
                    type="button"
                    onClick={() => handleClaim(selectedTicket)}
                    className="mt-3 w-full rounded-xl bg-[#1db954] py-2 text-sm font-semibold text-black transition hover:bg-[#1ed760]"
                  >
                    Take over conversation
                  </button>
                )}

                {selectedTicket.handoff_data && (
                  <div className="mt-3 grid grid-cols-2 gap-2 rounded-xl bg-[#202020] p-3 text-xs border border-[#2a2a2a]">
                    <div>
                      <span className="text-[#8e8e8e]">Intent</span>
                      <p className="font-semibold text-[#e0e0e0]">
                        {selectedTicket.handoff_data.case_intent as string}
                      </p>
                    </div>
                    <div>
                      <span className="text-[#8e8e8e]">Priority</span>
                      <p className="font-semibold text-[#e0e0e0]">{selectedTicket.priority}</p>
                    </div>
                    <div>
                      <span className="text-[#8e8e8e]">Frustration</span>
                      <p className="font-semibold text-[#e0e0e0]">
                        {selectedTicket.handoff_data.frustration_level as string}
                      </p>
                    </div>
                    <div>
                      <span className="text-[#8e8e8e]">Failed attempts</span>
                      <p className="font-semibold text-[#e0e0e0]">
                        {String(selectedTicket.handoff_data.failed_attempts ?? 0)}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-4">
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} />
                ))}
                <div ref={bottomRef} />
              </div>

              {canChat ? (
                <ChatInput onSend={handleSend} disabled={loading} placeholder="Type your reply to customer..." />
              ) : selectedTicket.status === "resolved" ? (
                <div className="border-t border-[#242424] bg-[#141414] p-4 text-center text-xs text-[#888888]">
                  This ticket has been marked resolved
                </div>
              ) : (
                <div className="border-t border-[#242424] bg-[#141414] p-4 text-center text-xs text-[#888888]">
                  Claim this ticket to start replying
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
