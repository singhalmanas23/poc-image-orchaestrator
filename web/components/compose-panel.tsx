"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

import {
  fetchPromptSuggestions,
  imageUrlOf,
  modelOf,
  providerOf,
  reasoningOf,
} from "@/lib/api";
import type { OrchestratorImage, Priority } from "@/lib/types";
import { ChannelHeader } from "./channel-header";
import { PrioritySwitch } from "./priority-switch";

interface Props {
  selected: OrchestratorImage | null;
  prompt: string;
  setPrompt: (s: string) => void;
  submittedPrompt: string;
  generateTrigger: number;
  priority: Priority;
  setPriority: (p: Priority) => void;
  transparentBg: boolean;
  setTransparentBg: (v: boolean) => void;
  onGenerate: () => void;
  generating: boolean;
  error: string | null;
}

export function ComposePanel({
  selected,
  prompt,
  setPrompt,
  submittedPrompt,
  generateTrigger,
  priority,
  setPriority,
  transparentBg,
  setTransparentBg,
  onGenerate,
  generating,
  error,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [suggestionsError, setSuggestionsError] = useState<string | null>(null);

  // ↵ to generate, ⌘↵ ignored here (left for refine)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
        if (document.activeElement === taRef.current) {
          e.preventDefault();
          onGenerate();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onGenerate]);

  const url = imageUrlOf(selected);
  const model = modelOf(selected);
  const provider = providerOf(selected);
  const reasoning = reasoningOf(selected);
  const showAlpha = !!selected?.transparent_background;

  useEffect(() => {
    const key = submittedPrompt.trim();
    if (!key || generating) return;

    let cancelled = false;

    const run = async () => {
      setLoadingSuggestions(true);
      setSuggestionsError(null);
      setSuggestions([]);
      setSelectedSuggestion("");

      try {
        const res = await fetchPromptSuggestions({
          prompt: key,
          count: 5,
        });

        if (cancelled) return;
        setSuggestions(Array.isArray(res.suggestions) ? res.suggestions : []);
        if (!res.success && res.error) setSuggestionsError(res.error);
      } catch (e) {
        if (cancelled) return;
        setSuggestions([]);
        setSuggestionsError(
          (e as Error).message || "Failed to load suggestions",
        );
      } finally {
        if (!cancelled) setLoadingSuggestions(false);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [generateTrigger, submittedPrompt, generating]);

  const applySuggestion = (value: string) => {
    if (!value) return;
    const base = prompt.trim();
    const next = base ? `${base}, ${value}` : value;
    setPrompt(next);
    setSelectedSuggestion("");
    taRef.current?.focus();
  };

  return (
    <section className="flex min-h-0 flex-col border-r border-line/80 bg-ink-900/20">
      <ChannelHeader index="02" title="compose" badge="canvas">
        <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
          {selected ? "loaded" : "awaiting intent"}
        </span>
      </ChannelHeader>

      {/* canvas */}
      <div className="relative min-h-0 flex-1 px-8 pt-6">
        <div
          className={`crosshair relative mx-auto aspect-square w-full max-w-[560px] border border-line/80 bg-ink-800 ${
            showAlpha ? "bg-checker" : "bg-grid"
          }`}
        >
          <span className="ch-bl" />
          <span className="ch-br" />

          {/* corner registration marks */}
          <CornerMarks />

          <AnimatePresence mode="wait">
            {url && !generating && (
              <motion.div
                key={url}
                initial={{ opacity: 0, scale: 1.02 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                className="absolute inset-0"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={url}
                  alt={selected?.user_prompt ?? "generated image"}
                  className="h-full w-full object-contain"
                />
              </motion.div>
            )}

            {!url && !generating && (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 flex flex-col items-center justify-center gap-4 px-10 text-center"
              >
                <div className="font-display text-[64px] leading-none tracking-tightest text-bone-mute/40">
                  ∅
                </div>
                <p className="max-w-xs font-display text-[18px] leading-snug text-bone-dim">
                  no latent loaded.
                  <br />
                  describe an image below to begin.
                </p>
                <p className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
                  routing engine · idle
                </p>
              </motion.div>
            )}

            {generating && (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 overflow-hidden"
              >
                <div className="absolute inset-0 bg-grid-fine" />
                <div className="absolute inset-x-0 top-0 h-1/2 animate-scan bg-gradient-to-b from-transparent via-saffron/15 to-transparent" />
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-saffron">
                    brain · analyse
                  </div>
                  <RoutingTrace />
                  <div className="font-mono text-[10px] uppercase tracking-widest text-bone-dim">
                    routing → optimal model
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* selection readout */}
        <div className="mx-auto mt-4 max-w-[560px]">
          <AnimatePresence mode="wait">
            {selected && (
              <motion.div
                key={selected.image_id ?? "sel"}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4 }}
                className="grid grid-cols-4 gap-3 border border-line/70 bg-ink-800/40 p-3"
              >
                <Readout k="model" v={model ?? "—"} accent />
                <Readout k="provider" v={provider ?? "—"} />
                <Readout
                  k="cost"
                  v={
                    selected.cost != null ? `$${selected.cost.toFixed(3)}` : "—"
                  }
                />
                <Readout
                  k="latency"
                  v={
                    selected.latency_ms != null
                      ? `${(selected.latency_ms / 1000).toFixed(1)}s`
                      : "—"
                  }
                />
                {reasoning && (
                  <p className="col-span-4 mt-1 border-t border-line/60 pt-2 font-mono text-[11px] leading-relaxed text-bone-dim">
                    <span className="text-bone-mute">why · </span>
                    {reasoning}
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* prompt dock */}
      <div className="border-t border-line/80 bg-ink-800/40 px-8 py-5">
        <div className="mx-auto max-w-[560px]">
          <div className="mb-2 flex items-center justify-between">
            <span className="label">prompt · 02.a</span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
              {prompt.length} ch · ↵ to generate
            </span>
          </div>

          <div className="crosshair relative border border-line/80 bg-ink-700/60 p-3">
            <span className="ch-bl" />
            <span className="ch-br" />
            <textarea
              ref={taRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="describe the image…  e.g. ‘a moody analog product shot of a brass compass on linen, golden-hour light’"
              className="focus-ring w-full resize-none bg-transparent font-mono text-[13px] leading-relaxed text-bone placeholder:text-bone-mute focus:outline-none"
            />
          </div>

          {error && (
            <p className="mt-2 border border-saffron-deep/60 bg-saffron/5 px-3 py-1.5 font-mono text-[11px] text-saffron">
              ! {error}
            </p>
          )}

          <div className="mt-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="label">image improvements · 02.b</span>
              <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
                {loadingSuggestions
                  ? "loading…"
                  : `${suggestions.length} options`}
              </span>
            </div>

            <select
              value={selectedSuggestion}
              onChange={(e) => {
                const value = e.target.value;
                setSelectedSuggestion(value);
                applySuggestion(value);
              }}
              disabled={loadingSuggestions || suggestions.length === 0}
              className="focus-ring w-full border border-line/80 bg-ink-700/60 px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-bone outline-none transition hover:border-saffron disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="">
                {loadingSuggestions
                  ? "generating suggestions from submitted prompt…"
                  : suggestions.length === 0
                    ? "generate once to get 4-5 prompt improvements"
                    : "select an improvement to append to prompt…"}
              </option>
              {suggestions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>

            {suggestionsError && (
              <p className="mt-1.5 font-mono text-[10px] leading-relaxed text-saffron">
                {suggestionsError}
              </p>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <PrioritySwitch value={priority} onChange={setPriority} />
              <AlphaToggle value={transparentBg} onChange={setTransparentBg} />
            </div>
            <button
              disabled={!prompt.trim() || generating}
              onClick={onGenerate}
              className="focus-ring crosshair group relative flex items-center gap-3 border border-saffron bg-saffron px-5 py-2.5 font-mono text-[11px] uppercase tracking-widest text-ink-900 transition disabled:cursor-not-allowed disabled:border-line disabled:bg-transparent disabled:text-bone-mute"
            >
              <span className="ch-bl" />
              <span className="ch-br" />
              {generating ? "synthesising…" : "generate"}
              {!generating && (
                <span className="font-display text-[16px] leading-none">→</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function AlphaToggle({
  value,
  onChange,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="focus-ring group flex items-center gap-2 border border-line/80 px-2 py-1 transition hover:border-saffron"
      aria-pressed={value}
      title="Generate image with transparent (alpha) background"
    >
      <span className="label">alpha</span>
      <span
        className={`relative inline-flex h-3.5 w-7 items-center border ${
          value ? "border-saffron bg-saffron/20" : "border-line bg-ink-700"
        }`}
      >
        <span
          className={`absolute top-[1px] h-[10px] w-[10px] transition-all ${
            value ? "left-[15px] bg-saffron" : "left-[1px] bg-bone-mute"
          }`}
        />
      </span>
      <span
        className={`font-mono text-[10px] uppercase tracking-widest ${
          value ? "text-saffron" : "text-bone-mute"
        }`}
      >
        {value ? "on" : "off"}
      </span>
    </button>
  );
}

function Readout({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="label">{k}</div>
      <div
        className={`mt-0.5 truncate font-mono text-[12px] ${accent ? "text-saffron" : "text-bone"}`}
      >
        {v}
      </div>
    </div>
  );
}

function CornerMarks() {
  return (
    <>
      {(["tl", "tr", "bl", "br"] as const).map((pos) => (
        <span
          key={pos}
          aria-hidden
          className={`absolute h-3 w-3 border-bone-mute ${
            pos.includes("t") ? "top-2" : "bottom-2"
          } ${pos.includes("l") ? "left-2" : "right-2"}`}
          style={{
            borderTop: pos.includes("t") ? "1px solid" : undefined,
            borderBottom: pos.includes("b") ? "1px solid" : undefined,
            borderLeft: pos.includes("l") ? "1px solid" : undefined,
            borderRight: pos.includes("r") ? "1px solid" : undefined,
          }}
        />
      ))}
    </>
  );
}

function RoutingTrace() {
  const stages = ["analyse", "score", "route", "render"];
  return (
    <div className="flex items-center gap-2">
      {stages.map((s, i) => (
        <motion.div
          key={s}
          initial={{ opacity: 0.2 }}
          animate={{ opacity: [0.2, 1, 0.2] }}
          transition={{
            duration: 1.4,
            delay: i * 0.2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="border border-saffron/40 px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-saffron"
        >
          {s}
        </motion.div>
      ))}
    </div>
  );
}
