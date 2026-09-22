import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import type { HitlTicket } from "../api/client";

interface Props {
  ticket: HitlTicket;
  selected: boolean;
  onSelect: () => void;
  onClaim?: () => void;
}

const COLORS = {
  green: "#1db954",
  surface: "#181818",
  surfaceSelected: "#262626",
  border: "#2e2e2e",
  borderSelected: "#1db954",
  borderHover: "#404040",
  textWhite: "#ffffff",
  textMono: "#8e8e8e",
  textBody: "#a0a0a0",
  textClaimed: "#8e8e8e",
};

const priorityBg: Record<string, string> = {
  Urgent: "rgba(127,29,29,0.6)",
  High: "rgba(120,53,15,0.6)",
  Standard: "#282828",
};
const priorityText: Record<string, string> = {
  Urgent: "#f87171",
  High: "#fbbf24",
  Standard: "#cccccc",
};

export default function TicketCard({ ticket, selected, onSelect, onClaim }: Props) {
  const bg = priorityBg[ticket.priority] ?? priorityBg.Standard;
  const badgeColor = priorityText[ticket.priority] ?? priorityText.Standard;

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={onSelect}
      style={[
        styles.card,
        selected ? styles.cardSelected : styles.cardDefault,
      ]}
    >
      {/* Top row: ticket ID + priority badge */}
      <View style={styles.topRow}>
        <Text style={styles.ticketId}>{ticket.ticket_id}</Text>
        <View style={[styles.badge, { backgroundColor: bg }]}>
          <Text style={[styles.badgeText, { color: badgeColor }]}>
            {ticket.priority.toUpperCase()}
          </Text>
        </View>
      </View>

      {/* Customer name */}
      <Text style={styles.customerName} numberOfLines={1}>
        {ticket.customer_name ?? "Spotify User"}
      </Text>

      {/* Last message */}
      <Text style={styles.lastMsg} numberOfLines={2}>
        {ticket.last_message ??
          (ticket.handoff_data.customer_query as string) ??
          "No message"}
      </Text>

      {/* Claim action */}
      {ticket.status === "pending" && onClaim && (
        <TouchableOpacity onPress={onClaim} activeOpacity={0.8} style={styles.claimBtn}>
          <Text style={styles.claimText}>Take over conversation →</Text>
        </TouchableOpacity>
      )}

      {/* Claimed by */}
      {ticket.status === "claimed" && ticket.claimed_by && (
        <Text style={styles.claimedBy}>Handled by {ticket.claimed_by}</Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 10,
  },
  cardDefault: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
  },
  cardSelected: {
    backgroundColor: COLORS.surfaceSelected,
    borderColor: COLORS.borderSelected,
  },

  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  ticketId: {
    fontFamily: "monospace",
    fontSize: 11,
    color: COLORS.textMono,
  },
  badge: {
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
  },

  customerName: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.textWhite,
    marginBottom: 4,
  },
  lastMsg: {
    fontSize: 12,
    color: COLORS.textBody,
    lineHeight: 17,
  },

  claimBtn: {
    marginTop: 10,
  },
  claimText: {
    fontSize: 12,
    fontWeight: "600",
    color: COLORS.green,
  },
  claimedBy: {
    marginTop: 8,
    fontSize: 12,
    color: COLORS.textClaimed,
  },
});
