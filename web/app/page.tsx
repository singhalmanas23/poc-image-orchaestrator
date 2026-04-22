"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";

import { editImage, fetchHistory, generateImage, imageUrlOf } from "@/lib/api";
import type { OrchestratorImage, Priority } from "@/lib/types";
import { ExplorePanel } from "@/components/explore-panel";
import { ComposePanel } from "@/components/compose-panel";
import { RefinePanel } from "@/components/refine-panel";

export default function Page() {
  const [history, setHistory] = useState<OrchestratorImage[]>([]);
  const [selected, setSelected] = useState<OrchestratorImage | null>(null);

  const [generating, setGenerating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [prompt, setPrompt] = useState("");
  const [priority, setPriority] = useState<Priority>("quality");
  const [transparentBg, setTransparentBg] = useState(true);
  const [multiView, setMultiView] = useState(false);

  const [instruction, setInstruction] = useState("");
  const [editPriority, setEditPriority] = useState<Priority>("quality");
  const [lastSubmittedPrompt, setLastSubmittedPrompt] = useState("");
  const [generateTrigger, setGenerateTrigger] = useState(0);

  const [clock, setClock] = useState("");

  // live UTC clock for the header
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      const hh = d.getUTCHours().toString().padStart(2, "0");
      const mm = d.getUTCMinutes().toString().padStart(2, "0");
      const ss = d.getUTCSeconds().toString().padStart(2, "0");
      setClock(`${hh}:${mm}:${ss} UTC`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      const res = await fetchHistory(24);
      setHistory(res.images ?? []);
    } catch (e) {
      // backend may not be live yet; surface a soft hint
      setError((prev) => prev ?? `history offline — ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  const onGenerate = useCallback(async () => {
    if (!prompt.trim() || generating) return;
    const submittedPrompt = prompt.trim();
    setLastSubmittedPrompt(submittedPrompt);
    setGenerateTrigger((n) => n + 1);
    setError(null);
    setGenerating(true);
    try {
      const res = await generateImage(
        submittedPrompt,
        priority,
        transparentBg,
        multiView,
      );
      if (res.error) {
        setError(res.error);
      } else {
        setSelected({
          ...res,
          user_prompt: submittedPrompt,
        });
        await refreshHistory();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }, [prompt, priority, transparentBg, multiView, generating, refreshHistory]);

  const onEdit = useCallback(
    async (override?: string) => {
      const text = (override ?? instruction).trim();
      if (!text || editing || !selected) return;
      setError(null);
      setEditing(true);
      try {
        const res = await editImage({
          instruction: text,
          image_id: selected.image_id ?? null,
          image_url: imageUrlOf(selected),
          priority: editPriority,
        });
        if (res.error) {
          setError(res.error);
        } else {
          setSelected(res);
          setInstruction("");
          await refreshHistory();
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setEditing(false);
      }
    },
    [instruction, editing, selected, editPriority, refreshHistory],
  );

  const status = useMemo(() => {
    if (generating) return { label: "synthesising", tone: "live" as const };
    if (editing) return { label: "refining", tone: "live" as const };
    if (error) return { label: "fault", tone: "warn" as const };
    return { label: "online", tone: "ok" as const };
  }, [generating, editing, error]);

  return (
    <div className="relative z-10 flex min-h-screen flex-col">
      {/* ─────────────────── header ─────────────────── */}
      <header className="flex items-center justify-between border-b border-line/80 bg-ink-900/60 px-6 py-3 backdrop-blur">
        <div className="flex items-center gap-4">
          <Mark />
          <div className="hidden flex-col leading-tight md:flex">
            <span className="label text-bone-dim">orchestrator / img</span>
            <span className="font-mono text-[11px] text-bone-mute">
              intent → optimal model → image
            </span>
          </div>
        </div>

        <div className="hidden items-center gap-6 lg:flex">
          <HeaderStat k="palette" v="saffron · bone · ink" />
          <HeaderStat k="models" v="9 routed" />
          <HeaderStat k="version" v="0.1.0" />
        </div>

        <div className="flex items-center gap-4">
          <StatusPill label={status.label} tone={status.tone} />
          <span className="font-mono text-[11px] tracking-wider text-bone-dim">
            {clock || "—"}
          </span>
        </div>
      </header>

      {/* ─────────────────── main 3-channel grid ─────────────────── */}
      <main className="grid flex-1 grid-cols-1 lg:grid-cols-[340px_minmax(0,1fr)_400px]">
        <ExplorePanel
          history={history}
          selected={selected}
          onSelect={setSelected}
          onRefresh={refreshHistory}
        />
        <ComposePanel
          selected={selected}
          prompt={prompt}
          submittedPrompt={lastSubmittedPrompt}
          generateTrigger={generateTrigger}
          setPrompt={setPrompt}
          priority={priority}
          setPriority={setPriority}
          transparentBg={transparentBg}
          setTransparentBg={setTransparentBg}
          multiView={multiView}
          setMultiView={setMultiView}
          onGenerate={onGenerate}
          generating={generating}
          error={error}
        />
        <RefinePanel
          selected={selected}
          instruction={instruction}
          setInstruction={setInstruction}
          priority={editPriority}
          setPriority={setEditPriority}
          onEdit={onEdit}
          editing={editing}
        />
      </main>

      {/* ─────────────────── footer rail ─────────────────── */}
      <footer className="flex items-center justify-between border-t border-line/80 bg-ink-900/60 px-6 py-2 font-mono text-[10px] uppercase tracking-widest text-bone-mute">
        <div className="flex items-center gap-5">
          <span>↵ generate</span>
          <span>⌘↵ refine</span>
          <span>↑↓ history</span>
        </div>
        <div className="hidden items-center gap-5 md:flex">
          <span>palette · 01</span>
          <span>fraunces × jetbrains mono</span>
          <span>built for routing</span>
        </div>
      </footer>
    </div>
  );
}

/* ────────────────────── small header pieces ────────────────────── */

function Mark() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="flex items-center gap-2"
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 22 22"
        fill="none"
        className="text-saffron"
        aria-hidden
      >
        <rect
          x="0.75"
          y="0.75"
          width="20.5"
          height="20.5"
          stroke="currentColor"
          strokeWidth="1"
        />
        <path
          d="M3 11 H19 M11 3 V19 M5 5 L17 17 M17 5 L5 17"
          stroke="currentColor"
          strokeWidth="0.6"
        />
        <circle cx="11" cy="11" r="3.4" fill="currentColor" />
      </svg>
      <span className="font-display text-[18px] tracking-tightest text-bone">
        orchestrator
      </span>
    </motion.div>
  );
}

function HeaderStat({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="label text-bone-mute">{k}</span>
      <span className="font-mono text-[11px] text-bone-dim">{v}</span>
    </div>
  );
}

function StatusPill({
  label,
  tone,
}: {
  label: string;
  tone: "ok" | "warn" | "live";
}) {
  const dotColor =
    tone === "ok"
      ? "bg-saffron"
      : tone === "warn"
        ? "bg-saffron-deep"
        : "bg-saffron";
  return (
    <div className="flex items-center gap-2 border border-line/80 px-2.5 py-1">
      <span
        className={`relative inline-block h-1.5 w-1.5 rounded-full ${dotColor}`}
      >
        <span
          className={`absolute inset-0 animate-pulseDot rounded-full ${dotColor}`}
        />
      </span>
      <span className="font-mono text-[10px] uppercase tracking-widest text-bone-dim">
        {label}
      </span>
    </div>
  );
}
