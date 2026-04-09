"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";

import { imageUrlOf, modelOf, providerOf, reasoningOf } from "@/lib/api";
import type { OrchestratorImage, Priority } from "@/lib/types";
import { ChannelHeader } from "./channel-header";
import { PrioritySwitch } from "./priority-switch";

interface Props {
  selected: OrchestratorImage | null;
  instruction: string;
  setInstruction: (s: string) => void;
  priority: Priority;
  setPriority: (p: Priority) => void;
  onEdit: (instructionOverride?: string) => void;
  editing: boolean;
}

const PROBE_HINTS = [
  "shift the background to dusk",
  "remove the watermark",
  "make the linen fabric darker",
  "swap brass for matte black",
];

// Curated 12-color recolor palette — distinctive named colors that map cleanly to a
// natural-language edit instruction. Hex values are shown as the swatch fill; the
// brain prompt uses the human name only.
const PALETTE: { name: string; hex: string }[] = [
  { name: "saffron", hex: "#F4A340" },
  { name: "oxblood", hex: "#6E1A1F" },
  { name: "cobalt", hex: "#1B5BB0" },
  { name: "sage", hex: "#8FA786" },
  { name: "plum", hex: "#5C2545" },
  { name: "terracotta", hex: "#C66B3D" },
  { name: "bone", hex: "#EDE6D3" },
  { name: "charcoal", hex: "#1C1C20" },
  { name: "moss", hex: "#4A5D2A" },
  { name: "rust", hex: "#A4441D" },
  { name: "indigo", hex: "#1F2A6E" },
  { name: "cream", hex: "#F5EBD8" },
];

function recolorInstruction(name: string) {
  return `recolor the subject in ${name} tones, keeping the existing shape, material, lighting and composition consistent`;
}

