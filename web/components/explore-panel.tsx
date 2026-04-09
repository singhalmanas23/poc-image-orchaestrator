"use client";

import { useMemo, useState } from "react";
import { motion } from "motion/react";

import {
  imageUrlOf,
  modelOf,
  providerOf,
} from "@/lib/api";
import type { OrchestratorImage } from "@/lib/types";
import { ChannelHeader } from "./channel-header";

interface Props {
  history: OrchestratorImage[];
  selected: OrchestratorImage | null;
  onSelect: (img: OrchestratorImage) => void;
  onRefresh: () => void;
}

export function ExplorePanel({ history, selected, onSelect, onRefresh }: Props) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return history;
    return history.filter((h) => {
      const hay = [
        h.user_prompt,
        h.optimized_prompt,
        modelOf(h),
        providerOf(h),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [history, query]);

  return (
    <section className="flex min-h-0 flex-col border-r border-line/80 bg-ink-800/40">
      <ChannelHeader index="01" title="explore" badge={`${history.length} latents`}>
        <button
          onClick={onRefresh}
          className="focus-ring border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-bone-dim transition hover:border-saffron hover:text-saffron"
        >
          sync
        </button>
      </ChannelHeader>

      {/* search */}
      <div className="border-b border-line/60 px-5 py-3">
        <label className="flex items-center gap-2 border-b border-line/0 pb-1 transition focus-within:border-saffron">
          <span className="font-mono text-[11px] text-bone-mute">/</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="filter latents…"
            className="focus-ring w-full bg-transparent font-mono text-[12px] text-bone placeholder:text-bone-mute focus:outline-none"
          />
        </label>
      </div>

      <div className="scroll min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {filtered.length === 0 && <EmptyState hasHistory={history.length > 0} />}

        <ul className="space-y-3">
          {filtered.map((img, i) => (
            <HistoryCard
              key={(img.image_id ?? "i") + "-" + i}
              img={img}
              active={
                !!selected &&
                ((selected.image_id && selected.image_id === img.image_id) ||
                  imageUrlOf(selected) === imageUrlOf(img))
              }
              onClick={() => onSelect(img)}
              index={i}
            />
          ))}
        </ul>
      </div>
    </section>
  );
}

function HistoryCard({
  img,
  active,
  onClick,
  index,
}: {
  img: OrchestratorImage;
  active: boolean;
  onClick: () => void;
  index: number;
}) {
  const url = imageUrlOf(img);
  const model = modelOf(img) ?? "—";
  const provider = providerOf(img);
  const cost = img.cost != null ? `$${img.cost.toFixed(3)}` : "—";

  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <button
        onClick={onClick}
        className={`crosshair group relative w-full border bg-ink-700/60 p-2 text-left transition ${
          active
            ? "border-saffron shadow-[0_0_0_1px_rgba(244,163,64,0.25)]"
            : "border-line/70 hover:border-bone-mute"
        }`}
      >
        <span className="ch-bl" />
        <span className="ch-br" />

        <div className="flex gap-3">
          <div className="relative h-16 w-16 shrink-0 overflow-hidden border border-line bg-ink-900 bg-grid-fine">
            {url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={url}
                alt={img.user_prompt ?? "latent"}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center font-mono text-[9px] text-bone-mute">
                ∅
              </div>
            )}
            <div className="pointer-events-none absolute inset-0 ring-1 ring-inset ring-bone/5" />
          </div>

          <div className="min-w-0 flex-1">
            <p className="line-clamp-2 font-display text-[13px] leading-snug text-bone">
              {img.user_prompt ?? img.optimized_prompt ?? "untitled"}
            </p>
            <div className="mt-1.5 flex items-center justify-between gap-2 font-mono text-[9px] uppercase tracking-widest text-bone-mute">
              <span className="truncate">
                {model}
                {provider ? ` · ${provider}` : ""}
              </span>
              <span className="text-saffron/80">{cost}</span>
            </div>
          </div>
        </div>
      </button>
    </motion.li>
  );
}

function EmptyState({ hasHistory }: { hasHistory: boolean }) {
  return (
    <div className="border border-dashed border-line/80 px-4 py-10 text-center">
      <div className="mx-auto mb-3 h-8 w-8 border border-line/80" />
      <p className="font-display text-[15px] leading-tight text-bone-dim">
        {hasHistory ? "no matches" : "your latents will live here"}
      </p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-bone-mute">
        {hasHistory ? "try a different filter" : "compose · 02"}
      </p>
    </div>
  );
}
