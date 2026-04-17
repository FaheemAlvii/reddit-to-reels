/**
 * Reddit Video Engine - API client
 * Author: Faheem Alvi <faheemalvi2000@gmail.com>
 * GitHub: https://github.com/FaheemAlvii
 * License: CC BY-NC 4.0
 */
const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── Types ───────────────────────────────────────────────────────────

export interface PipelineSubStep {
  label: string;
  status: "pending" | "running" | "done" | "error";
  detail?: string;
}

export interface PipelineStep {
  id: string;
  title: string;
  status: "idle" | "running" | "done" | "error";
  detail: string;
  sub_steps?: PipelineSubStep[];
}

export interface PipelineState {
  steps: PipelineStep[];
  is_running: boolean;
  current_post: {
    id: string;
    title: string;
    subreddit: string;
    score: number;
  } | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface RedditPost {
  id: string;
  title: string;
  subreddit: string;
  score: number;
  num_comments: number;
  selftext: string;
  url: string;
  permalink: string;
  age_hours: number;
  over_18: boolean;
  meets_filters: boolean;
  filter_reason: string | null;
  already_used: boolean;
}

export interface VideoRecord {
  id: string;
  title: string;
  subreddit: string;
  score: number;
  num_comments: number;
  status: string;
  created_at: string;
  has_video: boolean;
  has_audio: boolean;
  render_time_s?: number;
  parts?: number;
  file_size_bytes?: number;
  part_files?: string[];
  has_thumbnails?: boolean;
}

export interface Stats {
  videos_today: number;
  posts_scanned: number;
  avg_render_time_s: number;
  success_rate: number;
  total_runs: number;
}

export interface TtsProviderStatus {
  installed: boolean;
  repo_cloned?: boolean;
  model_downloaded?: boolean;
  python_deps?: boolean;
  details: string;
}

export interface TtsVoiceDetail {
  id: string;
  name: string;
  lang: string;
  gender: string;
  has_bgm: boolean;
  type: "wav" | "streaming";
  file: string;
}

export interface TtsModelOption {
  id: string;
  name: string;
  description: string;
  size: string;
}

export interface TtsProvider extends TtsProviderStatus {
  id: string;
  name: string;
  type: "cloud" | "local";
  voices: string[];
  voices_detailed?: TtsVoiceDetail[];
  models?: TtsModelOption[];
  models_downloaded?: string[];
}

export interface FullConfig {
  subreddits: string[];
  request_delay: number;
  filters: {
    min_upvotes: number;
    min_comments: number;
    max_comments: number;
    min_age_hours: number;
    max_age_hours: number;
    allow_nsfw: boolean;
    require_selftext: boolean;
  };
  formatting: {
    default_mode: string;
    max_comments: number;
    min_comment_score: number;
  };
  tts: {
    enabled: boolean;
    provider: string;
    model_size: string;
    main_voice: string;
    use_multiple_voices: boolean;
    comment_voices: string[];
    output_format: string;
    speed: number;
  };
  video: {
    mode: string;
    hw_accel: string;
    use_gpu: boolean;
    auto_cleanup: boolean;
    threads: number;
    engine: string;
    split_duration: number;
    outro_text: string;
    branding: string;
  };
  output: {
    posts_directory: string;
    used_posts_file: string;
  };
  discord: {
    enabled: boolean;
    webhook_url: string;
    upload_media: boolean;
  };
  [key: string]: unknown;
}

// ── API Functions ───────────────────────────────────────────────────

export const api = {
  // Health
  health: () => request<{ status: string }>("/api/health"),

  // Config — full config.json
  getConfig: () => request<FullConfig>("/api/config"),
  updateConfig: (update: Record<string, unknown>) =>
    request<{ success: boolean; config: FullConfig }>("/api/config", {
      method: "PUT",
      body: JSON.stringify(update),
    }),

  // Posts
  discoverPosts: (sort: string = "hot") =>
    request<{ posts: RedditPost[]; total: number }>(`/api/posts/discover?sort=${sort}`),

  // Fetch comments for selection
  fetchPostComments: (params: { url?: string; post_id?: string }) =>
    request<{
      post_id: string;
      title: string;
      comments: Array<{ index: number; author: string; body: string; score: number; char_count: number }>;
    }>("/api/posts/comments", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // Generate from URL
  runPipelineFromUrl: (params: {
    url: string; video_mode: string; format_mode: string; tts_enabled: boolean;
    selected_comments?: number[]; max_comment_chars?: number;
  }) =>
    request<{ started: boolean }>("/api/pipeline/run-url", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // Pipeline
  getPipelineStatus: () => request<PipelineState>("/api/pipeline/status"),
  runPipeline: (params?: { post_id?: string; selected_comments?: number[]; max_comment_chars?: number }) =>
    request<{ started: boolean }>("/api/pipeline/run", {
      method: "POST",
      body: JSON.stringify(params || {}),
    }),
  resetPipeline: () =>
    request<{ success: boolean }>("/api/pipeline/reset", { method: "POST" }),
  cancelPipeline: () =>
    request<{ success: boolean }>("/api/pipeline/cancel", { method: "POST" }),

  // Custom content pipeline
  runPipelineCustom: (params: {
    title: string; content: string; format_mode: string;
    video_mode: string; tts_enabled: boolean;
    comments?: Array<{ author: string; body: string }>;
  }) =>
    request<{ started: boolean }>("/api/pipeline/run-custom", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // Videos
  getVideos: () => request<{ videos: VideoRecord[] }>("/api/videos"),

  // Stats
  getStats: () => request<Stats>("/api/stats"),

  // Used posts
  getUsedPosts: () => request<{ used_posts: string[] }>("/api/used-posts"),

  // Logs
  getLogs: () => request<{ logs: string[] }>("/api/logs"),

  // Video actions
  deleteVideo: (id: string) =>
    request<{ success: boolean }>(`/api/videos/${id}`, { method: "DELETE" }),

  // TTS Provider management
  getTtsProviders: () =>
    request<{ providers: TtsProvider[] }>("/api/tts/providers"),
  checkTtsProvider: (providerId: string) =>
    request<TtsProviderStatus>(`/api/tts/check/${providerId}`),
  installTtsProvider: (providerId: string) =>
    request<{ success: boolean; steps: unknown[]; error?: string }>(`/api/tts/install/${providerId}`, {
      method: "POST",
    }),

  // AI test
  testAiModel: (params: { provider: string; model: string; api_key: string; ollama_url?: string }) =>
    request<{ success: boolean; response: string }>("/api/ai/test", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // AI content generation pipeline
  runPipelineAI: (params: {
    content_style: string; niche: string; custom_topic?: string;
    interactive_format?: string; video_mode: string; tts_enabled: boolean;
  }) =>
    request<{ started: boolean }>("/api/pipeline/run-ai", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // Resume video from audio-only post
  resumeVideo: (post_id: string) =>
    request<{ started: boolean }>("/api/pipeline/resume-video", {
      method: "POST",
      body: JSON.stringify({ post_id }),
    }),
};
