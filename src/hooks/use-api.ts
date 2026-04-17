import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, PipelineState } from "@/lib/api";

// ── Health (poll every 10s) ─────────────────────────────────────────
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 10_000,
    retry: 1,
  });
}

// ── Stats (poll every 15s) ──────────────────────────────────────────
export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: api.getStats,
    refetchInterval: 15_000,
  });
}

// ── Config ──────────────────────────────────────────────────────────
export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: api.getConfig,
  });
}

export function useUpdateConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.updateConfig,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["config"] }),
  });
}

// ── Posts (on-demand) ───────────────────────────────────────────────
export function useDiscoverPosts(sort: string = "hot") {
  return useQuery({
    queryKey: ["posts", sort],
    queryFn: () => api.discoverPosts(sort),
    enabled: false,
    staleTime: 60_000,
  });
}

// ── Videos (poll every 10s) ─────────────────────────────────────────
export function useVideos() {
  return useQuery({
    queryKey: ["videos"],
    queryFn: api.getVideos,
    refetchInterval: 10_000,
  });
}

// ── Used Posts ───────────────────────────────────────────────────────
export function useUsedPosts() {
  return useQuery({
    queryKey: ["used-posts"],
    queryFn: api.getUsedPosts,
  });
}

// ── Pipeline (fast poll while running, slow otherwise) ──────────────
export function usePipelineStatus() {
  return useQuery({
    queryKey: ["pipeline"],
    queryFn: api.getPipelineStatus,
    refetchInterval: (query) => {
      const data = query.state.data as PipelineState | undefined;
      return data?.is_running ? 1_500 : 8_000;
    },
  });
}

export function useRunPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params?: { post_id?: string; selected_comments?: number[]; max_comment_chars?: number }) =>
      api.runPipeline(params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["videos"] });
        qc.invalidateQueries({ queryKey: ["stats"] });
      }, 3000);
    },
  });
}

export function useResetPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.resetPipeline,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline"] }),
  });
}

export function useCancelPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.cancelPipeline,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline"] }),
  });
}

export function useDeleteVideo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteVideo(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["videos"] }),
  });
}

export function useResumeVideo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (post_id: string) => api.resumeVideo(post_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["videos"] });
        qc.invalidateQueries({ queryKey: ["stats"] });
      }, 3000);
    },
  });
}

// ── TTS Providers ───────────────────────────────────────────────────
export function useTtsProviders() {
  return useQuery({
    queryKey: ["tts-providers"],
    queryFn: api.getTtsProviders,
    staleTime: 30_000,
  });
}

export function useInstallTtsProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (providerId: string) => api.installTtsProvider(providerId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tts-providers"] }),
  });
}
