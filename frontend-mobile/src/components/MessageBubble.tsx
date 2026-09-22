import React from "react";
import { StyleSheet, Text, View } from "react-native";
import type { Message } from "../api/client";

interface Props {
  message: Message;
}

const roleLabels: Record<string, string> = {
  customer: "You",
  agent: "Spotify Support",
  human_agent: "Support Specialist",
  system: "Notice",
};

// Colours matching the web UI exactly
const COLORS = {
  green: "#1db954",
  surface: "#222222",
  border: "#2e2e2e",
  textMuted: "#a7a7a7",
  textLight: "#b3b3b3",
  textMain: "#f0f0f0",
  black: "#000000",
};

export default function MessageBubble({ message }: Props) {
  const isCustomer = message.role === "customer";
  const isSystem = message.role === "system";
  const isSpecialist = message.role === "human_agent";

  if (isSystem) {
    return (
      <View style={styles.systemWrapper}>
        <View style={styles.systemBubble}>
          <Text style={styles.systemText}>{message.content}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.row, isCustomer ? styles.rowEnd : styles.rowStart]}>
      <View style={[styles.col, isCustomer ? styles.colEnd : styles.colStart]}>
        {/* Role label row */}
        <View style={[styles.labelRow, isCustomer ? styles.labelRowEnd : styles.labelRowStart]}>
          {!isCustomer && (
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>{isSpecialist ? "S" : "♫"}</Text>
            </View>
          )}
          <Text style={styles.roleLabel}>
            {roleLabels[message.role] ?? "Spotify Support"}
          </Text>
        </View>

        {/* Bubble */}
        <View
          style={[
            styles.bubble,
            isCustomer ? styles.bubbleCustomer : styles.bubbleAgent,
          ]}
        >
          <Text
            style={[
              styles.bubbleText,
              isCustomer ? styles.bubbleTextCustomer : styles.bubbleTextAgent,
            ]}
          >
            {message.content}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    marginBottom: 16,
  },
  rowEnd: { justifyContent: "flex-end" },
  rowStart: { justifyContent: "flex-start" },

  col: {
    maxWidth: "85%",
    flexDirection: "column",
  },
  colEnd: { alignItems: "flex-end" },
  colStart: { alignItems: "flex-start" },

  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 5,
    paddingHorizontal: 4,
    gap: 5,
  },
  labelRowEnd: { flexDirection: "row-reverse" },
  labelRowStart: { flexDirection: "row" },

  avatar: {
    height: 16,
    width: 16,
    borderRadius: 8,
    backgroundColor: COLORS.green,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: {
    fontSize: 9,
    fontWeight: "700",
    color: COLORS.black,
  },

  roleLabel: {
    fontSize: 11,
    color: COLORS.textLight,
    fontWeight: "500",
  },

  bubble: {
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  bubbleCustomer: {
    backgroundColor: COLORS.green,
    borderBottomRightRadius: 4,
  },
  bubbleAgent: {
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderBottomLeftRadius: 4,
  },

  bubbleText: {
    fontSize: 14,
    lineHeight: 20,
  },
  bubbleTextCustomer: {
    color: COLORS.black,
    fontWeight: "500",
  },
  bubbleTextAgent: {
    color: COLORS.textMain,
  },

  // System message
  systemWrapper: {
    alignItems: "center",
    paddingVertical: 10,
  },
  systemBubble: {
    backgroundColor: "#181818",
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 99,
    paddingHorizontal: 14,
    paddingVertical: 5,
  },
  systemText: {
    fontSize: 11,
    color: COLORS.textMuted,
  },
});
