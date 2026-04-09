export type Priority = "quality" | "speed" | "cost";

export interface OrchestratorImage {
  success?: boolean;
  image_url?: string | null;
  output_image_url?: string | null;
  image_id?: string | null;
  model_used?: string | null;
  selected_model?: string | null;
  provider?: string | null;
  selected_provider?: string | null;
  reasoning?: string | null;
  selection_reasoning?: string | null;
  optimized_prompt?: string | null;
  user_prompt?: string | null;
  cost?: number | null;
  latency_ms?: number | null;
  created_at?: string | null;
  transparent_background?: boolean | null;
  error?: string | null;
}

export interface HistoryResponse {
  images: OrchestratorImage[];
}
