import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Settings2, Save, Loader2, Plus, X, RotateCcw,
  MessageSquare, Mic, Film, FolderOutput, Bell,
  Download, CheckCircle2, XCircle, RefreshCw, Cpu, Sparkles, Zap
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { useConfig, useUpdateConfig, useTtsProviders, useInstallTtsProvider } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import type { FullConfig, TtsProvider } from "@/lib/api";

function TestAiButton({ provider, model, apiKey, ollamaUrl }: { provider: string; model: string; apiKey: string; ollamaUrl?: string }) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; text: string } | null>(null);
  const { toast } = useToast();

  const handleTest = async () => {
    if (provider !== "ollama" && !apiKey) {
      toast({ title: "Missing API key", description: "Enter an API key first.", variant: "destructive" });
      return;
    }
    setTesting(true);
    setResult(null);
    try {
      const res = await api.testAiModel({ provider, model, api_key: apiKey, ollama_url: ollamaUrl });
      setResult({ success: true, text: res.response });
    } catch (e: any) {
      setResult({ success: false, text: e.message || "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-2">
      <Button
        variant="outline"
        size="sm"
        onClick={handleTest}
        disabled={testing}
        className="w-full gap-2 text-xs"
      >
        {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
        Test AI Model
      </Button>
      {result && (
        <div className={`rounded-md border p-2.5 text-xs ${result.success ? "border-green-500/30 bg-green-500/5" : "border-destructive/30 bg-destructive/5"}`}>
          <div className="flex items-center gap-1.5 mb-1">
            {result.success ? <CheckCircle2 className="h-3.5 w-3.5 text-green-500" /> : <XCircle className="h-3.5 w-3.5 text-destructive" />}
            <span className="font-medium">{result.success ? "Success" : "Error"}</span>
          </div>
          <p className="text-muted-foreground leading-relaxed">{result.text}</p>
        </div>
      )}
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-sm">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

const STREAMLABS_VOICES = [
  "Brian", "Amy", "Emma", "Joanna", "Matthew",
  "Joey", "Justin", "Kendra", "Kimberly", "Salli",
];

export default function ConfigPage() {
  const { data: config, isLoading, isError, error } = useConfig();
  const updateMutation = useUpdateConfig();
  const { data: providersData, isLoading: providersLoading } = useTtsProviders();
  const installMutation = useInstallTtsProvider();
  const { toast } = useToast();
  const providers = providersData?.providers ?? [];

  // Local state for all config sections
  const [subreddits, setSubreddits] = useState<string[]>([]);
  const [newSub, setNewSub] = useState("");
  const [requestDelay, setRequestDelay] = useState(2);

  // Filters
  const [minUpvotes, setMinUpvotes] = useState(500);
  const [minComments, setMinComments] = useState(10);
  const [maxComments, setMaxComments] = useState(500);
  const [minAgeHours, setMinAgeHours] = useState(1);
  const [maxAgeHours, setMaxAgeHours] = useState(168);
  const [allowNsfw, setAllowNsfw] = useState(false);
  const [requireSelftext, setRequireSelftext] = useState(true);

  // Formatting
  const [fmtMode, setFmtMode] = useState("qa");
  const [fmtMaxComments, setFmtMaxComments] = useState(10);
  const [fmtMinScore, setFmtMinScore] = useState(10);

  // TTS
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [ttsProvider, setTtsProvider] = useState("streamlabs_polly");
  const [ttsModelSize, setTtsModelSize] = useState("");
  const [ttsMainVoice, setTtsMainVoice] = useState("Matthew");
  const [ttsMultiVoice, setTtsMultiVoice] = useState(true);
  const [ttsCommentVoices, setTtsCommentVoices] = useState<string[]>(STREAMLABS_VOICES);
  const [ttsFormat, setTtsFormat] = useState("mp3");
  const [ttsSpeed, setTtsSpeed] = useState(0.5);

  // Video
  const [videoMode, setVideoMode] = useState("short_reel");
  const [hwAccel, setHwAccel] = useState("none");
  const [autoCleanup, setAutoCleanup] = useState(false);
  const [threads, setThreads] = useState(0);
  const [engine, setEngine] = useState("ffmpeg");
  const [splitDuration, setSplitDuration] = useState(30);
  const [outroText, setOutroText] = useState("Follow for Part {next_part}");
  const [branding, setBranding] = useState("");

  // Output
  const [postsDir, setPostsDir] = useState("posts");
  const [usedPostsFile, setUsedPostsFile] = useState("used_posts.json");

  // Discord
  const [discordEnabled, setDiscordEnabled] = useState(true);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [uploadMedia, setUploadMedia] = useState(true);

  // AI Hooks
  const [geminiEnabled, setGeminiEnabled] = useState(false);
  const [geminiProvider, setGeminiProvider] = useState("gemini");
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [openrouterApiKey, setOpenrouterApiKey] = useState("");
  const [nvidiaNimApiKey, setNvidiaNimApiKey] = useState("");
  const [geminiModel, setGeminiModel] = useState("gemini-2.0-flash");
  const [geminiHook, setGeminiHook] = useState(true);
  const [geminiThumbnail, setGeminiThumbnail] = useState(true);
  const [geminiModels, setGeminiModels] = useState<string[]>([
    "gemini-2.0-flash", "gemini-2.5-flash-preview-05-20",
    "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-lite",
  ]);
  const [openrouterModels, setOpenrouterModels] = useState<string[]>([
    "google/gemma-3-27b-it:free", "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free", "google/gemma-3-1b-it:free",
    "google/gemini-2.0-flash-exp:free", "google/gemini-2.5-flash-preview:thinking",
    "deepseek/deepseek-chat-v3-0324:free", "meta-llama/llama-4-maverick:free",
    "qwen/qwen3-235b-a22b:free", "mistralai/mistral-small-3.1-24b-instruct:free",
  ]);
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [ollamaModels, setOllamaModels] = useState<string[]>([
    "llama3.2", "llama3.1", "gemma3", "gemma2",
    "mistral", "qwen2.5", "phi3", "deepseek-r1",
  ]);
  const [nvidiaNimModels, setNvidiaNimModels] = useState<string[]>([
    "meta/llama-3.1-405b-instruct", "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct", "google/gemma-2-27b-it",
    "google/gemma-2-9b-it", "mistralai/mixtral-8x22b-instruct-v0.1",
    "nvidia/llama-3.1-nemotron-70b-instruct", "deepseek-ai/deepseek-r1",
  ]);
  const [newModelId, setNewModelId] = useState("");

  const [initialLoaded, setInitialLoaded] = useState(false);

  useEffect(() => {
    if (!config || initialLoaded) return;
    const c = config as FullConfig;
    setSubreddits(c.subreddits ?? []);
    setRequestDelay(c.request_delay ?? 2);

    const f = c.filters ?? {} as FullConfig["filters"];
    setMinUpvotes(f.min_upvotes ?? 500);
    setMinComments(f.min_comments ?? 10);
    setMaxComments(f.max_comments ?? 500);
    setMinAgeHours(f.min_age_hours ?? 1);
    setMaxAgeHours(f.max_age_hours ?? 168);
    setAllowNsfw(f.allow_nsfw ?? false);
    setRequireSelftext(f.require_selftext ?? true);

    const fmt = c.formatting ?? {} as FullConfig["formatting"];
    setFmtMode(fmt.default_mode ?? "qa");
    setFmtMaxComments(fmt.max_comments ?? 10);
    setFmtMinScore(fmt.min_comment_score ?? 10);

    const t = c.tts ?? {} as FullConfig["tts"];
    setTtsEnabled(t.enabled ?? true);
    setTtsProvider(t.provider ?? "streamlabs_polly");
    setTtsModelSize(t.model_size ?? "");
    setTtsMainVoice(t.main_voice ?? "Matthew");
    setTtsMultiVoice(t.use_multiple_voices ?? true);
    setTtsCommentVoices(t.comment_voices ?? STREAMLABS_VOICES);
    setTtsFormat(t.output_format ?? "mp3");
    setTtsSpeed(t.speed ?? 0.5);

    const v = c.video ?? {} as FullConfig["video"];
    setVideoMode(v.mode ?? "short_reel");
    setHwAccel(v.hw_accel ?? "none");
    setAutoCleanup(v.auto_cleanup ?? false);
    setThreads(v.threads ?? 0);
    setEngine(v.engine ?? "ffmpeg");
    setSplitDuration(v.split_duration ?? 30);
    setOutroText(v.outro_text ?? "Follow for Part {next_part}");
    setBranding(v.branding ?? "");

    const o = c.output ?? {} as FullConfig["output"];
    setPostsDir(o.posts_directory ?? "posts");
    setUsedPostsFile(o.used_posts_file ?? "used_posts.json");

    const d = c.discord ?? {} as FullConfig["discord"];
    setDiscordEnabled(d.enabled ?? true);
    setWebhookUrl(d.webhook_url ?? "");
    setUploadMedia(d.upload_media ?? true);

    const g = (c as any).gemini ?? {};
    setGeminiEnabled(g.enabled ?? false);
    setGeminiProvider(g.provider ?? "gemini");
    setGeminiApiKey(g.api_key ?? "");
    setOpenrouterApiKey(g.openrouter_api_key ?? "");
    setGeminiModel(g.model ?? "gemini-2.0-flash");
    setGeminiHook(g.generate_hook ?? true);
    setGeminiThumbnail(g.generate_thumbnail_text ?? true);
    if (g.gemini_models?.length) setGeminiModels(g.gemini_models);
    if (g.openrouter_models?.length) setOpenrouterModels(g.openrouter_models);
    if (g.ollama_url) setOllamaUrl(g.ollama_url);
    if (g.ollama_models?.length) setOllamaModels(g.ollama_models);
    setNvidiaNimApiKey(g.nvidia_nim_api_key ?? "");
    if (g.nvidia_nim_models?.length) setNvidiaNimModels(g.nvidia_nim_models);

    setInitialLoaded(true);
  }, [config, initialLoaded]);

  // Auto-set default model size when provider changes
  useEffect(() => {
    const currentProvider = providers.find((p) => p.id === ttsProvider);
    if (currentProvider?.models?.length && !ttsModelSize) {
      setTtsModelSize(currentProvider.models[0].id);
    }
  }, [ttsProvider, providers, ttsModelSize]);

  const addSubreddit = () => {
    const s = newSub.trim().replace(/^r\//, "");
    if (s && !subreddits.includes(s)) {
      setSubreddits([...subreddits, s]);
      setNewSub("");
    }
  };

  const toggleVoice = (voice: string) => {
    setTtsCommentVoices((prev) =>
      prev.includes(voice) ? prev.filter((v) => v !== voice) : [...prev, voice]
    );
  };

  const handleSave = () => {
    updateMutation.mutate(
      {
        subreddits,
        request_delay: requestDelay,
        filters: {
          min_upvotes: minUpvotes,
          min_comments: minComments,
          max_comments: maxComments,
          min_age_hours: minAgeHours,
          max_age_hours: maxAgeHours,
          allow_nsfw: allowNsfw,
          require_selftext: requireSelftext,
        },
        formatting: {
          default_mode: fmtMode,
          max_comments: fmtMaxComments,
          min_comment_score: fmtMinScore,
        },
        tts: {
          enabled: ttsEnabled,
          provider: ttsProvider,
          model_size: ttsModelSize,
          main_voice: ttsMainVoice,
          use_multiple_voices: ttsMultiVoice,
          comment_voices: ttsCommentVoices,
          output_format: ttsFormat,
          speed: ttsSpeed,
        },
        video: {
          mode: videoMode,
          hw_accel: hwAccel,
          use_gpu: hwAccel !== "none",
          auto_cleanup: autoCleanup,
          threads,
          engine,
          split_duration: splitDuration,
          outro_text: outroText,
          branding,
        },
        output: {
          posts_directory: postsDir,
          used_posts_file: usedPostsFile,
        },
        discord: {
          enabled: discordEnabled,
          webhook_url: webhookUrl,
          upload_media: uploadMedia,
        },
        gemini: {
          enabled: geminiEnabled,
          provider: geminiProvider,
          api_key: geminiApiKey,
          openrouter_api_key: openrouterApiKey,
          nvidia_nim_api_key: nvidiaNimApiKey,
          model: geminiModel,
          generate_hook: geminiHook,
          generate_thumbnail_text: geminiThumbnail,
          gemini_models: geminiModels,
          openrouter_models: openrouterModels,
          ollama_url: ollamaUrl,
          ollama_models: ollamaModels,
          nvidia_nim_models: nvidiaNimModels,
        },
      },
      {
        onSuccess: () => toast({ title: "Configuration saved" }),
        onError: (e) => toast({ title: "Save failed", description: e.message, variant: "destructive" }),
      }
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <p className="text-destructive text-sm">{(error as Error)?.message || "Failed to load config"}</p>
        <p className="text-muted-foreground text-xs">Make sure the backend is running</p>
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Configuration</h2>
          <p className="text-xs text-muted-foreground mt-1">Manage your pipeline settings — all sections of config.json</p>
        </div>
        <Button onClick={handleSave} disabled={updateMutation.isPending} className="glow-primary gap-2">
          {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save All
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Subreddits & General */}
        <Section title="Subreddits & General" icon={<Settings2 className="h-4 w-4 text-primary" />}>
          <div className="space-y-2">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">Subreddits</Label>
            <div className="flex flex-wrap gap-1.5">
              {subreddits.map((sub) => (
                <Badge key={sub} variant="secondary" className="gap-1 font-mono text-xs">
                  r/{sub}
                  <button onClick={() => setSubreddits(subreddits.filter((s) => s !== sub))}>
                    <X className="h-3 w-3 hover:text-destructive transition-colors" />
                  </button>
                </Badge>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={newSub}
                onChange={(e) => setNewSub(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addSubreddit()}
                placeholder="Add subreddit..."
                className="h-8 text-xs bg-secondary border-border"
              />
              <Button size="sm" variant="outline" onClick={addSubreddit} className="h-8 px-2">
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Request Delay (seconds)</Label>
            <Input type="number" value={requestDelay} onChange={(e) => setRequestDelay(+e.target.value)} className="h-8 text-xs bg-secondary border-border" step={0.5} min={0} />
          </div>
        </Section>

        {/* Filters */}
        <Section title="Post Filters" icon={<MessageSquare className="h-4 w-4 text-primary" />}>
          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span>Min Upvotes</span>
              <span className="font-mono text-primary">{minUpvotes}</span>
            </div>
            <Slider value={[minUpvotes]} onValueChange={([v]) => setMinUpvotes(v)} max={10000} step={50} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Min Comments</label>
              <Input type="number" value={minComments} onChange={(e) => setMinComments(+e.target.value)} className="h-8 text-xs bg-secondary border-border" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Max Comments</label>
              <Input type="number" value={maxComments} onChange={(e) => setMaxComments(+e.target.value)} className="h-8 text-xs bg-secondary border-border" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Min Age (hours)</label>
              <Input type="number" value={minAgeHours} onChange={(e) => setMinAgeHours(+e.target.value)} className="h-8 text-xs bg-secondary border-border" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Max Age (hours)</label>
              <Input type="number" value={maxAgeHours} onChange={(e) => setMaxAgeHours(+e.target.value)} className="h-8 text-xs bg-secondary border-border" />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <label className="text-xs text-muted-foreground">Allow NSFW</label>
            <Switch checked={allowNsfw} onCheckedChange={setAllowNsfw} />
          </div>
          <div className="flex items-center justify-between">
            <label className="text-xs text-muted-foreground">Require Story Text</label>
            <Switch checked={requireSelftext} onCheckedChange={setRequireSelftext} />
          </div>
        </Section>

        {/* Formatting */}
        <Section title="Story Formatting" icon={<MessageSquare className="h-4 w-4 text-accent" />}>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Default Mode</Label>
            <Select value={fmtMode} onValueChange={setFmtMode}>
              <SelectTrigger className="h-8 text-xs bg-secondary border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="qa">Q&A (Question + Answers)</SelectItem>
                <SelectItem value="story">Story (Selftext narration)</SelectItem>
                <SelectItem value="comments">Comments Only</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Max Comments</label>
              <Input type="number" value={fmtMaxComments} onChange={(e) => setFmtMaxComments(+e.target.value)} className="h-8 text-xs bg-secondary border-border" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Min Comment Score</label>
              <Input type="number" value={fmtMinScore} onChange={(e) => setFmtMinScore(+e.target.value)} className="h-8 text-xs bg-secondary border-border" />
            </div>
          </div>
        </Section>

        {/* TTS */}
        <Section title="Text-to-Speech" icon={<Mic className="h-4 w-4 text-accent" />}>
          <div className="flex items-center justify-between">
            <label className="text-xs text-muted-foreground">TTS Enabled</label>
            <Switch checked={ttsEnabled} onCheckedChange={setTtsEnabled} />
          </div>

          {ttsEnabled && (
            <>
              {/* Info box */}
              <div className="rounded-md bg-secondary/50 border border-border p-3 space-y-1.5">
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  <strong className="text-foreground">How it works:</strong> The pipeline splits the story into <strong>segments</strong> — title, body paragraphs, and individual comments each become a separate audio clip. These are stitched into a timeline that drives the video rendering.
                </p>
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  <strong className="text-foreground">Multiple Voices:</strong> When enabled, the narrator voice reads the title & body, while each comment is read by a randomly assigned voice from your selected pool — creating a natural multi-speaker feel.
                </p>
              </div>

              <Separator />

              {/* Provider Selection with Install/Verify */}
              <div className="space-y-3">
                <Label className="text-xs text-muted-foreground">Provider</Label>
                <div className="space-y-2">
                  {providers.map((p) => {
                    const isSelected = ttsProvider === p.id;
                    const isLocal = p.type === "local";
                    return (
                      <div
                        key={p.id}
                        className={`rounded-lg border p-3 cursor-pointer transition-all ${
                          isSelected ? "border-primary bg-primary/5" : "border-border hover:border-primary/30"
                        }`}
                        onClick={() => setTtsProvider(p.id)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {isLocal ? <Cpu className="h-3.5 w-3.5 text-accent" /> : <Mic className="h-3.5 w-3.5 text-primary" />}
                            <span className="text-xs font-medium">{p.name}</span>
                            <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                              {p.type === "local" ? "Local GPU" : "Cloud"}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {p.installed ? (
                              <Badge variant="default" className="text-[9px] px-1.5 py-0 gap-0.5">
                                <CheckCircle2 className="h-3 w-3" /> Ready
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0 gap-0.5 border-warning text-warning">
                                <XCircle className="h-3 w-3" /> Not Installed
                              </Badge>
                            )}
                          </div>
                        </div>
                        <p className="text-[10px] text-muted-foreground mt-1">{p.details}</p>
                        
                        {/* Install/Verify buttons for local providers */}
                        {isLocal && (
                          <div className="flex gap-2 mt-2">
                            {!p.installed && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-6 text-[10px] gap-1"
                                disabled={installMutation.isPending}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  installMutation.mutate(p.id, {
                                    onSuccess: (data) => {
                                      if (data.success) {
                                        toast({ title: `${p.name} installed`, description: "Provider is now ready to use." });
                                      } else {
                                        toast({ title: "Install failed", description: data.error || "Check server logs", variant: "destructive" });
                                      }
                                    },
                                    onError: (err) => toast({ title: "Install error", description: err.message, variant: "destructive" }),
                                  });
                                }}
                              >
                                {installMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
                                Install
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-[10px] gap-1"
                              onClick={(e) => {
                                e.stopPropagation();
                                // Re-fetch providers to verify
                                toast({ title: "Checking...", description: `Verifying ${p.name} installation` });
                              }}
                            >
                              <RefreshCw className="h-3 w-3" /> Verify
                            </Button>
                          </div>
                        )}

                        {/* Model size selector for local providers */}
                        {isLocal && isSelected && p.models && p.models.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-border/50 space-y-1.5">
                            <Label className="text-[10px] text-muted-foreground uppercase tracking-wider">Model Size</Label>
                            <div className="space-y-1">
                              {p.models.map((m: any) => {
                                const isDownloaded = p.models_downloaded?.includes(m.id);
                                const isActive = ttsModelSize === m.id;
                                return (
                                  <div
                                    key={m.id}
                                    className={`rounded-md border p-2 cursor-pointer transition-all ${
                                      isActive ? "border-primary bg-primary/10" : "border-border/50 hover:border-primary/30"
                                    }`}
                                    onClick={(e) => { e.stopPropagation(); setTtsModelSize(m.id); }}
                                  >
                                    <div className="flex items-center justify-between">
                                      <span className="text-[11px] font-medium">{m.name}</span>
                                      <div className="flex items-center gap-1">
                                        <Badge variant="outline" className="text-[8px] px-1 py-0">{m.size}</Badge>
                                        {isDownloaded && (
                                          <Badge variant="default" className="text-[8px] px-1 py-0 gap-0.5">
                                            <CheckCircle2 className="h-2.5 w-2.5" /> Cached
                                          </Badge>
                                        )}
                                      </div>
                                    </div>
                                    <p className="text-[9px] text-muted-foreground mt-0.5">{m.description}</p>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        
                        {isSelected && p.voices && (
                          <div className="flex flex-wrap gap-1 mt-2 pt-2 border-t border-border/50">
                            {(p.voices_detailed ?? p.voices.map(v => ({ id: v, name: v, lang: "en", gender: "unknown" }))).slice(0, 8).map((v: any) => (
                              <Badge key={typeof v === "string" ? v : v.id} variant="secondary" className="text-[9px] gap-0.5">
                                {typeof v === "string" ? v : (
                                  <>
                                    <span className="font-medium">{v.name}</span>
                                    <span className="text-muted-foreground">({v.lang})</span>
                                  </>
                                )}
                              </Badge>
                            ))}
                            {p.voices.length > 8 && (
                              <Badge variant="secondary" className="text-[9px]">+{p.voices.length - 8} more</Badge>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {providersLoading && (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    </div>
                  )}
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Main Narrator Voice</Label>
                {(() => {
                  const currentProvider = providers.find((p) => p.id === ttsProvider);
                  const voiceList = currentProvider?.voices ?? STREAMLABS_VOICES;
                  const detailedList = currentProvider?.voices_detailed;
                  return (
                    <Select value={ttsMainVoice} onValueChange={setTtsMainVoice}>
                      <SelectTrigger className="h-8 text-xs bg-secondary border-border">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {voiceList.map((v) => {
                          const detail = detailedList?.find((d) => d.id === v);
                          return (
                            <SelectItem key={v} value={v}>
                              {detail ? `${detail.name} (${detail.lang}, ${detail.gender})` : v}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  );
                })()}
                <p className="text-[10px] text-muted-foreground">
                  Used for the post title and body/story text narration.
                </p>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <div>
                  <label className="text-xs text-muted-foreground">Multiple Voices for Comments</label>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Each comment gets a random voice from the pool below</p>
                </div>
                <Switch checked={ttsMultiVoice} onCheckedChange={setTtsMultiVoice} />
              </div>
              {ttsMultiVoice && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-muted-foreground">Comment Voice Pool</Label>
                    <span className="text-[10px] text-muted-foreground">{ttsCommentVoices.length} selected</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(() => {
                      const currentProvider = providers.find((p) => p.id === ttsProvider);
                      const voiceList = currentProvider?.voices ?? STREAMLABS_VOICES;
                      const detailedList = currentProvider?.voices_detailed;
                      return voiceList.map((v) => {
                        const detail = detailedList?.find((d) => d.id === v);
                        const label = detail ? `${detail.name} (${detail.lang})` : v;
                        return (
                          <Badge
                            key={v}
                            variant={ttsCommentVoices.includes(v) ? "default" : "outline"}
                            className="cursor-pointer text-xs"
                            onClick={() => toggleVoice(v)}
                          >
                            {label}
                          </Badge>
                        );
                      });
                    })()}
                  </div>
                  <p className="text-[10px] text-muted-foreground">Click to toggle. More voices = more variety in the final video.</p>
                </div>
              )}

              <Separator />

              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span>Playback Speed</span>
                  <span className="font-mono text-primary">{ttsSpeed}x</span>
                </div>
                <Slider value={[ttsSpeed]} onValueChange={([v]) => setTtsSpeed(v)} min={0.25} max={2} step={0.05} />
                <p className="text-[10px] text-muted-foreground">
                  {ttsSpeed < 0.8 ? "Slow — good for dramatic stories" : ttsSpeed > 1.2 ? "Fast — more content per video" : "Normal conversational pace"}
                </p>
              </div>

              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Output Format</Label>
                <Select value={ttsFormat} onValueChange={setTtsFormat}>
                  <SelectTrigger className="h-8 text-xs bg-secondary border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mp3">MP3 (smaller files)</SelectItem>
                    <SelectItem value="wav">WAV (lossless quality)</SelectItem>
                    <SelectItem value="ogg">OGG (good compression)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          )}
        </Section>

        {/* Video */}
        <Section title="Video Rendering" icon={<Film className="h-4 w-4 text-warning" />}>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Video Mode</Label>
            <Select value={videoMode} onValueChange={setVideoMode}>
              <SelectTrigger className="h-8 text-xs bg-secondary border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="full">Full Video</SelectItem>
                <SelectItem value="reel">Reel</SelectItem>
                <SelectItem value="short_reel">Short Reel (Split)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Engine</Label>
            <Select value={engine} onValueChange={setEngine}>
              <SelectTrigger className="h-8 text-xs bg-secondary border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ffmpeg">FFmpeg (Recommended)</SelectItem>
                <SelectItem value="moviepy">MoviePy (Fallback)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Hardware Acceleration</Label>
            <Select value={hwAccel} onValueChange={setHwAccel}>
              <SelectTrigger className="h-8 text-xs bg-secondary border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">CPU (libx264)</SelectItem>
                <SelectItem value="nvenc">NVIDIA GPU (NVENC)</SelectItem>
                <SelectItem value="amf">AMD GPU (AMF)</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-[10px] text-muted-foreground">
              {hwAccel === "nvenc" ? "Requires NVIDIA GPU with NVENC support" : hwAccel === "amf" ? "Requires AMD GPU with AMF support (RX 400+)" : "Works on any system, no GPU required"}
            </p>
          </div>
          <div className="flex items-center justify-between">
            <label className="text-xs text-muted-foreground">Auto Cleanup</label>
            <Switch checked={autoCleanup} onCheckedChange={setAutoCleanup} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Threads (0 = auto)</label>
              <Input type="number" value={threads} onChange={(e) => setThreads(+e.target.value)} className="h-8 text-xs bg-secondary border-border" min={0} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Split Duration (s)</label>
              <Input type="number" value={splitDuration} onChange={(e) => setSplitDuration(+e.target.value)} className="h-8 text-xs bg-secondary border-border" />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Outro Text</Label>
            <Input value={outroText} onChange={(e) => setOutroText(e.target.value)} className="h-8 text-xs bg-secondary border-border" />
          </div>
          <Separator />
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Branding Watermark</Label>
            <Input value={branding} onChange={(e) => setBranding(e.target.value)} placeholder="e.g. @yourhandle or YourChannel" className="h-8 text-xs bg-secondary border-border" />
            <p className="text-[10px] text-muted-foreground">Shown on thumbnails to prevent uncredited copying. Leave blank to disable.</p>
          </div>
        </Section>

        {/* AI Hooks */}
        <Section title="AI Hooks" icon={<Sparkles className="h-4 w-4 text-primary" />}>
          <div className="rounded-md bg-secondary/50 border border-border p-3">
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              <strong className="text-foreground">How it works:</strong> AI generates a 3-4 second attention-grabbing hook prepended to the video narration, plus curiosity-driven thumbnail text — all without spoiling the story.
            </p>
          </div>
          <div className="flex items-center justify-between">
            <label className="text-xs text-muted-foreground">Enable AI Hooks</label>
            <Switch checked={geminiEnabled} onCheckedChange={setGeminiEnabled} />
          </div>
          {geminiEnabled && (
            <div className="space-y-3 pl-2 border-l-2 border-primary/20">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Provider</Label>
                <Select value={geminiProvider} onValueChange={(v) => {
                  setGeminiProvider(v);
                  if (v === "openrouter") setGeminiModel(openrouterModels[0] || "");
                  else if (v === "ollama") setGeminiModel(ollamaModels[0] || "llama3.2");
                  else if (v === "nvidia_nim") setGeminiModel(nvidiaNimModels[0] || "meta/llama-3.1-405b-instruct");
                  else setGeminiModel(geminiModels[0] || "gemini-2.0-flash");
                }}>
                  <SelectTrigger className="h-8 text-xs bg-secondary border-border">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gemini">Gemini (Google AI Studio)</SelectItem>
                    <SelectItem value="openrouter">OpenRouter</SelectItem>
                    <SelectItem value="ollama">Ollama (Local / Cloud)</SelectItem>
                    <SelectItem value="nvidia_nim">Nvidia NIM</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Model</Label>
                <Select value={geminiModel} onValueChange={setGeminiModel}>
                  <SelectTrigger className="h-8 text-xs bg-secondary border-border font-mono">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(geminiProvider === "openrouter" ? openrouterModels : geminiProvider === "ollama" ? ollamaModels : geminiProvider === "nvidia_nim" ? nvidiaNimModels : geminiModels).map((m) => (
                      <SelectItem key={m} value={m}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="flex gap-1.5 mt-1.5">
                  <Input
                    value={newModelId}
                    onChange={(e) => setNewModelId(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const id = newModelId.trim();
                        if (!id) return;
                        if (geminiProvider === "openrouter") {
                          if (!openrouterModels.includes(id)) setOpenrouterModels([...openrouterModels, id]);
                        } else if (geminiProvider === "ollama") {
                          if (!ollamaModels.includes(id)) setOllamaModels([...ollamaModels, id]);
                        } else if (geminiProvider === "nvidia_nim") {
                          if (!nvidiaNimModels.includes(id)) setNvidiaNimModels([...nvidiaNimModels, id]);
                        } else {
                          if (!geminiModels.includes(id)) setGeminiModels([...geminiModels, id]);
                        }
                        setNewModelId("");
                      }
                    }}
                    placeholder="Add custom model ID..."
                    className="h-7 text-xs bg-secondary border-border font-mono"
                  />
                  <Button size="sm" variant="outline" className="h-7 px-2" onClick={() => {
                    const id = newModelId.trim();
                    if (!id) return;
                    if (geminiProvider === "openrouter") {
                      if (!openrouterModels.includes(id)) setOpenrouterModels([...openrouterModels, id]);
                    } else if (geminiProvider === "ollama") {
                      if (!ollamaModels.includes(id)) setOllamaModels([...ollamaModels, id]);
                    } else if (geminiProvider === "nvidia_nim") {
                      if (!nvidiaNimModels.includes(id)) setNvidiaNimModels([...nvidiaNimModels, id]);
                    } else {
                      if (!geminiModels.includes(id)) setGeminiModels([...geminiModels, id]);
                    }
                    setNewModelId("");
                  }}>
                    <Plus className="h-3 w-3" />
                  </Button>
                </div>
                {(geminiProvider === "openrouter" ? openrouterModels : geminiProvider === "ollama" ? ollamaModels : geminiProvider === "nvidia_nim" ? nvidiaNimModels : geminiModels).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {(geminiProvider === "openrouter" ? openrouterModels : geminiProvider === "ollama" ? ollamaModels : geminiProvider === "nvidia_nim" ? nvidiaNimModels : geminiModels).map((m) => (
                      <Badge key={m} variant="secondary" className="gap-1 font-mono text-[10px] px-1.5 py-0">
                        {m}
                        <button onClick={() => {
                          if (geminiProvider === "openrouter") {
                            const updated = openrouterModels.filter((x) => x !== m);
                            setOpenrouterModels(updated);
                            if (geminiModel === m) setGeminiModel(updated[0] || "");
                          } else if (geminiProvider === "ollama") {
                            const updated = ollamaModels.filter((x) => x !== m);
                            setOllamaModels(updated);
                            if (geminiModel === m) setGeminiModel(updated[0] || "");
                          } else if (geminiProvider === "nvidia_nim") {
                            const updated = nvidiaNimModels.filter((x) => x !== m);
                            setNvidiaNimModels(updated);
                            if (geminiModel === m) setGeminiModel(updated[0] || "");
                          } else {
                            const updated = geminiModels.filter((x) => x !== m);
                            setGeminiModels(updated);
                            if (geminiModel === m) setGeminiModel(updated[0] || "");
                          }
                        }}>
                          <X className="h-2.5 w-2.5 hover:text-destructive transition-colors" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              {geminiProvider === "gemini" && (
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Gemini API Key</Label>
                  <Input
                    type="password"
                    value={geminiApiKey}
                    onChange={(e) => setGeminiApiKey(e.target.value)}
                    placeholder="AIza..."
                    className="h-8 text-xs bg-secondary border-border font-mono"
                  />
                </div>
              )}
              {geminiProvider === "openrouter" && (
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">OpenRouter API Key</Label>
                  <Input
                    type="password"
                    value={openrouterApiKey}
                    onChange={(e) => setOpenrouterApiKey(e.target.value)}
                    placeholder="sk-or-..."
                    className="h-8 text-xs bg-secondary border-border font-mono"
                  />
                </div>
              )}
              {geminiProvider === "ollama" && (
                <div className="space-y-2">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Ollama URL</Label>
                    <Input
                      value={ollamaUrl}
                      onChange={(e) => setOllamaUrl(e.target.value)}
                      placeholder="http://localhost:11434"
                      className="h-8 text-xs bg-secondary border-border font-mono"
                    />
                    <p className="text-[10px] text-muted-foreground">
                      Local: http://localhost:11434 · Cloud: your remote Ollama endpoint
                    </p>
                  </div>
                </div>
              )}
              {geminiProvider === "nvidia_nim" && (
                <div className="space-y-1">
                  <Label className="text-xs text-muted-foreground">Nvidia NIM API Key</Label>
                  <Input
                    type="password"
                    value={nvidiaNimApiKey}
                    onChange={(e) => setNvidiaNimApiKey(e.target.value)}
                    placeholder="nvapi-..."
                    className="h-8 text-xs bg-secondary border-border font-mono"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    Get your key from <a href="https://build.nvidia.com" target="_blank" rel="noopener noreferrer" className="text-primary underline">build.nvidia.com</a>
                  </p>
                </div>
              )}
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-xs text-muted-foreground">Generate Video Hook</label>
                  <p className="text-[10px] text-muted-foreground mt-0.5">3-4s spoken intro prepended to the story</p>
                </div>
                <Switch checked={geminiHook} onCheckedChange={setGeminiHook} />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <label className="text-xs text-muted-foreground">Generate Thumbnail Text</label>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Eye-catching overlay text for thumbnails</p>
                </div>
                <Switch checked={geminiThumbnail} onCheckedChange={setGeminiThumbnail} />
              </div>

              <Separator />

              <TestAiButton
                provider={geminiProvider}
                model={geminiModel}
                apiKey={geminiProvider === "openrouter" ? openrouterApiKey : geminiProvider === "nvidia_nim" ? nvidiaNimApiKey : geminiApiKey}
                ollamaUrl={geminiProvider === "ollama" ? ollamaUrl : undefined}
              />
            </div>
          )}
        </Section>

        {/* Output & Discord */}
        <div className="space-y-5">
          <Section title="Output Paths" icon={<FolderOutput className="h-4 w-4 text-success" />}>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Posts Directory</Label>
              <Input value={postsDir} onChange={(e) => setPostsDir(e.target.value)} className="h-8 text-xs bg-secondary border-border font-mono" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Used Posts File</Label>
              <Input value={usedPostsFile} onChange={(e) => setUsedPostsFile(e.target.value)} className="h-8 text-xs bg-secondary border-border font-mono" />
            </div>
          </Section>

          <Section title="Discord Notifications" icon={<Bell className="h-4 w-4 text-accent" />}>
            <div className="flex items-center justify-between">
              <label className="text-xs text-muted-foreground">Discord Enabled</label>
              <Switch checked={discordEnabled} onCheckedChange={setDiscordEnabled} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">Webhook URL</Label>
              <Input
                type="password"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="h-8 text-xs bg-secondary border-border font-mono"
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-xs text-muted-foreground">Upload Media Files</label>
              <Switch checked={uploadMedia} onCheckedChange={setUploadMedia} />
            </div>
          </Section>
        </div>
      </div>

      {/* Floating save bar */}
      <div className="sticky bottom-4 flex justify-end">
        <Button onClick={handleSave} disabled={updateMutation.isPending} size="lg" className="glow-primary gap-2 shadow-xl">
          {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save Configuration
        </Button>
      </div>
    </motion.div>
  );
}
