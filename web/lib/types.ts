export type Priority = "quality" | "speed" | "cost";

export interface PromptSuggestionsRequest {
  prompt: string;
  count?: 4 | 5;
  context?: string | null;
}

export interface PromptSuggestionsResponse {
  success: boolean;
  base_prompt: string;
  suggestions: string[];
  reasoning?: string | null;
  error?: string | null;
}

export interface ProbeOption {
  label: string;
  instruction: string;
}

export interface ProbeCategory {
  title: string;
  options: ProbeOption[];
}

export interface EditProbesRequest {
  prompt: string;
  count?: number;
}

export interface EditProbesResponse {
  success: boolean;
  base_prompt: string;
  probes: ProbeCategory[];
  reasoning?: string | null;
  error?: string | null;
}

export interface ViewFrame {
  angle?: string | null;
  degrees?: number | null;
  image_url?: string | null;
  cost?: number | null;
  latency_ms?: number | null;
  error?: string | null;
}

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
  views?: ViewFrame[] | null;
  error?: string | null;
}

export interface HistoryResponse {
  images: OrchestratorImage[];
}
