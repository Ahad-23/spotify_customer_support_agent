import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  api,
  computeDefaultBase,
  getActiveApiBase,
  getDetectedHost,
  initApiClient,
  Message,
  setCustomApiBase,
  wsUrl,
} from "../api/client";
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

const COLORS = {
  bg: "#121212",
  surface: "#181818",
  card: "#222222",
  border: "#242424",
  border2: "#333333",
  green: "#1db954",
  white: "#ffffff",
  muted: "#a7a7a7",
  amber: "#fbbf24",
  neutral: "#737373",
  red: "#ef4444",
  redBg: "rgba(239, 68, 68, 0.15)",
};

export default function CustomerChatScreen() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<string>("active_ai");
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [serverUrlInput, setServerUrlInput] = useState(getActiveApiBase());
  const flatListRef = useRef<FlatList>(null);

  const appendMessage = useCallback((msg: Message) => {
    setMessages((prev) =>
      prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]
    );
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
    if (messages.length > 0) {
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [messages, loading]);

  const initSession = useCallback(async () => {
    setInitializing(true);
    setConnectionError(null);
    try {
      await initApiClient();
      setServerUrlInput(getActiveApiBase());

      let id = await AsyncStorage.getItem(SESSION_KEY);
      let sessionData = null;

      if (id) {
        try {
          sessionData = await api.getSession(id);
        } catch {
          id = null;
        }
      }

      if (!id || !sessionData) {
        const created = await api.createSession();
        id = created.id;
        await AsyncStorage.setItem(SESSION_KEY, id);
        sessionData = created;
      }

      setSessionId(id);
      setMessages(sessionData.messages ?? []);
      setStatus(sessionData.status);
      setConnectionError(null);
    } catch (err: any) {
      console.warn("[CustomerChatScreen] Init failed:", err.message);
      setConnectionError(err.message || "Cannot reach support backend");
    } finally {
      setInitializing(false);
    }
  }, []);

  useEffect(() => {
    initSession();
  }, [initSession]);

  async function handleSend(content: string) {
    if (loading || status === "closed") return;
    setLoading(true);
    setConnectionError(null);

    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const created = await api.createSession();
        currentSessionId = created.id;
        setSessionId(created.id);
        await AsyncStorage.setItem(SESSION_KEY, created.id);
      }

      if (connected) {
        send({ content });
      } else {
        await api.sendMessage(currentSessionId, content);
        const session = await api.getSession(currentSessionId);
        setMessages(session.messages ?? []);
        setStatus(session.status);
        setLoading(false);
      }
    } catch (err: any) {
      setLoading(false);
      setConnectionError(err.message || "Failed to send message");
    }
  }

  async function handleNewChat() {
    await AsyncStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setMessages([]);
    setStatus("active_ai");
    await initSession();
  }

  async function handleSaveServerUrl(newUrl: string) {
    await setCustomApiBase(newUrl);
    setServerUrlInput(newUrl);
    setShowConfigModal(false);
    await initSession();
  }

  if (initializing) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color={COLORS.green} />
          <Text style={styles.loadingText}>Connecting to Spotify Support...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const statusConfig =
    status === "hitl_pending"
      ? { label: "Connecting with specialist", dotColor: COLORS.amber }
      : status === "human_active"
      ? { label: "Live with Support Specialist", dotColor: COLORS.green }
      : status === "closed"
      ? { label: "Chat ended", dotColor: COLORS.neutral }
      : { label: "Support Team · Online", dotColor: COLORS.green };

  const inputDisabled = loading || status === "closed";

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.logoBg}>
            <Text style={styles.logoIcon}>♫</Text>
          </View>
          <View>
            <Text style={styles.headerTitle}>Spotify Support</Text>
            <View style={styles.statusRow}>
              <View style={[styles.statusDot, { backgroundColor: statusConfig.dotColor }]} />
              <Text style={styles.statusLabel}>{statusConfig.label}</Text>
            </View>
          </View>
        </View>
        <View style={styles.headerActions}>
          <TouchableOpacity
            style={styles.serverConfigBtn}
            onPress={() => {
              setServerUrlInput(getActiveApiBase());
              setShowConfigModal(true);
            }}
          >
            <Text style={styles.serverConfigText}>⚙️ Server</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.newChatBtn} onPress={handleNewChat}>
            <Text style={styles.newChatText}>New chat</Text>
          </TouchableOpacity>
        </View>
      </View>

      {connectionError && (
        <View style={styles.errorBanner}>
          <View style={styles.errorBannerContent}>
            <Text style={styles.errorBannerTitle}>⚠️ Backend Connection Failed</Text>
            <Text style={styles.errorBannerText} numberOfLines={2}>
              Target: {getActiveApiBase()} ({connectionError})
            </Text>
          </View>
          <View style={styles.errorBannerButtons}>
            <TouchableOpacity style={styles.errorRetryBtn} onPress={initSession}>
              <Text style={styles.errorRetryText}>Retry</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.errorSettingsBtn}
              onPress={() => setShowConfigModal(true)}
            >
              <Text style={styles.errorSettingsText}>Change</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {messages.length === 0 ? (
        <ScrollView contentContainerStyle={styles.emptyContainer}>
          <View style={styles.emptyIconWrapper}>
            <Text style={styles.emptyIconText}>🎧</Text>
          </View>
          <Text style={styles.emptyTitle}>How can we help today?</Text>
          <Text style={styles.emptySubtitle}>
            Ask us anything about your Spotify account, Premium plan, playback,
            or troubleshooting.
          </Text>
          <View style={styles.suggestionsWrapper}>
            {SUGGESTIONS.map((s) => (
              <TouchableOpacity
                key={s}
                style={styles.suggestionChip}
                onPress={() => handleSend(s)}
                activeOpacity={0.75}
              >
                <Text style={styles.suggestionText}>{s}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      ) : (
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <MessageBubble message={item} />}
          contentContainerStyle={styles.messageList}
          onContentSizeChange={() =>
            flatListRef.current?.scrollToEnd({ animated: true })
          }
          ListFooterComponent={
            loading ? (
              <View style={styles.typingRow}>
                <Text style={styles.typingLabel}>Spotify Support</Text>
                <View style={styles.typingBubble}>
                  <ActivityIndicator size="small" color={COLORS.green} />
                </View>
              </View>
            ) : null
          }
        />
      )}

      <ChatInput
        onSend={handleSend}
        disabled={inputDisabled}
        placeholder={
          status === "closed"
            ? "This conversation is closed"
            : "Type your message or question..."
        }
      />

      <Modal
        visible={showConfigModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowConfigModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Backend Server Connection</Text>
            <Text style={styles.modalSubtitle}>
              Select the appropriate URL for your current device or testing environment:
            </Text>

            <View style={styles.presetList}>
              <TouchableOpacity
                style={styles.presetItem}
                onPress={() => handleSaveServerUrl(computeDefaultBase())}
              >
                <Text style={styles.presetTitle}>🔄 Auto-detected Host ({getDetectedHost()})</Text>
                <Text style={styles.presetSub}>{computeDefaultBase()}</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.presetItem}
                onPress={() => handleSaveServerUrl("http://10.0.2.2:8000")}
              >
                <Text style={styles.presetTitle}>🤖 Android Emulator</Text>
                <Text style={styles.presetSub}>http://10.0.2.2:8000</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.presetItem}
                onPress={() => handleSaveServerUrl("http://localhost:8000")}
              >
                <Text style={styles.presetTitle}>💻 Localhost (iOS / Web Preview)</Text>
                <Text style={styles.presetSub}>http://localhost:8000</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.customUrlLabel}>Custom Server URL:</Text>
            <TextInput
              style={styles.customUrlInput}
              value={serverUrlInput}
              onChangeText={setServerUrlInput}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="http://192.168.x.x:8000"
              placeholderTextColor="#777"
            />

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setShowConfigModal(false)}
              >
                <Text style={styles.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.modalSaveBtn}
                onPress={() => handleSaveServerUrl(serverUrlInput)}
              >
                <Text style={styles.modalSaveText}>Connect</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: COLORS.bg,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    flexDirection: "row",
    gap: 10,
  },
  loadingText: {
    fontSize: 13,
    color: COLORS.muted,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  logoBg: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: COLORS.green,
    alignItems: "center",
    justifyContent: "center",
  },
  logoIcon: {
    color: COLORS.bg,
    fontSize: 16,
    fontWeight: "900",
  },
  headerTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: COLORS.white,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginTop: 2,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusLabel: {
    fontSize: 11,
    color: COLORS.muted,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  serverConfigBtn: {
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: COLORS.border2,
    backgroundColor: "#202020",
  },
  serverConfigText: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.muted,
  },
  newChatBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: COLORS.border2,
  },
  newChatText: {
    fontSize: 12,
    color: COLORS.white,
    fontWeight: "500",
  },
  errorBanner: {
    backgroundColor: COLORS.redBg,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(239, 68, 68, 0.3)",
    paddingHorizontal: 16,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  errorBannerContent: {
    flex: 1,
    marginRight: 10,
  },
  errorBannerTitle: {
    color: COLORS.red,
    fontSize: 12,
    fontWeight: "700",
  },
  errorBannerText: {
    color: "#ffaaaa",
    fontSize: 11,
    marginTop: 2,
  },
  errorBannerButtons: {
    flexDirection: "row",
    gap: 6,
  },
  errorRetryBtn: {
    backgroundColor: COLORS.red,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 4,
  },
  errorRetryText: {
    color: COLORS.white,
    fontSize: 11,
    fontWeight: "700",
  },
  errorSettingsBtn: {
    backgroundColor: "#333",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  errorSettingsText: {
    color: COLORS.white,
    fontSize: 11,
  },
  messageList: {
    paddingVertical: 12,
  },
  typingRow: {
    paddingHorizontal: 16,
    marginVertical: 4,
    alignItems: "flex-start",
  },
  typingLabel: {
    fontSize: 11,
    color: COLORS.muted,
    marginBottom: 4,
  },
  typingBubble: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    borderBottomLeftRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    alignSelf: "flex-start",
  },
  emptyContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
    paddingTop: 60,
  },
  emptyIconWrapper: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "rgba(29,185,84,0.1)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },
  emptyIconText: {
    fontSize: 26,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: COLORS.white,
    marginBottom: 6,
  },
  emptySubtitle: {
    fontSize: 12,
    color: COLORS.muted,
    textAlign: "center",
    maxWidth: 280,
    lineHeight: 18,
    marginBottom: 24,
  },
  suggestionsWrapper: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
  },
  suggestionChip: {
    borderRadius: 99,
    borderWidth: 1,
    borderColor: "#2e2e2e",
    backgroundColor: "#181818",
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  suggestionText: {
    fontSize: 12,
    fontWeight: "500",
    color: "#cccccc",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.75)",
    justifyContent: "center",
    padding: 20,
  },
  modalContent: {
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border2,
    padding: 20,
  },
  modalTitle: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 6,
  },
  modalSubtitle: {
    color: COLORS.muted,
    fontSize: 12,
    marginBottom: 16,
    lineHeight: 16,
  },
  presetList: {
    gap: 8,
    marginBottom: 16,
  },
  presetItem: {
    backgroundColor: "#202020",
    borderWidth: 1,
    borderColor: COLORS.border2,
    borderRadius: 8,
    padding: 10,
  },
  presetTitle: {
    color: COLORS.white,
    fontSize: 13,
    fontWeight: "600",
  },
  presetSub: {
    color: COLORS.green,
    fontSize: 11,
    marginTop: 2,
  },
  customUrlLabel: {
    color: COLORS.muted,
    fontSize: 11,
    marginBottom: 6,
    fontWeight: "600",
  },
  customUrlInput: {
    backgroundColor: "#141414",
    borderWidth: 1,
    borderColor: COLORS.border2,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    color: COLORS.white,
    fontSize: 13,
    marginBottom: 16,
  },
  modalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 10,
  },
  modalCancelBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: "#2a2a2a",
  },
  modalCancelText: {
    color: COLORS.muted,
    fontSize: 13,
  },
  modalSaveBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
    backgroundColor: COLORS.green,
  },
  modalSaveText: {
    color: COLORS.bg,
    fontWeight: "700",
    fontSize: 13,
  },
});
