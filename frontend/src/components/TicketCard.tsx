import type { HitlTicket } from "../api/client";

interface Props {
  ticket: HitlTicket;
  selected: boolean;
  onSelect: () => void;
  onClaim?: () => void;
}

const priorityStyles: Record<string, string> = {
  Urgent: "bg-red-950/60 text-red-400 border-red-800/60",
  High: "bg-amber-950/60 text-amber-400 border-amber-800/60",
  Standard: "bg-[#282828] text-[#cccccc] border-[#383838]",
};

export default function TicketCard({ ticket, selected, onSelect, onClaim }: Props) {
  const priorityClass = priorityStyles[ticket.priority] || priorityStyles.Standard;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-xl border p-3.5 text-left transition ${
        selected
          ? "border-[#1db954] bg-[#262626] shadow-md"
          : "border-[#2e2e2e] bg-[#181818] hover:border-[#404040] hover:bg-[#202020]"
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-mono text-[#8e8e8e]">{ticket.ticket_id}</span>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${priorityClass}`}>
          {ticket.priority}
        </span>
      </div>
      <p className="mb-1 truncate text-sm font-semibold text-white">
        {ticket.customer_name || "Spotify User"}
      </p>
      <p className="line-clamp-2 text-xs text-[#a0a0a0]">
        {ticket.last_message || (ticket.handoff_data.customer_query as string) || "No message"}
      </p>
      {ticket.status === "pending" && onClaim && (
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.stopPropagation();
            onClaim();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.stopPropagation();
              onClaim();
            }
          }}
          className="mt-2.5 inline-flex items-center gap-1 text-xs font-semibold text-[#1db954] hover:underline"
        >
          Take over conversation →
        </span>
      )}
      {ticket.status === "claimed" && ticket.claimed_by && (
        <p className="mt-2 text-xs text-[#8e8e8e]">Handled by {ticket.claimed_by}</p>
      )}
    </button>
  );
}
