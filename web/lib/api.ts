import type {
  EditProbesResponse,
  HistoryResponse,
  OrchestratorImage,
  Priority,
  PromptSuggestionsResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text || path}`);
  }
  return (await res.json()) as T;
}

export async function generateImage(
  prompt: string,
  priority: Priority,
  transparentBackground: boolean,
  multiView: boolean = false,
  numViews: number = 8,
): Promise<OrchestratorImage> {
  return jsonFetch<OrchestratorImage>("/api/generate", {
    method: "POST",
    body: JSON.stringify({
      prompt,
      priority,
      transparent_background: transparentBackground,
      multi_view: multiView,
      num_views: numViews,
    }),
  });
}

export async function editImage(args: {
  instruction: string;
  image_id?: string | null;
  image_url?: string | null;
  priority: Priority;
}): Promise<OrchestratorImage> {
  return jsonFetch<OrchestratorImage>("/api/edit", {
    method: "POST",
    body: JSON.stringify(args),
  });
}

export async function fetchHistory(limit = 24): Promise<HistoryResponse> {
  return jsonFetch<HistoryResponse>(`/api/history?limit=${limit}`);
}

export async function fetchPromptSuggestions(args: {
  prompt: string;
  count?: 4 | 5;
  context?: string | null;
}): Promise<PromptSuggestionsResponse> {
  return jsonFetch<PromptSuggestionsResponse>("/api/prompt-suggestions", {
    method: "POST",
    body: JSON.stringify({
      prompt: args.prompt,
      count: args.count ?? 5,
      context: args.context ?? null,
    }),
  });
}

export async function fetchEditProbes(args: {
  prompt: string;
  count?: number;
  signal?: AbortSignal;
}): Promise<EditProbesResponse> {
  return jsonFetch<EditProbesResponse>("/api/edit-probes", {
    method: "POST",
    body: JSON.stringify({
      prompt: args.prompt,
      count: args.count ?? 4,
    }),
    signal: args.signal,
  });
}

/** Best-effort accessor that handles both api and store shapes. */
export function imageUrlOf(
  img: OrchestratorImage | null | undefined,
): string | null {
  if (!img) return null;
  return img.image_url ?? img.output_image_url ?? null;
}

export function modelOf(
  img: OrchestratorImage | null | undefined,
): string | null {
  if (!img) return null;
  return img.model_used ?? img.selected_model ?? null;
}

export function providerOf(
  img: OrchestratorImage | null | undefined,
): string | null {
  if (!img) return null;
  return img.provider ?? img.selected_provider ?? null;
}

export function reasoningOf(
  img: OrchestratorImage | null | undefined,
): string | null {
  if (!img) return null;
  return img.reasoning ?? img.selection_reasoning ?? null;
}
