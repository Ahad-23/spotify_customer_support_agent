import React, { useState } from "react";
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

interface Props {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

const COLORS = {
  green: "#1db954",
  greenHover: "#1ed760",
  surface: "#222222",
  border: "#2e2e2e",
  inputBg: "#222222",
  barBg: "#141414",
  barBorder: "#242424",
  textWhite: "#ffffff",
  placeholder: "#787878",
  black: "#000000",
};

export default function ChatInput({
  onSend,
  disabled,
  placeholder = "Type a message...",
}: Props) {
  const [text, setText] = useState("");

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  const canSend = text.trim().length > 0 && !disabled;

  return (
    <View style={styles.bar}>
      <TextInput
        style={[styles.input, disabled && styles.inputDisabled]}
        value={text}
        onChangeText={setText}
        placeholder={placeholder}
        placeholderTextColor={COLORS.placeholder}
        editable={!disabled}
        onSubmitEditing={handleSend}
        returnKeyType="send"
        multiline={false}
      />
      <TouchableOpacity
        style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
        onPress={handleSend}
        disabled={!canSend}
        activeOpacity={0.8}
      >
        <Text style={[styles.sendText, !canSend && styles.sendTextDisabled]}>
          Send
        </Text>
        {/* Arrow icon */}
        <Text style={[styles.arrowIcon, !canSend && styles.sendTextDisabled]}>
          →
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.barBorder,
    backgroundColor: COLORS.barBg,
  },
  input: {
    flex: 1,
    height: 46,
    borderRadius: 23,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.inputBg,
    paddingHorizontal: 16,
    fontSize: 14,
    color: COLORS.textWhite,
  },
  inputDisabled: {
    opacity: 0.4,
  },
  sendBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: COLORS.green,
    paddingHorizontal: 18,
    height: 46,
    borderRadius: 23,
  },
  sendBtnDisabled: {
    opacity: 0.3,
  },
  sendText: {
    fontSize: 14,
    fontWeight: "600",
    color: COLORS.black,
  },
  sendTextDisabled: {
    color: COLORS.black,
  },
  arrowIcon: {
    fontSize: 16,
    color: COLORS.black,
    fontWeight: "700",
  },
});
