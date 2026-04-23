"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";

import {
  fetchEditProbes,
  imageUrlOf,
  modelOf,
  providerOf,
  reasoningOf,
} from "@/lib/api";
import type { OrchestratorImage, Priority, ProbeCategory } from "@/lib/types";
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

const PROBE_CATEGORIES_FALLBACK: ProbeCategory[] = [
  {
    title: "shift background",
    options: [
      { label: "dusk gradient", instruction: "shift the background to a warm dusk gradient" },
      { label: "clean white", instruction: "replace the background with a clean white studio backdrop" },
      { label: "dark studio", instruction: "change the background to a dark moody studio setting" },
    ],
  },
  {
    title: "adjust material finish",
    options: [
      { label: "matte", instruction: "apply a matte finish to the main material" },
      { label: "glossy", instruction: "apply a glossy finish to the main material" },
      { label: "brushed texture", instruction: "add a brushed texture to the surface" },
    ],
  },
  {
    title: "change accent tone",
    options: [
      { label: "brass accents", instruction: "swap hardware and accent details to a warm brass tone" },
      { label: "matte black", instruction: "change metal and accent details to matte black" },
      { label: "chrome", instruction: "swap accents to a polished chrome finish" },
    ],
  },
  {
    title: "remove distractions",
    options: [
      { label: "remove logo", instruction: "remove any visible logo or branding from the product" },
      { label: "remove watermark", instruction: "remove any watermark or overlay text from the image" },
      { label: "clean shadows", instruction: "clean up stray shadows and reflections for a neater look" },
    ],
  },
];

// Curated 12-color recolor palette
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

