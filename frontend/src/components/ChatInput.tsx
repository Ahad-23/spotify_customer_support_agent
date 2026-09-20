import { FormEvent, useState } from "react";

interface Props {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({ onSend, disabled, placeholder = "Type a message..." }: Props) {
  const [text, setText] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-[#242424] bg-[#141414] p-3 sm:p-4"
    >
      <div className="mx-auto flex max-w-2xl items-center gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
          placeholder={placeholder}
          className="flex-1 rounded-full border border-[#2e2e2e] bg-[#222222] px-4 py-3 text-sm text-white placeholder-[#787878] outline-none transition focus:border-[#1db954] focus:ring-1 focus:ring-[#1db954] disabled:opacity-40 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="flex items-center justify-center gap-1.5 rounded-full bg-[#1db954] px-5 py-3 text-sm font-semibold text-black transition hover:bg-[#1ed760] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-[#1db954]"
        >
          <span>Send</span>
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </button>
      </div>
    </form>
  );
}
