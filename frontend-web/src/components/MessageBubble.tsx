import type { Message } from "../api/client";
import MarkdownContent from "./MarkdownContent";

interface Props {
  message: Message;
}

const roleLabels: Record<string, string> = {
  customer: "You",
  agent: "Spotify Support",
  human_agent: "Support Specialist",
  system: "Notice",
};

export default function MessageBubble({ message }: Props) {
  const isCustomer = message.role === "customer";
  const isSystem = message.role === "system";
  const isSpecialist = message.role === "human_agent";

  if (isSystem) {
    return (
      <div className="flex justify-center py-2.5">
        <span className="rounded-full border border-[#2e2e2e] bg-[#181818] px-3.5 py-1 text-xs text-[#a7a7a7]">
          {message.content}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex ${isCustomer ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-[85%] sm:max-w-[78%] flex flex-col ${isCustomer ? "items-end" : "items-start"}`}>
        <div className="mb-1.5 flex items-center gap-1.5 px-1 text-xs text-[#a7a7a7]">
          {!isCustomer && (
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#1db954] text-[9px] font-bold text-black">
              {isSpecialist ? "S" : "♫"}
            </span>
          )}
          <span className="font-medium text-[#b3b3b3]">
            {roleLabels[message.role] || "Spotify Support"}
          </span>
        </div>

        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed transition-colors ${
            isCustomer
              ? "rounded-br-sm bg-[#1db954] text-black font-medium selection:bg-black selection:text-white"
              : "rounded-bl-sm border border-[#2e2e2e] bg-[#222222] text-[#f0f0f0] shadow-sm"
          }`}
        >
          <MarkdownContent
            content={message.content}
            className={isCustomer ? "[&_a]:text-black [&_strong]:text-black [&_code]:bg-black/15 [&_code]:border-black/20" : ""}
          />
        </div>
      </div>
    </div>
  );
}