export function RefinePanel({
  selected,
  instruction,
  setInstruction,
  priority,
  setPriority,
  onEdit,
  editing,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);

  // ⌘↵ (or ctrl↵) to apply edit — only when the refine textarea is focused
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        (e.metaKey || e.ctrlKey) &&
        e.key === "Enter" &&
        document.activeElement === taRef.current
      ) {
        e.preventDefault();
        onEdit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onEdit]);

  const url = imageUrlOf(selected);
  const model = modelOf(selected);
  const provider = providerOf(selected);
  const reasoning = reasoningOf(selected);

  return (
    <section className="flex min-h-0 flex-col bg-ink-800/40">
      <ChannelHeader index="03" title="refine" badge="instruction">
        <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
          {selected ? "ready" : "no target"}
        </span>
      </ChannelHeader>

      <div className="scroll min-h-0 flex-1 overflow-y-auto px-5 py-5">
        {/* selected target preview */}
        <div className="mb-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="label">target · 03.a</span>
            {selected?.image_id && (
              <span className="font-mono text-[9px] uppercase tracking-widest text-bone-mute">
                id · {String(selected.image_id).slice(0, 8)}
              </span>
            )}
          </div>

          <div className="crosshair relative aspect-[4/3] border border-line/80 bg-ink-700 bg-grid-fine">
            <span className="ch-bl" />
            <span className="ch-br" />
            <AnimatePresence mode="wait">
              {url ? (
                <motion.img
                  key={url}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  src={url}
                  alt={selected?.user_prompt ?? "target"}
                  className="absolute inset-0 h-full w-full object-cover"
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
                  <div className="font-display text-[36px] leading-none text-bone-mute/40">
                    ⌖
                  </div>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
                    select a latent to refine
                  </p>
                </div>
              )}
            </AnimatePresence>
          </div>

          {selected && (
            <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-[10px] uppercase tracking-widest text-bone-mute">
              <span className="truncate">model · {model ?? "—"}</span>
              <span className="truncate text-right">
                {provider ?? "—"}
              </span>
            </div>
          )}
        </div>

        {/* palette · 03.b — click to recolor */}
        <div className="mb-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="label">palette · 03.b</span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
              click to recolor
            </span>
          </div>
          <div className="crosshair relative grid grid-cols-3 gap-px border border-line/80 bg-line">
            <span className="ch-bl" />
            <span className="ch-br" />
            {PALETTE.map((c) => {
              const disabled = !selected || editing;
              return (
                <button
                  key={c.name}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    const text = recolorInstruction(c.name);
                    setInstruction(text);
                    onEdit(text);
                  }}
                  title={`${c.name} · ${c.hex}`}
                  className="focus-ring group relative flex items-center gap-2 bg-ink-800 px-2 py-2 transition hover:bg-ink-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <span
                    aria-hidden
                    className="block h-5 w-5 shrink-0 border border-bone/10 transition group-hover:scale-110 group-hover:border-bone/30"
                    style={{ backgroundColor: c.hex }}
                  />
                  <span className="truncate font-mono text-[10px] uppercase tracking-widest text-bone-dim group-hover:text-bone">
                    {c.name}
                  </span>
                </button>
              );
            })}
          </div>
          {selected && (
            <p className="mt-1.5 font-mono text-[9px] uppercase tracking-widest text-bone-mute">
              one click → templated recolor edit
            </p>
          )}
        </div>

        {/* instruction */}
        <div className="mb-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="label">instruction · 03.c</span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
              ⌘↵ to apply
            </span>
          </div>

          <div className="crosshair relative border border-line/80 bg-ink-700/60 p-3">
            <span className="ch-bl" />
            <span className="ch-br" />
            <textarea
              ref={taRef}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              rows={4}
              disabled={!selected}
              placeholder={
                selected
                  ? "describe the edit…"
                  : "no target loaded — pick a latent from explore"
              }
              className="focus-ring w-full resize-none bg-transparent font-mono text-[12px] leading-relaxed text-bone placeholder:text-bone-mute focus:outline-none disabled:opacity-50"
            />
          </div>
        </div>

        {/* probes */}
        {selected && (
          <div className="mb-4">
            <div className="label mb-2">probes · 03.d</div>
            <div className="flex flex-wrap gap-1.5">
              {PROBE_HINTS.map((p) => (
                <button
                  key={p}
                  onClick={() => setInstruction(p)}
                  className="focus-ring border border-line/70 bg-ink-700/40 px-2 py-1 font-mono text-[10px] text-bone-dim transition hover:border-saffron hover:text-saffron"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* priority + apply */}
        <div className="mb-5 flex items-center justify-between gap-2">
          <PrioritySwitch value={priority} onChange={setPriority} />
        </div>

        <button
          disabled={!selected || !instruction.trim() || editing}
          onClick={() => onEdit()}
          className="focus-ring crosshair group relative flex w-full items-center justify-center gap-3 border border-saffron bg-transparent px-5 py-3 font-mono text-[11px] uppercase tracking-widest text-saffron transition hover:bg-saffron/10 disabled:cursor-not-allowed disabled:border-line disabled:text-bone-mute disabled:hover:bg-transparent"
        >
          <span className="ch-bl" />
          <span className="ch-br" />
          {editing ? (
            <>
              <Spinner /> refining…
            </>
          ) : (
            <>
              apply edit
              <span className="font-display text-[16px] leading-none">↻</span>
            </>
          )}
        </button>

        {/* reasoning */}
        {reasoning && (
          <div className="mt-5 border-t border-line/60 pt-4">
            <div className="label mb-2">routing · why</div>
            <p className="font-mono text-[11px] leading-relaxed text-bone-dim">
              {reasoning}
            </p>
          </div>
        )}

        {/* footnote */}
        <div className="mt-6 border-t border-line/60 pt-3 font-mono text-[9px] uppercase leading-relaxed tracking-widest text-bone-mute">
          edits route through specialised models · text → ideogram · mask → flux
          fill · style → flux kontext
        </div>
      </div>
    </section>
  );
}

function Spinner() {
  return (
    <motion.span
      animate={{ rotate: 360 }}
      transition={{ duration: 1.2, ease: "linear", repeat: Infinity }}
      className="inline-block h-3 w-3 rounded-full border border-saffron border-t-transparent"
    />
  );
}
