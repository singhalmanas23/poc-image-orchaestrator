"use client";

import type { Priority } from "@/lib/types";

const ITEMS: { value: Priority; label: string }[] = [
  { value: "quality", label: "quality" },
  { value: "speed", label: "speed" },
  { value: "cost", label: "cost" },
];

export function PrioritySwitch({
  value,
  onChange,
}: {
  value: Priority;
  onChange: (v: Priority) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="label">priority</span>
      <div className="flex border border-line/80">
        {ITEMS.map((it) => {
          const active = it.value === value;
          return (
            <button
              key={it.value}
              type="button"
              onClick={() => onChange(it.value)}
              className={`focus-ring border-r border-line/60 px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest transition last:border-r-0 ${
                active
                  ? "bg-saffron text-ink-900"
                  : "text-bone-dim hover:text-bone"
              }`}
            >
              {it.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
