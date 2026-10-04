import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, TaskResponse, TaskStep } from "../api/client";

interface DemoTemplate {
  title: string;
  category: "Tickets" | "Dashboard" | "Users" | "Tasks";
  targetUrl: string;
  badge: string;
  badgeColor: string;
  task: string;
  description: string;
}

const DEMO_TEMPLATES: DemoTemplate[] = [
  {
    title: "Continuous Chatbot Support: Ticket #133139",
    category: "Tickets",
    targetUrl: "/scp/tickets.php",
    badge: "Continuous AI Chatbot",
    badgeColor: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    description: "Inspect customer thread from saransh, formulate verified Spotify playlist recovery solution using RAG support brain, and post staff reply.",
    task: "Open osTicket staff control panel at http://localhost:8088/scp, navigate to the open tickets list, open ticket #133139 ('songs missing from my playlist' from saransh), read the conversation thread, generate the Spotify playlist troubleshooting solution using the support agent brain, and post the staff reply.",
  },
  {
    title: "Multi-Turn Follow-up & Resolve Ticket #133139",
    category: "Tickets",
    targetUrl: "/scp/tickets.php",
    badge: "Follow-up & Resolve",
    badgeColor: "bg-teal-500/20 text-teal-400 border-teal-500/30",
    description: "Inspect updated thread on ticket #133139, read customer's follow-up reply, generate the next-step solution or closing confirmation, and mark Resolved once confirmed.",
    task: "Open ticket #133139 on osTicket SCP, read the full conversation thread including customer follow-ups, synthesize the next troubleshooting step or closing resolution without repeating greetings, post the reply, and set ticket status to Resolved if customer confirmed resolution or keep Open if still troubleshooting.",
  },

  {
    title: "Triage & Assign Unassigned Ticket #364877",
    category: "Tickets",
    targetUrl: "/scp/tickets.php",
    badge: "Staff Assignment",
    badgeColor: "bg-sky-500/20 text-sky-400 border-sky-500/30",
    description: "Inspect unassigned ticket #364877 from Dev Soni regarding Premium access, assign to Admin User, and post an entitlement check acknowledgement.",
    task: "Navigate to open tickets queue in osTicket SCP (http://localhost:8088/scp/tickets.php), inspect unassigned ticket #364877 from Dev Soni about 'Upgraded to premium but unable to access', assign the ticket to Admin User, and post an initial entitlement check reply.",
  },
  {
    title: "Audit Billing Ticket #428981 (Internal Note)",
    category: "Tickets",
    targetUrl: "/scp/tickets.php",
    badge: "Internal Staff Note",
    badgeColor: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    description: "Analyze billing dispute thread from Ahad Shaikh, redact payment data, set priority to High, and log an internal staff note summarizing refund requirements.",
    task: "Open ticket #428981 ('Premium payment issue' from Ahad Shaikh) in osTicket SCP, inspect the message thread for billing discrepancies, redact sensitive credit card data, post an internal staff note summarizing the refund requirement, and verify.",
  },
  {
    title: "Audit Helpdesk Department Statistics",
    category: "Dashboard",
    targetUrl: "/scp/dashboard.php",
    badge: "Department Metrics",
    badgeColor: "bg-purple-500/20 text-purple-400 border-purple-500/30",
    description: "Extract opened, overdue, and response time metrics for Support and Maintenance departments from the SCP Dashboard, capturing evidence screenshots.",
    task: "Log into osTicket SCP Dashboard at http://localhost:8088/scp/index.php, view the Statistics table by Department, extract open and overdue ticket counts for Support and Maintenance departments, and capture a verification screenshot.",
  },
  {
    title: "Lookup Customer 'Dev Soni' in User Directory",
    category: "Users",
    targetUrl: "/scp/users.php",
    badge: "Account History",
    badgeColor: "bg-teal-500/20 text-teal-400 border-teal-500/30",
    description: "Search customer directory at /scp/users.php, inspect user profile and linked tickets, verifying user account status.",
    task: "Navigate to the osTicket User Directory at http://localhost:8088/scp/users.php, search for customer 'Dev Soni', inspect their account profile and linked tickets, and take a verification screenshot.",
  },
  {
    title: "Create Staff Maintenance Task",
    category: "Tasks",
    targetUrl: "/scp/tasks.php",
    badge: "Staff Operations",
    badgeColor: "bg-rose-500/20 text-rose-400 border-rose-500/30",
    description: "Create a new internal operational task at /scp/tasks.php?a=add assigned to the Support department for Bluetooth investigation.",
    task: "Navigate to osTicket SCP Tasks (http://localhost:8088/scp/tasks.php?a=add), create a new internal task titled 'Investigate Spotify Android Bluetooth playback glitch reported by users', assign to Support department, set priority to High, and save.",
  },
];

