import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { api, HitlTicket, initApiClient, Message, wsUrl } from "../api/client";
import ChatInput from "../components/ChatInput";
import MessageBubble from "../components/MessageBubble";
import TicketCard from "../components/TicketCard";
import { useWebSocket } from "../hooks/useWebSocket";

const AGENT_NAME_KEY = "support_agent_name";

const COLORS = {
  bg: "#121212",
  surface: "#141414",
  surface2: "#181818",
  card: "#222222",
  border: "#242424",
  border2: "#2e2e2e",
  border3: "#333333",
  green: "#1db954",
  greenHover: "#1ed760",
  white: "#ffffff",
  muted: "#a7a7a7",
  muted2: "#a0a0a0",
  muted3: "#8e8e8e",
  muted4: "#777777",
  black: "#000000",
};

type AgentView = "tickets" | "chat";

export default function AgentDashboardScreen() {
  const [agentName, setAgentName] = useState<string>("");
  const [nameInput, setNameInput] = useState("");
  const [tickets, setTickets] = useState<HitlTicket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<HitlTicket | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);
  const [view, setView] = useState<AgentView>("tickets");
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    initApiClient();
    AsyncStorage.getItem(AGENT_NAME_KEY).then((saved) => {
      if (saved) setAgentName(saved);
    });
  }, []);

  const loadTickets = useCallback(async () => {
    try {
      const data = await api.listTickets();
      setTickets(data);
    } catch (err: any) {
      console.warn("[AgentDashboard] loadTickets failed:", err.message);
    }
  }, []);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const session = await api.getAgentSession(sessionId);
      setMessages(session.messages ?? []);
    } catch (err: any) {
      console.warn("[AgentDashboard] loadSession failed:", err.message);
    }
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
          setView("tickets");
        }
      }
      if (data.type === "customer_message" && selectedTicket) {
        if (data.session_id === selectedTicket.session_id && data.message) {
          const msg = data.message as Message;
          setMessages((prev) =>
            prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]
          );
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
    if (selectedTicket) loadSession(selectedTicket.session_id);
  }, [selectedTicket, loadSession]);

  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [messages]);

  async function handleSignIn() {
    const name = nameInput.trim();
    if (!name) return;
    await AsyncStorage.setItem(AGENT_NAME_KEY, name);
    setAgentName(name);
  }

  async function handleClaim(ticket: HitlTicket) {
    try {
      const updated = await api.claimTicket(ticket.id, agentName);
      setSelectedTicket(updated);
      setView("chat");
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
      const msg = await api.sendAgentMessage(
        selectedTicket.session_id,
        content,
        agentName
      );
      setMessages((prev) =>
        prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleResolve() {
    if (!selectedTicket) return;
    await api.resolveTicket(selectedTicket.id);
    setSelectedTicket(null);
    setMessages([]);
    setView("tickets");
    loadTickets();
  }

  // ─── Sign-in screen ───────────────────────────────────────────────────────
  if (!agentName) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.signinContainer}>
          <View style={styles.logoBg}>
            <Text style={styles.logoText}>♫</Text>
          </View>
          <Text style={styles.signinTitle}>Agent Workspace</Text>
          <Text style={styles.signinSub}>
            Sign in to manage escalated support requests
          </Text>
          <Text style={styles.inputLabel}>AGENT NAME</Text>
          <TextInput
            style={styles.nameInput}
            value={nameInput}
            onChangeText={setNameInput}
            placeholder="e.g. Alex"
            placeholderTextColor="#787878"
            autoFocus
            onSubmitEditing={handleSignIn}
            returnKeyType="done"
          />
          <TouchableOpacity style={styles.signinBtn} onPress={handleSignIn} activeOpacity={0.85}>
            <Text style={styles.signinBtnText}>Open Console</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const pendingCount = tickets.filter((t) => t.status === "pending").length;
  const canChat =
    selectedTicket &&
    (selectedTicket.status === "claimed" ||
      selectedTicket.claimed_by === agentName);

  // ─── Agent console ────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Notification banner */}
      {notification && (
        <View style={styles.notifBanner}>
          <Text style={styles.notifText}>{notification}</Text>
        </View>
      )}

      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.headerIcon}>
            <Text style={styles.headerIconText}>♫</Text>
          </View>
          <View>
            <Text style={styles.headerTitle}>Spotify Support Console</Text>
            <Text style={styles.headerSub}>
              Logged in as{" "}
              <Text style={{ color: COLORS.white, fontWeight: "600" }}>
                {agentName}
              </Text>
              {pendingCount > 0 && (
                <Text style={styles.pendingBadge}> {pendingCount} pending</Text>
              )}
            </Text>
          </View>
        </View>
      </View>

      {/* Tab bar: Tickets | Chat */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tab, view === "tickets" && styles.tabActive]}
          onPress={() => setView("tickets")}
        >
          <Text style={[styles.tabText, view === "tickets" && styles.tabTextActive]}>
            Queue {pendingCount > 0 ? `(${pendingCount})` : ""}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, view === "chat" && styles.tabActive]}
          onPress={() => setView("chat")}
          disabled={!selectedTicket}
        >
          <Text
            style={[
              styles.tabText,
              view === "chat" && styles.tabTextActive,
              !selectedTicket && styles.tabTextDisabled,
            ]}
          >
            {selectedTicket ? selectedTicket.ticket_id : "No Ticket"}
          </Text>
        </TouchableOpacity>
      </View>

      {/* ── Tickets Queue ── */}
      {view === "tickets" && (
        <ScrollView style={styles.ticketsPane} contentContainerStyle={styles.ticketsPaneContent}>
          {tickets.length === 0 ? (
            <Text style={styles.emptyText}>No active handoffs</Text>
          ) : (
            tickets.map((ticket) => (
              <TicketCard
                key={ticket.id}
                ticket={ticket}
                selected={selectedTicket?.id === ticket.id}
                onSelect={() => {
                  setSelectedTicket(ticket);
                  setView("chat");
                }}
                onClaim={
                  ticket.status === "pending" ? () => handleClaim(ticket) : undefined
                }
              />
            ))
          )}
        </ScrollView>
      )}

      {/* ── Chat Panel ── */}
      {view === "chat" && (
        <>
          {!selectedTicket ? (
            <View style={styles.noTicketContainer}>
              <Text style={styles.noTicketText}>
                Select a ticket from the queue to view conversation
              </Text>
            </View>
          ) : (
            <View style={{ flex: 1 }}>
              {/* Ticket info bar */}
              <View style={styles.ticketInfoBar}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.ticketCustomer}>
                    {selectedTicket.customer_name ?? "Spotify User"} ·{" "}
                    {selectedTicket.ticket_id}
                  </Text>
                  <Text style={styles.ticketReason}>
                    {(selectedTicket.handoff_data.escalation_reason as string) ??
                      "Escalation requested"}
                  </Text>
                </View>
                {canChat && (
                  <TouchableOpacity style={styles.resolveBtn} onPress={handleResolve}>
                    <Text style={styles.resolveBtnText}>Resolve</Text>
                  </TouchableOpacity>
                )}
              </View>

              {/* Claim banner */}
              {selectedTicket.status === "pending" && (
                <TouchableOpacity
                  style={styles.claimBanner}
                  onPress={() => handleClaim(selectedTicket)}
                  activeOpacity={0.85}
                >
                  <Text style={styles.claimBannerText}>Take over conversation</Text>
                </TouchableOpacity>
              )}

              {/* Handoff data grid */}
              {selectedTicket.handoff_data && (
                <View style={styles.dataGrid}>
                  <View style={styles.dataItem}>
                    <Text style={styles.dataLabel}>Intent</Text>
                    <Text style={styles.dataValue}>
                      {selectedTicket.handoff_data.case_intent as string}
                    </Text>
                  </View>
                  <View style={styles.dataItem}>
                    <Text style={styles.dataLabel}>Priority</Text>
                    <Text style={styles.dataValue}>{selectedTicket.priority}</Text>
                  </View>
                  <View style={styles.dataItem}>
                    <Text style={styles.dataLabel}>Frustration</Text>
                    <Text style={styles.dataValue}>
                      {selectedTicket.handoff_data.frustration_level as string}
                    </Text>
                  </View>
                  <View style={styles.dataItem}>
                    <Text style={styles.dataLabel}>Failed attempts</Text>
                    <Text style={styles.dataValue}>
                      {String(selectedTicket.handoff_data.failed_attempts ?? 0)}
                    </Text>
                  </View>
                </View>
              )}

              {/* Messages */}
              <FlatList
                ref={flatListRef}
                data={messages}
                keyExtractor={(item) => item.id}
                renderItem={({ item }) => <MessageBubble message={item} />}
                contentContainerStyle={styles.messageList}
                ListFooterComponent={
                  loading ? (
                    <ActivityIndicator size="small" color={COLORS.green} style={{ marginBottom: 12 }} />
                  ) : null
                }
                onContentSizeChange={() =>
                  flatListRef.current?.scrollToEnd({ animated: true })
                }
              />

              {/* Input / status bar */}
              {canChat ? (
                <ChatInput
                  onSend={handleSend}
                  disabled={loading}
                  placeholder="Type your reply to customer..."
                />
              ) : (
                <View style={styles.statusBar}>
                  <Text style={styles.statusBarText}>
                    {selectedTicket.status === "resolved"
                      ? "This ticket has been marked resolved"
                      : "Claim this ticket to start replying"}
                  </Text>
                </View>
              )}
            </View>
          )}
        </>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: COLORS.bg },

  // Sign-in
  signinContainer: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  logoBg: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: COLORS.green,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  logoText: { fontSize: 22, color: COLORS.black },
  signinTitle: {
    fontSize: 22,
    fontWeight: "700",
    color: COLORS.white,
    marginBottom: 6,
  },
  signinSub: {
    fontSize: 13,
    color: COLORS.muted,
    marginBottom: 24,
    lineHeight: 19,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1,
    color: "#b3b3b3",
    marginBottom: 8,
  },
  nameInput: {
    height: 48,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border2,
    backgroundColor: "#222222",
    paddingHorizontal: 14,
    fontSize: 14,
    color: COLORS.white,
    marginBottom: 20,
  },
  signinBtn: {
    height: 50,
    borderRadius: 25,
    backgroundColor: COLORS.green,
    alignItems: "center",
    justifyContent: "center",
  },
  signinBtnText: { fontSize: 15, fontWeight: "700", color: COLORS.black },

  // Notification
  notifBanner: {
    backgroundColor: COLORS.green,
    paddingVertical: 8,
    alignItems: "center",
  },
  notifText: { fontSize: 12, fontWeight: "700", color: COLORS.black },

  // Header
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface2,
  },
  headerLeft: { flexDirection: "row", alignItems: "center", gap: 12 },
  headerIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: COLORS.green,
    alignItems: "center",
    justifyContent: "center",
  },
  headerIconText: { fontSize: 14, color: COLORS.black },
  headerTitle: { fontSize: 13, fontWeight: "600", color: COLORS.white },
  headerSub: { fontSize: 11, color: COLORS.muted2 },
  pendingBadge: { color: "#f87171", fontWeight: "700" },

  // Tab bar
  tabBar: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface2,
  },
  tab: {
    flex: 1,
    paddingVertical: 11,
    alignItems: "center",
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabActive: { borderBottomColor: COLORS.green },
  tabText: { fontSize: 13, color: COLORS.muted3 },
  tabTextActive: { color: COLORS.green, fontWeight: "600" },
  tabTextDisabled: { color: "#444444" },

  // Ticket queue
  ticketsPane: { flex: 1, backgroundColor: COLORS.surface },
  ticketsPaneContent: { padding: 12 },
  emptyText: { fontSize: 13, color: COLORS.muted4, padding: 8 },

  // No ticket
  noTicketContainer: { flex: 1, alignItems: "center", justifyContent: "center" },
  noTicketText: { fontSize: 13, color: COLORS.muted4, textAlign: "center", paddingHorizontal: 32 },

  // Ticket info bar
  ticketInfoBar: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface2,
    gap: 10,
  },
  ticketCustomer: { fontSize: 14, fontWeight: "600", color: COLORS.white },
  ticketReason: { fontSize: 11, color: COLORS.muted2, marginTop: 2 },
  resolveBtn: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 99,
    borderWidth: 1,
    borderColor: COLORS.border2,
    backgroundColor: "#242424",
  },
  resolveBtnText: { fontSize: 12, color: "#cccccc" },

  // Claim banner
  claimBanner: {
    backgroundColor: COLORS.green,
    marginHorizontal: 14,
    marginTop: 10,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  claimBannerText: { fontSize: 14, fontWeight: "700", color: COLORS.black },

  // Data grid
  dataGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    margin: 14,
    marginTop: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#2a2a2a",
    backgroundColor: "#202020",
    padding: 12,
    gap: 8,
  },
  dataItem: { width: "48%", gap: 2 },
  dataLabel: { fontSize: 11, color: COLORS.muted3 },
  dataValue: { fontSize: 12, fontWeight: "600", color: "#e0e0e0" },

  // Messages
  messageList: {
    paddingHorizontal: 14,
    paddingTop: 14,
    paddingBottom: 8,
  },

  // Status bar (no-chat state)
  statusBar: {
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    backgroundColor: COLORS.surface,
    paddingVertical: 16,
    alignItems: "center",
  },
  statusBarText: { fontSize: 12, color: "#888888" },
});
