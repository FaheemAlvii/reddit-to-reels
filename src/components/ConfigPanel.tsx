import { Settings2, Plus, X, Loader2, Save, Sparkles, Zap, CheckCircle2, XCircle } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { useConfig, useUpdateConfig } from "@/hooks/use-api";
import { useState, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";

function TestAiButtonSmall({ provider, model, apiKey, ollamaUrl }: { provider: string; model: string; apiKey: string; ollamaUrl?: string }) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<"success" | "error" | null>(null);
  const { toast } = useToast();

  const handleTest = async () => {
    if (provider !== "ollama" && !apiKey) {
      toast({ title: "Missing API key", variant: "destructive" });
      return;
    }
    setTesting(true);
    setResult(null);
    try {
      const res = await api.testAiModel({ provider, model, api_key: apiKey, ollama_url: ollamaUrl });
      setResult("success");
      toast({ title: "AI model works!", description: res.response.slice(0, 100) });
    } catch (e: any) {
      setResult("error");
      toast({ title: "Test failed", description: e.message, variant: "destructive" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Button variant="outline" size="sm" onClick={handleTest} disabled={testing} className="w-full gap-1.5 text-xs h-7">
      {testing ? <Loader2 className="h-3 w-3 animate-spin" /> : result === "success" ? <CheckCircle2 className="h-3 w-3 text-green-500" /> : result === "error" ? <XCircle className="h-3 w-3 text-destructive" /> : <Zap className="h-3 w-3" />}
      Test Model
    </Button>
  );
}

export function ConfigPanel() {
  const { data: config, isLoading } = useConfig();
  const updateMutation = useUpdateConfig();
  const { toast } = useToast();

  const [subreddits, setSubreddits] = useState<string[]>([]);
  const [minUpvotes, setMinUpvotes] = useState(500);
  const [minComments, setMinComments] = useState(10);
  const [maxComments, setMaxComments] = useState(500);
  const [allowNsfw, setAllowNsfw] = useState(false);
  const [requireSelftext, setRequireSelftext] = useState(true);
  const [newSubreddit, setNewSubreddit] = useState("");

  // AI Hooks
  const [geminiEnabled, setGeminiEnabled] = useState(false);
  const [geminiProvider, setGeminiProvider] = useState("gemini");
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [openrouterApiKey, setOpenrouterApiKey] = useState("");
  const [nvidiaNimApiKey, setNvidiaNimApiKey] = useState("");
  const [geminiModel, setGeminiModel] = useState("gemini-2.0-flash");
  const [geminiHook, setGeminiHook] = useState(true);
  const [geminiThumbnail, setGeminiThumbnail] = useState(true);
  const [geminiModels, setGeminiModels] = useState<string[]>([]);
  const [openrouterModels, setOpenrouterModels] = useState<string[]>([]);
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [nvidiaNimModels, setNvidiaNimModels] = useState<string[]>([]);

  // Sync from server
  useEffect(() => {
    if (config) {
      setSubreddits(config.subreddits ?? []);
      setMinUpvotes(config.filters?.min_upvotes ?? 500);
      setMinComments(config.filters?.min_comments ?? 10);
      setMaxComments(config.filters?.max_comments ?? 500);
      setAllowNsfw(config.filters?.allow_nsfw ?? false);
      setRequireSelftext(config.filters?.require_selftext ?? true);
      setGeminiEnabled((config as any).gemini?.enabled ?? false);
      setGeminiProvider((config as any).gemini?.provider ?? "gemini");
      setGeminiApiKey((config as any).gemini?.api_key ?? "");
      setOpenrouterApiKey((config as any).gemini?.openrouter_api_key ?? "");
      setGeminiModel((config as any).gemini?.model ?? "gemini-2.0-flash");
      setGeminiHook((config as any).gemini?.generate_hook ?? true);
      setGeminiThumbnail((config as any).gemini?.generate_thumbnail_text ?? true);
      if ((config as any).gemini?.gemini_models?.length) setGeminiModels((config as any).gemini.gemini_models);
      if ((config as any).gemini?.openrouter_models?.length) setOpenrouterModels((config as any).gemini.openrouter_models);
      if ((config as any).gemini?.ollama_url) setOllamaUrl((config as any).gemini.ollama_url);
      if ((config as any).gemini?.ollama_models?.length) setOllamaModels((config as any).gemini.ollama_models);
      setNvidiaNimApiKey((config as any).gemini?.nvidia_nim_api_key ?? "");
      if ((config as any).gemini?.nvidia_nim_models?.length) setNvidiaNimModels((config as any).gemini.nvidia_nim_models);
    }
  }, [config]);

  const addSubreddit = () => {
    const s = newSubreddit.trim();
    if (s && !subreddits.includes(s)) {
      setSubreddits([...subreddits, s]);
      setNewSubreddit("");
    }
  };

  const removeSubreddit = (sub: string) => {
    setSubreddits(subreddits.filter((s) => s !== sub));
  };

  const handleSave = () => {
    updateMutation.mutate(
      {
        subreddits,
        filters: {
          min_upvotes: minUpvotes,
          min_comments: minComments,
          max_comments: maxComments,
          allow_nsfw: allowNsfw,
          require_selftext: requireSelftext,
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
        onSuccess: () => toast({ title: "Config saved", description: "Pipeline configuration updated." }),
        onError: (e) => toast({ title: "Save failed", description: e.message, variant: "destructive" }),
      }
    );
  };

  if (isLoading) {
    return (
      <Card className="border-border bg-card">
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-base">
          <Settings2 className="h-4 w-4 text-primary" />
          Pipeline Configuration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Subreddits */}
        <div className="space-y-2">
          <Label className="text-xs uppercase tracking-wider text-muted-foreground">Subreddits</Label>
          <div className="flex flex-wrap gap-1.5">
            {subreddits.map((sub) => (
              <Badge key={sub} variant="secondary" className="gap-1 font-mono text-xs">
                r/{sub}
                <button onClick={() => removeSubreddit(sub)}>
                  <X className="h-3 w-3 hover:text-destructive transition-colors" />
                </button>
              </Badge>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              value={newSubreddit}
              onChange={(e) => setNewSubreddit(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addSubreddit()}
              placeholder="Add subreddit..."
              className="h-8 text-xs bg-secondary border-border"
            />
            <Button size="sm" variant="outline" onClick={addSubreddit} className="h-8 px-2">
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="space-y-4">
          <Label className="text-xs uppercase tracking-wider text-muted-foreground">Filters</Label>

          <div className="space-y-2">
            <div className="flex justify-between text-xs">
              <span>Min Upvotes</span>
              <span className="font-mono text-primary">{minUpvotes}</span>
            </div>
            <Slider
              value={[minUpvotes]}
              onValueChange={([v]) => setMinUpvotes(v)}
              max={10000}
              step={50}
              className="[&_[role=slider]]:bg-primary"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Min Comments</label>
              <Input
                type="number"
                value={minComments}
                onChange={(e) => setMinComments(+e.target.value)}
                className="h-8 text-xs bg-secondary border-border"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Max Comments</label>
              <Input
                type="number"
                value={maxComments}
                onChange={(e) => setMaxComments(+e.target.value)}
                className="h-8 text-xs bg-secondary border-border"
              />
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
        </div>

        {/* AI Hooks */}
        <div className="space-y-4">
          <Label className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
            <Sparkles className="h-3 w-3" />
            AI Hooks
          </Label>

          <div className="flex items-center justify-between">
            <label className="text-xs text-muted-foreground">Enable AI Hooks</label>
            <Switch checked={geminiEnabled} onCheckedChange={setGeminiEnabled} />
          </div>

          {geminiEnabled && (
            <div className="space-y-3 pl-1 border-l-2 border-primary/20 ml-1">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Provider</label>
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
                    <SelectItem value="gemini">Gemini</SelectItem>
                    <SelectItem value="openrouter">OpenRouter</SelectItem>
                    <SelectItem value="ollama">Ollama</SelectItem>
                    <SelectItem value="nvidia_nim">Nvidia NIM</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Model</label>
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
              </div>
              {geminiProvider === "gemini" && (
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Gemini API Key</label>
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
                  <label className="text-xs text-muted-foreground">OpenRouter API Key</label>
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
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Ollama URL</label>
                  <Input
                    value={ollamaUrl}
                    onChange={(e) => setOllamaUrl(e.target.value)}
                    placeholder="http://localhost:11434"
                    className="h-8 text-xs bg-secondary border-border font-mono"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    Local or remote Ollama endpoint
                  </p>
                </div>
              )}
              {geminiProvider === "nvidia_nim" && (
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">Nvidia NIM API Key</label>
                  <Input
                    type="password"
                    value={nvidiaNimApiKey}
                    onChange={(e) => setNvidiaNimApiKey(e.target.value)}
                    placeholder="nvapi-..."
                    className="h-8 text-xs bg-secondary border-border font-mono"
                  />
                </div>
              )}
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">Generate Video Hook</label>
                <Switch checked={geminiHook} onCheckedChange={setGeminiHook} />
              </div>
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">Generate Thumbnail Text</label>
                <Switch checked={geminiThumbnail} onCheckedChange={setGeminiThumbnail} />
              </div>
              <TestAiButtonSmall
                provider={geminiProvider}
                model={geminiModel}
                apiKey={geminiProvider === "openrouter" ? openrouterApiKey : geminiProvider === "nvidia_nim" ? nvidiaNimApiKey : geminiApiKey}
                ollamaUrl={geminiProvider === "ollama" ? ollamaUrl : undefined}
              />
            </div>
          )}
        </div>

        <Button
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="w-full glow-primary font-semibold"
        >
          {updateMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Save Configuration
        </Button>
      </CardContent>
    </Card>
  );
}