// Module-scoped cache keyed by image_id
const probesCache = new Map<string, ProbeCategory[]>();

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
  const [probeCategories, setProbeCategories] = useState<ProbeCategory[]>(PROBE_CATEGORIES_FALLBACK);
  const [probesLoading, setProbesLoading] = useState(false);
  const probesAbortRef = useRef<AbortController | null>(null);

  // Track selected option per category: { categoryTitle: optionInstruction }
  const [probeSelections, setProbeSelections] = useState<Record<string, string>>({});

  const loadProbes = useCallback(
    (image: OrchestratorImage | null, bustCache: boolean) => {
      const sourcePrompt = image?.user_prompt ?? image?.optimized_prompt ?? "";
      if (!image || !sourcePrompt || sourcePrompt.trim().length < 3) {
        setProbeCategories(PROBE_CATEGORIES_FALLBACK);
        setProbeSelections({});
        return;
      }
      const id = image.image_id ?? null;
      if (!bustCache && id && probesCache.has(id)) {
        setProbeCategories(probesCache.get(id)!);
        setProbeSelections({});
        setProbesLoading(false);
        return;
      }
      probesAbortRef.current?.abort();
      const controller = new AbortController();
      probesAbortRef.current = controller;
      setProbesLoading(true);
      setProbeSelections({});
      fetchEditProbes({
        prompt: sourcePrompt,
        count: 4,
        signal: controller.signal,
      })
        .then((res) => {
          if (controller.signal.aborted) return;
          const raw = res.probes && res.probes.length > 0 ? res.probes : PROBE_CATEGORIES_FALLBACK;
          const next: ProbeCategory[] = raw.map((p) => {
            if (typeof p === "string") {
              return { title: p, options: [{ label: "apply", instruction: p }] };
            }
            return p as ProbeCategory;
          });
          if (id) probesCache.set(id, next);
          setProbeCategories(next);
        })
        .catch((err) => {
          if (controller.signal.aborted) return;
          if (err?.name !== "AbortError") {
            setProbeCategories(PROBE_CATEGORIES_FALLBACK);
            setProbeSelections({});
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setProbesLoading(false);
        });
    },
    [],
  );

  useEffect(() => {
    loadProbes(selected, false);
    return () => probesAbortRef.current?.abort();
  }, [loadProbes, selected?.image_id, selected?.user_prompt, selected?.optimized_prompt]);

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

  const handleProbeApply = (category: ProbeCategory) => {
    const selectedInstruction = probeSelections[category.title];
    if (!selectedInstruction || !selected) return;

    const option = category.options.find((o) => o.instruction === selectedInstruction);
    const editInstruction = option
      ? `${category.title}: ${option.instruction}`
      : selectedInstruction;

    setInstruction(editInstruction);
    onEdit(editInstruction);
  };

  const handleApplyAll = () => {
    if (!selected) return;
    const parts: string[] = [];
    for (const cat of probeCategories) {
      const sel = probeSelections[cat.title];
      if (!sel) continue;
      const option = cat.options.find((o) => o.instruction === sel);
      parts.push(option ? `${cat.title}: ${option.instruction}` : sel);
    }
    if (parts.length === 0) return;
    const combined = parts.join("; ");
    setInstruction(combined);
    onEdit(combined);
  };

  const hasAnySelection = Object.values(probeSelections).some((v) => v !== "");

  return (
    <section className="flex min-h-0 flex-col bg-ink-800/40">
      <ChannelHeader index="03" title="refine" badge="instruction">
        <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
          {selected ? "ready" : "no target"}
        </span>
      </ChannelHeader>

      <div className="scroll min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {/* selected target preview */}
        <div className="mb-3">
          <div className="mb-1.5 flex items-center justify-between">
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
            <div className="mt-1.5 grid grid-cols-2 gap-2 font-mono text-[10px] uppercase tracking-widest text-bone-mute">
              <span className="truncate">model · {model ?? "—"}</span>
              <span className="truncate text-right">
                {provider ?? "—"}
              </span>
            </div>
          )}
        </div>

        {/* instruction — right below image */}
        <div className="mb-3">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="label">instruction · 03.b</span>
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
              rows={3}
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

        {/* palette · 03.c — click to recolor */}
        <div className="mb-3">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="label">palette · 03.c</span>
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
                  className="focus-ring group relative flex items-center gap-2 bg-ink-800 px-2 py-1.5 transition hover:bg-ink-700 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <span
                    aria-hidden
                    className="block h-4 w-4 shrink-0 border border-bone/10 transition group-hover:scale-110 group-hover:border-bone/30"
                    style={{ backgroundColor: c.hex }}
                  />
                  <span className="truncate font-mono text-[9px] uppercase tracking-widest text-bone-dim group-hover:text-bone">
                    {c.name}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* probe categories · 03.d */}
        {selected && (
          <div className="mb-3">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="label">probes · 03.d</span>
              <span className="font-mono text-[9px] uppercase tracking-widest text-bone-mute">
                {probesLoading
                  ? "probing…"
                  : probeCategories.length === 0
                    ? "no probes"
                    : `${probeCategories.length} categories`}
              </span>
            </div>

            <div className="space-y-2">
              {probeCategories.map((cat) => (
                <ProbeCategoryRow
                  key={cat.title}
                  category={cat}
                  selectedOption={probeSelections[cat.title] ?? ""}
                  onOptionChange={(instruction) =>
                    setProbeSelections((prev) => ({
                      ...prev,
                      [cat.title]: instruction,
                    }))
                  }
                  disabled={!selected || editing || probesLoading}
                />
              ))}
            </div>

            {hasAnySelection && (
              <button
                type="button"
                disabled={!selected || editing}
                onClick={handleApplyAll}
                className="focus-ring mt-2 w-full border border-saffron bg-saffron/10 px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-saffron transition hover:bg-saffron/20 disabled:cursor-not-allowed disabled:border-line/60 disabled:text-bone-mute/50 disabled:hover:bg-transparent"
              >
                Apply!
              </button>
            )}
          </div>
        )}

        {/* priority + apply */}
        <div className="mb-4 flex items-center justify-between gap-2">
          <PrioritySwitch value={priority} onChange={setPriority} />
        </div>

        <button
          disabled={!selected || !instruction.trim() || editing}
          onClick={() => onEdit()}
          className="focus-ring crosshair group relative flex w-full items-center justify-center gap-3 border border-saffron bg-transparent px-5 py-2.5 font-mono text-[11px] uppercase tracking-widest text-saffron transition hover:bg-saffron/10 disabled:cursor-not-allowed disabled:border-line disabled:text-bone-mute disabled:hover:bg-transparent"
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
          <div className="mt-4 border-t border-line/60 pt-3">
            <div className="label mb-1.5">routing · why</div>
            <p className="font-mono text-[11px] leading-relaxed text-bone-dim">
              {reasoning}
            </p>
          </div>
        )}

        {/* footnote */}
        <div className="mt-4 border-t border-line/60 pt-2 font-mono text-[9px] uppercase leading-relaxed tracking-widest text-bone-mute">
          edits route through specialised models · text → ideogram · mask → flux
          fill · style → flux kontext
        </div>
      </div>
    </section>
  );
}

function ProbeCategoryRow({
  category,
  selectedOption,
  onOptionChange,
  disabled,
}: {
  category: ProbeCategory;
  selectedOption: string;
  onOptionChange: (instruction: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="border border-line/80 bg-ink-700/40 px-3 py-2">
      <span className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-bone-dim">
        {category.title}
      </span>
      <select
        value={selectedOption}
        onChange={(e) => {
          onOptionChange(e.target.value);
        }}
        disabled={disabled || category.options.length === 0}
        aria-label={`pick an option for ${category.title}`}
        className="focus-ring w-full border border-line/80 bg-ink-700/60 px-2 py-1.5 font-mono text-[11px] text-bone outline-none transition hover:border-saffron disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">
          {category.options.length === 0 ? "no options" : "select"}
        </option>
        {category.options.map((opt) => (
          <option key={opt.label} value={opt.instruction}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
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
