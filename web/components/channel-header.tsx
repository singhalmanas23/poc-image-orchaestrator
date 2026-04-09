import type { ReactNode } from "react";

interface Props {
  index: string;
  title: string;
  badge?: string;
  children?: ReactNode;
}

export function ChannelHeader({ index, title, badge, children }: Props) {
  return (
    <div className="border-b border-line/80 bg-ink-800/30">
      <div className="flex items-baseline justify-between px-5 pt-5">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[10px] tracking-widest text-saffron">
            {index}
          </span>
          <h2 className="font-display text-[28px] leading-none tracking-tightest text-bone">
            {title}
          </h2>
        </div>
        {badge && (
          <span className="font-mono text-[10px] uppercase tracking-widest text-bone-mute">
            {badge}
          </span>
        )}
      </div>
      <div className="flex items-center justify-between gap-3 px-5 pb-3 pt-2">
        <div className="rule flex-1" />
        {children}
      </div>
    </div>
  );
}