export default function TaskDashboard() {
  const [taskInput, setTaskInput] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [activeTask, setActiveTask] = useState<TaskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [clarificationInput, setClarificationInput] = useState("");
  const [submittingClarification, setSubmittingClarification] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollIntervalRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current !== null) {
      window.clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const pollTask = useCallback(
    async (taskId: string) => {
      try {
        const data = await api.getTask(taskId);
        setActiveTask(data);
        if (
          data.status === "completed" ||
          data.status === "done" ||
          data.status === "failed" ||
          data.status === "awaiting_user"
        ) {
          stopPolling();
          setLoading(false);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to poll task");
        stopPolling();
        setLoading(false);
      }
    },
    [stopPolling]
  );

  const startPolling = useCallback(
    (taskId: string) => {
      stopPolling();
      pollIntervalRef.current = window.setInterval(() => {
        pollTask(taskId);
      }, 1500);
    },
    [pollTask, stopPolling]
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const handleLaunchTask = async (taskText?: string) => {
    const textToRun = (taskText ?? taskInput).trim();
    if (!textToRun || loading) return;

    setError(null);
    setLoading(true);
    setActiveTask(null);
    setClarificationInput("");

    try {
      const resp = await api.createTask(textToRun);
      setActiveTask(resp);
      startPolling(resp.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create task");
      setLoading(false);
    }
  };

  const handleResumeTask = async () => {
    if (!activeTask || !clarificationInput.trim() || submittingClarification) return;

    setSubmittingClarification(true);
    setError(null);

    try {
      const resp = await api.resumeTask(activeTask.id, clarificationInput.trim());
      setActiveTask(resp);
      setClarificationInput("");
      setLoading(true);
      startPolling(resp.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to resume task");
    } finally {
      setSubmittingClarification(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "done":
      case "completed":
        return <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-400">Completed</span>;
      case "failed":
        return <span className="rounded-full bg-red-500/20 px-3 py-1 text-xs font-semibold text-red-400">Failed</span>;
      case "awaiting_user":
        return <span className="rounded-full bg-amber-500/20 px-3 py-1 text-xs font-semibold text-amber-300 animate-pulse">Awaiting Clarification</span>;
      case "verifying":
        return <span className="rounded-full bg-purple-500/20 px-3 py-1 text-xs font-semibold text-purple-300 animate-pulse">Verifying Outcome</span>;
      case "running":
      case "executing":
        return <span className="rounded-full bg-sky-500/20 px-3 py-1 text-xs font-semibold text-sky-400 animate-pulse">Executing Tools</span>;
      default:
        return <span className="rounded-full bg-neutral-800 px-3 py-1 text-xs font-semibold text-neutral-300">Planning</span>;
    }
  };

  const getStepIcon = (step: TaskStep) => {
    switch (step.status) {
      case "done":
        return <span className="text-emerald-400 font-bold text-[10px]">OK</span>;
      case "failed":
        return <span className="text-red-400 font-bold text-[10px]">FAIL</span>;
      case "running":
        return <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />;
      default:
        return <span className="text-neutral-500 font-mono text-[10px]">--</span>;
    }
  };

  const categories = ["All", "Tickets", "Dashboard", "Users", "Tasks"];
  const filteredTemplates = selectedCategory === "All"
    ? DEMO_TEMPLATES
    : DEMO_TEMPLATES.filter((t) => t.category === selectedCategory);

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-sans">
      {/* Top Header */}
      <header className="border-b border-neutral-800 bg-neutral-900/60 backdrop-blur px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-neutral-900 border border-neutral-800 text-emerald-400 shadow-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
                Autonomous Task Worker
                <span className="text-xs font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 rounded-full px-2 py-0.5">
                  osTicket Staff Control Panel (SCP)
                </span>
              </h1>
              <p className="text-xs text-neutral-400">
                End-to-end plan, execute, observe, retry & verify cycle on osTicket Helpdesk
              </p>
            </div>
          </div>

          <nav className="flex items-center gap-4 text-xs font-medium text-neutral-400">
            <Link to="/" className="hover:text-emerald-400 transition-colors">
              Support Chat
            </Link>
            <Link to="/agent" className="hover:text-emerald-400 transition-colors">
              Human Agent Desk
            </Link>
            <span className="h-4 w-px bg-neutral-800" />
            <a
              href="http://localhost:8088/scp/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-semibold"
            >
              Open osTicket SCP ↗
            </a>
          </nav>
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto max-w-7xl p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Task Input & Templates (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {/* Natural Language Prompt Card */}
          <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 shadow-xl">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400 mb-3 flex items-center justify-between">
              <span>Staff Operation Prompt</span>
              <span className="text-[11px] font-normal text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded-md">SCP Autonomous</span>
            </h2>

            <div className="relative">
              <textarea
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                placeholder="Describe what you want the AI worker to achieve in osTicket SCP... e.g., 'Open ticket #133139 from saransh, analyze the missing playlist issue, generate troubleshooting steps with the CBR brain, and submit the staff reply.'"
                rows={5}
                className="w-full resize-none rounded-xl border border-neutral-700/80 bg-neutral-950/80 p-3.5 text-sm text-neutral-100 placeholder-neutral-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
              />
            </div>

            <div className="mt-3 flex items-center justify-between">
              <span className="text-xs text-neutral-500">
                Dispatches to Playwright & osTicket SCP
              </span>
              <button
                onClick={() => handleLaunchTask()}
                disabled={loading || !taskInput.trim()}
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-5 py-2.5 text-xs font-semibold text-neutral-950 shadow-md shadow-emerald-500/20 hover:from-emerald-400 hover:to-teal-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
              >
                {loading ? (
                  <>
                    <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-neutral-950 border-t-transparent" />
                    Executing...
                  </>
                ) : (
                  <>
                    <span>Execute Task</span>
                    <span>→</span>
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-950/30 p-2.5 text-xs text-red-400">
                {error}
              </div>
            )}
          </div>

          {/* Quick Demo Templates */}
          <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 shadow-xl">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400">
                SCP Demo Operations
              </h2>
              <span className="text-[11px] text-neutral-500 font-mono">
                {filteredTemplates.length} workflows
              </span>
            </div>

            {/* Category Filter Tabs */}
            <div className="flex items-center gap-1.5 mb-3.5 pb-2 border-b border-neutral-800/60 overflow-x-auto">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${
                    selectedCategory === cat
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/40"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="flex flex-col gap-3">
              {filteredTemplates.map((tmpl, idx) => (
                <div
                  key={idx}
                  className="group flex flex-col rounded-xl border border-neutral-800/80 bg-neutral-950/40 p-3.5 transition hover:border-emerald-500/50 hover:bg-neutral-900/80"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-xs font-semibold text-neutral-200 group-hover:text-emerald-400">
                          {tmpl.title}
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${tmpl.badgeColor}`}>
                          {tmpl.badge}
                        </span>
                      </div>
                      <p className="text-[11px] text-neutral-400 leading-relaxed mb-2">
                        {tmpl.description}
                      </p>
                      <div className="flex items-center gap-2 text-[10px] font-mono text-neutral-500">
                        <span>Target:</span>
                        <code className="text-neutral-400 bg-neutral-900 px-1.5 py-0.5 rounded">
                          {tmpl.targetUrl}
                        </code>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setTaskInput(tmpl.task);
                        handleLaunchTask(tmpl.task);
                      }}
                      disabled={loading}
                      className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-neutral-800 hover:bg-emerald-500 hover:text-neutral-950 text-neutral-300 px-2.5 py-1.5 text-xs font-medium transition disabled:opacity-50"
                    >
                      <span>Run</span>
                      <span>↗</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Execution Feed, Plan, Verification & Evidence (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {activeTask ? (
            <div className="flex flex-col gap-6">
              {/* Task Overview Card */}
              <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 shadow-xl">
                <div className="flex items-center justify-between border-b border-neutral-800/80 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-neutral-400">
                      Task #{activeTask.id}
                    </span>
                    {getStatusBadge(activeTask.status)}
                  </div>

                  {activeTask.verified !== null && activeTask.verified !== undefined && (
                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-neutral-400">Verification:</span>
                      {activeTask.verified ? (
                        <span className="font-semibold text-emerald-400">PASSED</span>
                      ) : (
                        <span className="font-semibold text-red-400">FAILED</span>
                      )}
                    </div>
                  )}
                </div>

                {activeTask.task && (
                  <div className="mb-3">
                    <div className="text-[11px] uppercase tracking-wider text-neutral-500 font-semibold mb-1">
                      User Request
                    </div>
                    <p className="text-xs text-neutral-300 bg-neutral-950/60 p-2.5 rounded-lg border border-neutral-800/60">
                      {activeTask.task}
                    </p>
                  </div>
                )}

                {/* Clarification Gate (C10) */}
                {activeTask.status === "awaiting_user" && (
                  <div className="mt-4 rounded-xl border border-amber-500/40 bg-amber-950/20 p-4">
                    <div className="flex items-center gap-2 text-xs font-bold text-amber-300 mb-1.5">
                      <span>[Action Required] Clarification Gate</span>
                    </div>
                    <p className="text-xs text-neutral-200 mb-3">
                      {activeTask.clarification || "The agent requires human confirmation before continuing."}
                    </p>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={clarificationInput}
                        onChange={(e) => setClarificationInput(e.target.value)}
                        placeholder="Provide details or approve..."
                        className="flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-amber-400 focus:outline-none"
                      />
                      <button
                        onClick={handleResumeTask}
                        disabled={submittingClarification || !clarificationInput.trim()}
                        className="rounded-lg bg-amber-400 px-4 py-2 text-xs font-bold text-neutral-950 hover:bg-amber-300 disabled:opacity-50"
                      >
                        {submittingClarification ? "Submitting..." : "Resume Worker"}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Execution Plan (C2, C4, C8) */}
              <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 shadow-xl">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-neutral-400 mb-3 flex items-center justify-between">
                  <span>Decomposed Plan & Act-Observe Loop</span>
                  <span className="text-xs font-mono text-neutral-500">
                    {activeTask.plan?.length || 0} steps
                  </span>
                </h3>

                {activeTask.plan && activeTask.plan.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {activeTask.plan.map((step, idx) => (
                      <div
                        key={idx}
                        className={`flex items-start gap-3 rounded-xl border p-3 transition ${
                          step.status === "running"
                            ? "border-sky-500/40 bg-sky-950/20"
                            : step.status === "done"
                            ? "border-neutral-800/60 bg-neutral-950/40"
                            : step.status === "failed"
                            ? "border-red-500/30 bg-red-950/20"
                            : "border-neutral-800/40 bg-neutral-950/20 opacity-70"
                        }`}
                      >
                        <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-900 text-xs">
                          {getStepIcon(step)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-medium text-neutral-200">
                              {step.index + 1}. {step.description}
                            </span>
                            <span className="text-[10px] font-mono text-neutral-500 bg-neutral-900/80 px-1.5 py-0.5 rounded">
                              {step.tool}
                            </span>
                          </div>

                          {step.retries ? (
                            <div className="mt-1 text-[11px] text-amber-400">
                              ↻ Retried {step.retries}x
                            </div>
                          ) : null}

                          {step.result && (
                            <div className="mt-1.5 text-[11px] text-neutral-400 font-mono bg-neutral-950 p-1.5 rounded border border-neutral-900 line-clamp-2">
                              {step.result}
                            </div>
                          )}

                          {step.error && (
                            <div className="mt-1.5 text-[11px] text-red-400 bg-red-950/30 p-1.5 rounded border border-red-900/40">
                              {step.error}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex h-24 items-center justify-center text-xs text-neutral-500">
                    Generating plan...
                  </div>
                )}
              </div>

              {/* Memory & Extracted State (C6) */}
              {activeTask.memory && Object.keys(activeTask.memory).length > 0 && (
                <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 shadow-xl">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-neutral-400 mb-3">
                    Working Memory & Data Extracted
                  </h3>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(activeTask.memory)
                      .filter(([k]) => !k.startsWith("_"))
                      .map(([k, v]) => (
                        <div
                          key={k}
                          className="rounded-lg bg-neutral-950 p-2.5 border border-neutral-800/60"
                        >
                          <div className="text-[10px] font-mono uppercase text-neutral-500">
                            {k}
                          </div>
                          <div className="mt-0.5 font-medium text-neutral-200 truncate">
                            {String(v)}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Completion Summary (C11) */}
              {activeTask.summary && (
                <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 shadow-xl">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-neutral-400 mb-2">
                    Autonomous Execution Summary
                  </h3>
                  <pre className="whitespace-pre-wrap font-mono text-xs text-neutral-300 bg-neutral-950 p-3.5 rounded-xl border border-neutral-800/80 leading-relaxed overflow-x-auto">
                    {activeTask.summary}
                  </pre>
                </div>
              )}

              {/* Evidence Screenshots (C11) */}
              {activeTask.evidence && activeTask.evidence.length > 0 && (
                <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 shadow-xl">
                  <h3 className="text-sm font-semibold uppercase tracking-wider text-neutral-400 mb-3">
                    Evidence Captured ({activeTask.evidence.length})
                  </h3>
                  <div className="flex flex-wrap gap-2 text-xs font-mono text-neutral-400">
                    {activeTask.evidence.map((shot, idx) => (
                      <span
                        key={idx}
                        className="rounded bg-neutral-950 px-2.5 py-1 border border-neutral-800 text-[11px]"
                      >
                        Screenshot: {shot}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Empty State */
            <div className="flex min-h-[380px] flex-col items-center justify-center rounded-2xl border border-dashed border-neutral-800 bg-neutral-900/20 p-8 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-900 text-xs font-bold text-neutral-400 border border-neutral-800 mb-3">
                IDLE
              </div>
              <h3 className="text-sm font-semibold text-neutral-200">
                No Active Autonomous Task
              </h3>
              <p className="mt-1 max-w-sm text-xs text-neutral-500">
                Enter a task on the left or click one of the pre-configured demo scenarios to begin execution against osTicket.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
