import { useCallback, useEffect, useRef, useState } from "react";
import { api, Message, wsUrl } from "../api/client";
import ChatInput from "../components/ChatInput";
import MessageBubble from "../components/MessageBubble";
import { useWebSocket } from "../hooks/useWebSocket";

const SESSION_KEY = "support_session_id";

const SUGGESTIONS = [
  "How do I get Spotify Premium?",
  "My offline downloads won't play",
  "How do I update my payment method?",
  "I'm having trouble logging in",
];

export default function CustomerChat() {
  const [sessionId, setSessionId] = useState<string | null>(() => localStorage.getItem(SESSION_KEY));
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<string>("active_ai");
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  const appendMessage = useCallback((msg: Message) => {
    setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
  }, []);

  const handleWsMessage = useCallback(
    (data: Record<string, unknown>) => {
      if (data.type === "message" && data.message) {
        const msg = data.message as Message;
        appendMessage(msg);
        if (msg.role !== "customer") setLoading(false);
      }
      if (data.type === "hitl_pending") {
        setStatus("hitl_pending");
        setLoading(false);
        if (data.message) appendMessage(data.message as Message);
      }
      if (data.type === "agent_joined") {
        setStatus("human_active");
        if (data.message) appendMessage(data.message as Message);
      }
      if (data.type === "session_closed") {
        setStatus("closed");
        setLoading(false);
        if (data.message) appendMessage(data.message as Message);
      }
    },
    [appendMessage]
  );

  const { connected, send } = useWebSocket(
    sessionId ? wsUrl(`/ws/sessions/${sessionId}`) : null,
    handleWsMessage
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    async function init() {
      try {
        let id = sessionId;
        if (!id) {
          const session = await api.createSession();
          id = session.id;
          localStorage.setItem(SESSION_KEY, id);
          setSessionId(id);
        }
        const session = await api.getSession(id);
        setMessages(session.messages || []);
        setStatus(session.status);
      } finally {
        setInitializing(false);
      }
    }
    init();
  }, []);

  async function handleSend(content: string) {
    if (!sessionId || loading || status === "closed") return;
    setLoading(true);
    try {
      if (connected) {
        send({ content });
      } else {
        await api.sendMessage(sessionId, content);
        const session = await api.getSession(sessionId);
        setMessages(session.messages || []);
        setStatus(session.status);
        setLoading(false);
      }
    } catch {
      setLoading(false);
    }
  }

  function handleNewChat() {
    localStorage.removeItem(SESSION_KEY);
    window.location.reload();
  }

  if (initializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#121212] text-sm text-[#a7a7a7]">
        <div className="flex items-center gap-2.5">
          <div className="h-2 w-2 animate-ping rounded-full bg-[#1db954]" />
          <span>Connecting to Spotify Support...</span>
        </div>
      </div>
    );
  }

  const inputDisabled = loading || status === "closed";
  const statusConfig =
    status === "hitl_pending"
      ? { label: "Connecting with specialist", dotColor: "bg-amber-400" }
      : status === "human_active"
        ? { label: "Live with Support Specialist", dotColor: "bg-[#1db954]" }
        : status === "closed"
          ? { label: "Chat ended", dotColor: "bg-neutral-500" }
          : { label: "Support Team · Online", dotColor: "bg-[#1db954]" };

  return (
    <div className="flex min-h-screen flex-col bg-[#121212] text-white">
      {/* Spotify Themed Header */}
      <header className="sticky top-0 z-10 border-b border-[#242424] bg-[#181818]/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3.5">
          <div className="flex items-center gap-3">
            {/* Spotify Brand Emblem */}
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-black text-[#1db954] shadow-inner">
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.498 17.306c-.217.355-.678.47-1.033.253-2.83-1.728-6.392-2.119-10.588-1.161-.403.093-.807-.16-.899-.562-.093-.404.16-.807.562-.899 4.593-1.05 8.528-.604 11.705 1.336.355.217.47.678.253 1.033zm1.468-3.26c-.273.444-.852.587-1.296.314-3.24-1.99-8.178-2.565-12.01-1.401-.497.151-1.026-.134-1.177-.63-.151-.496.134-1.026.63-1.177 4.383-1.33 9.818-.69 13.539 1.6-.444.272-.587.852-.314 1.294zm.14-3.4c-3.886-2.308-10.298-2.52-14.008-1.393-.596.182-1.229-.163-1.411-.758-.182-.596.163-1.229.758-1.411 4.258-1.293 11.33-1.05 15.795 1.6.535.318.71 1.011.393 1.545-.318.536-1.011.71-1.527.417z" />
              </svg>
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-tight text-white">Spotify Support</h1>
              <div className="flex items-center gap-1.5 text-xs text-[#a7a7a7]">
                <span className={`h-2 w-2 rounded-full ${statusConfig.dotColor} animate-pulse`} />
                <span>{statusConfig.label}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center">
            {/* Note: Agent Login link was removed as requested */}
            <button
              type="button"
              onClick={handleNewChat}
              className="rounded-full border border-[#333333] bg-[#222222] px-3.5 py-1.5 text-xs font-medium text-[#e0e0e0] transition hover:border-[#555555] hover:bg-[#2c2c2c] hover:text-white"
            >
              New chat
            </button>
          </div>
        </div>
      </header>

      {/* Main Chat Feed */}
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 && (
            <div className="flex h-full min-h-[380px] flex-col items-center justify-center text-center px-4">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#1db954]/10 text-[#1db954]">
                <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 18v-6a9 9 0 0118 0v6M21 19a2 2 0 01-2 2h-1a2 2 0 01-2-2v-3a2 2 0 012-2h3zM3 19a2 2 0 002 2h1a2 2 0 002-2v-3a2 2 0 00-2-2H3z" />
                </svg>
              </div>
              <h2 className="mb-1 text-lg font-semibold text-white">How can we help today?</h2>
              <p className="max-w-sm text-xs text-[#a7a7a7] mb-6">
                Ask us anything about your Spotify account, Premium plan, playback, or troubleshooting.
              </p>

              {/* Clickable Quick Topics */}
              <div className="flex flex-wrap justify-center gap-2 max-w-md">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => handleSend(suggestion)}
                    className="rounded-full border border-[#2e2e2e] bg-[#181818] px-3.5 py-2 text-xs font-medium text-[#cccccc] transition hover:border-[#1db954] hover:bg-[#222222] hover:text-white"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {loading && (
            <div className="flex justify-start mb-4">
              <div className="flex flex-col items-start max-w-[85%]">
                <span className="mb-1 text-xs text-[#a7a7a7] px-1">Spotify Support</span>
                <div className="rounded-2xl rounded-bl-sm border border-[#2e2e2e] bg-[#222222] px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-[#1db954] [animation-delay:0ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-[#1db954] [animation-delay:150ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-[#1db954] [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <ChatInput
          onSend={handleSend}
          disabled={inputDisabled}
          placeholder={
            status === "closed" ? "This conversation is closed" : "Type your message or question..."
          }
        />
      </main>
    </div>
  );
}
