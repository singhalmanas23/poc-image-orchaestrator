"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";

import {
  clarifyPrompt,
  editImage,
  fetchHistory,
  generateImage,
  imageUrlOf,
} from "@/lib/api";
import type { ClarifyQA, OrchestratorImage, Priority } from "@/lib/types";
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

  // clarifying-question flow (runs before image generation)
  const [clarifyStarted, setClarifyStarted] = useState(false);
  const [clarifyLoading, setClarifyLoading] = useState(false);
  const [clarifyDone, setClarifyDone] = useState(false);
  const [clarifyError, setClarifyError] = useState<string | null>(null);
  const [clarifyReasoning, setClarifyReasoning] = useState<string | null>(null);
  const [clarifyQA, setClarifyQA] = useState<ClarifyQA[]>([]);
  const [currentQuestions, setCurrentQuestions] = useState<string[]>([]);
  const [currentAnswers, setCurrentAnswers] = useState<string[]>([]);
  const [clarifyMinRounds, setClarifyMinRounds] = useState(5);
  const [clarifyMaxRounds, setClarifyMaxRounds] = useState(8);

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

  const resetClarify = useCallback(() => {
    setClarifyStarted(false);
    setClarifyLoading(false);
    setClarifyDone(false);
    setClarifyError(null);
    setClarifyReasoning(null);
    setClarifyQA([]);
    setCurrentQuestions([]);
    setCurrentAnswers([]);
    setClarifyMinRounds(5);
    setClarifyMaxRounds(8);
  }, []);

  const runClarify = useCallback(
    async (basePrompt: string, qa: ClarifyQA[]) => {
      setClarifyLoading(true);
      setClarifyError(null);
      try {
        const res = await clarifyPrompt({ prompt: basePrompt, qa });
        setCurrentQuestions(res.questions ?? []);
        setCurrentAnswers((res.questions ?? []).map(() => ""));
        setClarifyDone(!!res.done);
        setClarifyReasoning(res.reasoning ?? null);
        if (typeof res.min_rounds === "number") setClarifyMinRounds(res.min_rounds);
        if (typeof res.max_rounds === "number") setClarifyMaxRounds(res.max_rounds);
        if (res.error) setClarifyError(res.error);
      } catch (e) {
        setClarifyError((e as Error).message);
        setCurrentQuestions([]);
        setCurrentAnswers([]);
      } finally {
        setClarifyLoading(false);
      }
    },
    [],
  );

  const onStartClarify = useCallback(async () => {
    if (!prompt.trim() || generating || clarifyLoading || clarifyStarted) return;
    setError(null);
    setClarifyStarted(true);
    setClarifyQA([]);
    await runClarify(prompt.trim(), []);
  }, [prompt, generating, clarifyLoading, clarifyStarted, runClarify]);

  const onAskMore = useCallback(async () => {
    if (!clarifyStarted || clarifyLoading || generating) return;
    const nextQA: ClarifyQA[] = [
      ...clarifyQA,
      ...currentQuestions.map((q, i) => ({
        question: q,
        answer: (currentAnswers[i] ?? "").trim(),
      })),
    ];
    setClarifyQA(nextQA);
    setCurrentQuestions([]);
    setCurrentAnswers([]);
    await runClarify(prompt.trim(), nextQA);
  }, [
    clarifyStarted,
    clarifyLoading,
    generating,
    clarifyQA,
    currentQuestions,
    currentAnswers,
    prompt,
    runClarify,
  ]);

  const buildEnrichedPrompt = useCallback(
    (base: string, qa: ClarifyQA[]): string => {
      if (qa.length === 0) return base;
      const block = qa
        .filter((p) => p.question && p.answer)
        .map((p, i) => `  ${i + 1}. ${p.question}\n     → ${p.answer}`)
        .join("\n");
      if (!block) return base;
      return `${base}\n\nAdditional product details from briefing:\n${block}`;
    },
    [],
  );

  const onFinalize = useCallback(async () => {
    if (!clarifyStarted || generating || clarifyLoading) return;
    const base = prompt.trim();
    if (!base) return;

    const mergedQA: ClarifyQA[] = [
      ...clarifyQA,
      ...currentQuestions.map((q, i) => ({
        question: q,
        answer: (currentAnswers[i] ?? "").trim(),
      })),
    ].filter((p) => p.question);

    const enriched = buildEnrichedPrompt(base, mergedQA);

    setLastSubmittedPrompt(base);
    setGenerateTrigger((n) => n + 1);
    setError(null);
    setGenerating(true);
    try {
      const res = await generateImage(
        enriched,
        priority,
        transparentBg,
        multiView,
      );
      if (res.error) {
        setError(res.error);
      } else {
        setSelected({
          ...res,
          user_prompt: base,
        });
        await refreshHistory();
        resetClarify();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }, [
    clarifyStarted,
    generating,
    clarifyLoading,
    prompt,
    clarifyQA,
    currentQuestions,
    currentAnswers,
    buildEnrichedPrompt,
    priority,
    transparentBg,
    multiView,
    refreshHistory,
    resetClarify,
  ]);

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
          onStartClarify={onStartClarify}
          onAskMore={onAskMore}
          onFinalize={onFinalize}
          onCancelClarify={resetClarify}
          clarifyStarted={clarifyStarted}
          clarifyLoading={clarifyLoading}
          clarifyDone={clarifyDone}
          clarifyError={clarifyError}
          clarifyReasoning={clarifyReasoning}
          clarifyQA={clarifyQA}
          currentQuestions={currentQuestions}
          currentAnswers={currentAnswers}
          setCurrentAnswers={setCurrentAnswers}
          clarifyMinRounds={clarifyMinRounds}
          clarifyMaxRounds={clarifyMaxRounds}
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
          <span>↵ start briefing</span>
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
