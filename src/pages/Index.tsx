import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Video, Flame, Bot, PenLine, Link as LinkIcon, Clock, ArrowRight, Clapperboard, Layers, Globe, ShieldCheck, AlertCircle, Loader2 } from "lucide-react";
import { StatsCard } from "@/components/StatsCard";
import { PipelinePanel } from "@/components/PipelinePanel";
import { RecentVideos } from "@/components/RecentVideos";
import { GenerateWithAIDialog } from "@/components/GenerateWithAIDialog";
import { GenerateFromCustomDialog } from "@/components/GenerateFromCustomDialog";
import { GenerateFromUrlDialog } from "@/components/GenerateFromUrlDialog";
import { useStats } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function Index() {
  const { data: stats } = useStats();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [warming, setWarming] = useState(false);
  const [sessionInfo, setSessionInfo] = useState<{ valid?: boolean; cookie_count?: number; warmed_at?: string; reason?: string } | null>(null);

  useEffect(() => {
    api.getRedditSessionStatus().then(setSessionInfo).catch(() => {});
  }, []);

  const handleWarmup = async () => {
    setWarming(true);
    try {
      const res = await api.warmupRedditSession(true);
      toast({ title: "Playwright Session Warmed", description: res.message });
      const info = await api.getRedditSessionStatus();
      setSessionInfo(info);
    } catch (e: any) {
      toast({ title: "Warmup Failed", description: e.message, variant: "destructive" });
    } finally {
      setWarming(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Session Warmer Alert Notice on Dashboard */}
      <motion.div
        initial={{ opacity: 0, y: -5 }}
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-xl border p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs ${
          sessionInfo?.valid
            ? "border-green-500/30 bg-green-500/5 text-foreground"
            : "border-warning/30 bg-warning/10 text-warning"
        }`}
      >
        <div className="flex items-start gap-2.5">
          <Globe className={`h-4 w-4 shrink-0 mt-0.5 ${sessionInfo?.valid ? "text-green-400" : "text-warning"}`} />
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-foreground">Reddit Session Status:</span>
              {sessionInfo?.valid ? (
                <Badge variant="default" className="text-[9px] bg-green-500/20 text-green-400 border-green-500/30 gap-1 py-0">
                  <ShieldCheck className="h-3 w-3 text-green-400" /> Warmed & Active ({sessionInfo.cookie_count} cookies)
                </Badge>
              ) : (
                <Badge variant="outline" className="text-[9px] border-warning text-warning py-0">
                  {sessionInfo?.reason || "Needs Playwright Warmup"}
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground text-[11px]">
              {sessionInfo?.valid
                ? "Browser session is active. Reddit API calls will use persisted session cookies."
                : "Warm up session before using Reddit imports to prevent 403 anti-bot request blocks."}
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant={sessionInfo?.valid ? "outline" : "default"}
          onClick={handleWarmup}
          disabled={warming}
          className={`text-xs gap-1.5 h-8 shrink-0 ${!sessionInfo?.valid ? "glow-primary" : ""}`}
        >
          {warming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Globe className="h-3.5 w-3.5" />}
          {warming ? "Warming Session..." : sessionInfo?.valid ? "Refresh Session" : "Warm Up Session"}
        </Button>
      </motion.div>

      {/* Hero Welcome & Quick Studio Jump */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-primary/20 bg-gradient-to-r from-primary/10 via-background to-accent/10 p-6 shadow-sm"
      >
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-xl md:text-2xl font-bold tracking-tight flex items-center gap-2">
              <Clapperboard className="h-5 w-5 text-primary" />
              Text to Reels Studio
            </h2>
            <p className="text-xs text-muted-foreground max-w-xl">
              Turn manual text scripts, confessional stories, AskReddit Q&A, and AI prompts into vertical 1080x1920 short reels with multi-voice narration.
            </p>
          </div>
          <Button
            onClick={() => navigate("/studio")}
            className="glow-primary gap-2 font-semibold text-xs shrink-0"
          >
            Open Story Studio <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Quick Launch Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-5">
          <Card className="border-border bg-card/80 hover:border-accent/50 transition-all p-3.5 flex flex-col justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-accent/10 text-accent">
                  <Bot className="h-4 w-4" />
                </div>
                <h3 className="text-xs font-semibold">AI Story Generator</h3>
              </div>
              <p className="text-[11px] text-muted-foreground">Auto-generate viral stories, confessional drama, or Q&A threads.</p>
            </div>
            <GenerateWithAIDialog />
          </Card>

          <Card className="border-border bg-card/80 hover:border-primary/50 transition-all p-3.5 flex flex-col justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary/10 text-primary">
                  <PenLine className="h-4 w-4" />
                </div>
                <h3 className="text-xs font-semibold">Manual Script Studio</h3>
              </div>
              <p className="text-[11px] text-muted-foreground">Write custom stories, scripts, or speaker Q&A comments.</p>
            </div>
            <GenerateFromCustomDialog />
          </Card>

          <Card className="border-border bg-card/80 hover:border-blue-500/50 transition-all p-3.5 flex flex-col justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-blue-500/10 text-blue-400">
                  <LinkIcon className="h-4 w-4" />
                </div>
                <h3 className="text-xs font-semibold">Article / URL Import</h3>
              </div>
              <p className="text-[11px] text-muted-foreground">Convert text articles or post URLs directly into Reel scripts.</p>
            </div>
            <GenerateFromUrlDialog />
          </Card>
        </div>
      </motion.div>

      {/* Stats Row */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-3"
      >
        <StatsCard label="Reels Today" value={stats?.videos_today ?? "—"} icon={<Video className="h-4 w-4" />} accentColor="primary" index={0} />
        <StatsCard label="Render Time (avg)" value={stats?.avg_render_time_s ? `${stats.avg_render_time_s}s` : "—"} icon={<Clock className="h-4 w-4" />} accentColor="warning" index={1} />
        <StatsCard label="Success Rate" value={stats?.success_rate != null ? `${stats.success_rate}%` : "—"} icon={<Flame className="h-4 w-4" />} accentColor="success" index={2} />
        <StatsCard label="Total Runs" value={stats?.total_runs ?? "—"} icon={<Layers className="h-4 w-4" />} accentColor="accent" index={3} />
      </motion.div>

      {/* Main Execution & Gallery Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-4">
          <PipelinePanel />
        </div>
        <div className="lg:col-span-8">
          <RecentVideos />
        </div>
      </div>
    </div>
  );
}
