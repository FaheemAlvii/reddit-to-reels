import { useState } from "react";
import {
  Sparkles, ArrowRight, ArrowLeft, Play, Loader2,
  Film, Scissors, Mic, MicOff, BookOpen, MessageSquare,
  Gamepad2, Flame, HandMetal, HelpCircle, Star, Brain,
} from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";

const CONTENT_STYLES = [
  { id: "story", label: "Story", icon: BookOpen, desc: "First-person Reddit confessional", color: "text-blue-400" },
  { id: "qa", label: "Q&A", icon: MessageSquare, desc: "Viral AskReddit thread with answers", color: "text-green-400" },
  { id: "interactive", label: "Interactive", icon: Gamepad2, desc: '"Put a finger down" / quizzes with pauses', color: "text-purple-400" },
  { id: "hot_take", label: "Hot Take", icon: Flame, desc: "Controversial opinion that drives comments", color: "text-orange-400" },
];

const NICHES = [
  { id: "relationship_drama", name: "Relationship Drama", emoji: "💔" },
  { id: "childhood_nostalgia", name: "Childhood Nostalgia", emoji: "🧸" },
  { id: "workplace_horror", name: "Workplace Horror", emoji: "💼" },
  { id: "dating_disasters", name: "Dating Disasters", emoji: "🫠" },
  { id: "family_secrets", name: "Family Secrets", emoji: "🤫" },
  { id: "school_memories", name: "School Memories", emoji: "🎒" },
  { id: "paranormal_encounters", name: "Paranormal", emoji: "👻" },
  { id: "neighbor_stories", name: "Neighbor Stories", emoji: "🏠" },
  { id: "travel_nightmares", name: "Travel Nightmares", emoji: "✈️" },
  { id: "food_culture", name: "Food & Culture", emoji: "🍕" },
];

const INTERACTIVE_FORMATS = [
  { id: "put_a_finger_down", label: "Put a Finger Down", icon: HandMetal },
  { id: "would_you_rather", label: "Would You Rather", icon: HelpCircle },
  { id: "rate_yourself", label: "Rate Yourself", icon: Star },
  { id: "guess_the_answer", label: "Guess the Answer", icon: Brain },
];

const VIDEO_MODES = [
  { id: "short_reel", label: "Short Reel", icon: Scissors, desc: "< 60s vertical video" },
  { id: "full_video", label: "Full Video", icon: Film, desc: "Full-length horizontal" },
  { id: "reel", label: "Reel", icon: Film, desc: "60-90s vertical format" },
];

export function GenerateWithAIDialog() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [contentStyle, setContentStyle] = useState("story");
  const [niche, setNiche] = useState("relationship_drama");
  const [customTopic, setCustomTopic] = useState("");
  const [interactiveFormat, setInteractiveFormat] = useState("put_a_finger_down");
  const [videoMode, setVideoMode] = useState("short_reel");
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const { toast } = useToast();
  const qc = useQueryClient();

  const totalSteps = 4;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await api.runPipelineAI({
        content_style: contentStyle,
        niche,
        custom_topic: customTopic || undefined,
        interactive_format: contentStyle === "interactive" ? interactiveFormat : undefined,
        video_mode: videoMode,
        tts_enabled: ttsEnabled,
      });
      toast({ title: "AI Pipeline started", description: "Generating original content with AI..." });
      qc.invalidateQueries({ queryKey: ["pipeline"] });
      setOpen(false);
      resetForm();
    } catch (e: any) {
      toast({ title: "Failed", description: e.message, variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  const resetForm = () => {
    setStep(0);
    setContentStyle("story");
    setNiche("relationship_drama");
    setCustomTopic("");
    setInteractiveFormat("put_a_finger_down");
    setVideoMode("short_reel");
    setTtsEnabled(true);
  };

  const renderStep = () => {
    // Step 0: Content Style
    if (step === 0) {
      return (
        <div className="space-y-4">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Content Style</Label>
          <div className="grid grid-cols-1 gap-2">
            {CONTENT_STYLES.map((s) => (
              <button
                key={s.id}
                onClick={() => setContentStyle(s.id)}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border text-left transition-all",
                  contentStyle === s.id
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-secondary/50 text-muted-foreground hover:border-primary/30"
                )}
              >
                <s.icon className={cn("h-5 w-5 shrink-0", contentStyle === s.id ? s.color : "")} />
                <div>
                  <p className="text-xs font-medium">{s.label}</p>
                  <p className="text-[10px] opacity-70">{s.desc}</p>
                </div>
              </button>
            ))}
          </div>
          <Button onClick={() => setStep(1)} className="w-full gap-2">
            Next <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      );
    }

    // Step 1: Niche + Optional Topic
    if (step === 1) {
      return (
        <div className="space-y-4">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Choose Niche</Label>
          <div className="grid grid-cols-2 gap-1.5">
            {NICHES.map((n) => (
              <button
                key={n.id}
                onClick={() => setNiche(n.id)}
                className={cn(
                  "flex items-center gap-2 p-2 rounded-lg border text-left transition-all",
                  niche === n.id
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-secondary/50 text-muted-foreground hover:border-primary/30"
                )}
              >
                <span className="text-sm">{n.emoji}</span>
                <span className="text-[10px] font-medium leading-tight">{n.name}</span>
              </button>
            ))}
          </div>

          {contentStyle === "interactive" && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground uppercase tracking-wider">Format</Label>
              <div className="grid grid-cols-2 gap-1.5">
                {INTERACTIVE_FORMATS.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setInteractiveFormat(f.id)}
                    className={cn(
                      "flex items-center gap-2 p-2 rounded-lg border text-left transition-all",
                      interactiveFormat === f.id
                        ? "border-accent bg-accent/10 text-foreground"
                        : "border-border bg-secondary/50 text-muted-foreground hover:border-accent/30"
                    )}
                  >
                    <f.icon className="h-3.5 w-3.5 shrink-0" />
                    <span className="text-[10px] font-medium">{f.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Custom Topic (optional)</Label>
            <Input
              value={customTopic}
              onChange={(e) => setCustomTopic(e.target.value)}
              placeholder="e.g. 'caught my roommate doing something weird at 3am'"
              className="h-8 text-xs bg-secondary border-border"
            />
            <p className="text-[10px] text-muted-foreground">Leave empty for AI to choose a fresh angle</p>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(0)} className="flex-1 gap-2">
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <Button onClick={() => setStep(2)} className="flex-1 gap-2">
              Next <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      );
    }

    // Step 2: Video Mode & TTS
    if (step === 2) {
      return (
        <div className="space-y-4">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Video Format</Label>
          <div className="grid grid-cols-1 gap-2">
            {VIDEO_MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => setVideoMode(m.id)}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border text-left transition-all",
                  videoMode === m.id
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-secondary/50 text-muted-foreground hover:border-primary/30"
                )}
              >
                <m.icon className="h-5 w-5 shrink-0" />
                <div>
                  <p className="text-xs font-medium">{m.label}</p>
                  <p className="text-[10px] opacity-70">{m.desc}</p>
                </div>
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/50">
            <div className="flex items-center gap-2">
              {ttsEnabled ? <Mic className="h-4 w-4 text-primary" /> : <MicOff className="h-4 w-4 text-muted-foreground" />}
              <div>
                <p className="text-xs font-medium">Text-to-Speech</p>
                <p className="text-[10px] text-muted-foreground">Generate voiceover audio</p>
              </div>
            </div>
            <Button
              size="sm"
              variant={ttsEnabled ? "default" : "outline"}
              onClick={() => setTtsEnabled(!ttsEnabled)}
              className="h-7 text-xs"
            >
              {ttsEnabled ? "On" : "Off"}
            </Button>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(1)} className="flex-1 gap-2">
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <Button onClick={() => setStep(3)} className="flex-1 gap-2">
              Next <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      );
    }

    // Step 3: Review & Generate
    if (step === 3) {
      const styleInfo = CONTENT_STYLES.find((s) => s.id === contentStyle);
      const nicheInfo = NICHES.find((n) => n.id === niche);
      const formatInfo = INTERACTIVE_FORMATS.find((f) => f.id === interactiveFormat);

      return (
        <div className="space-y-4">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Review</Label>
          <div className="space-y-2 rounded-lg border border-border bg-secondary/30 p-3">
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground">Style</span>
              <span className="font-medium">{styleInfo?.label}</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground">Niche</span>
              <span className="font-medium">{nicheInfo?.emoji} {nicheInfo?.name}</span>
            </div>
            {contentStyle === "interactive" && (
              <div className="flex justify-between text-[10px]">
                <span className="text-muted-foreground">Format</span>
                <span className="font-medium">{formatInfo?.label}</span>
              </div>
            )}
            {customTopic && (
              <div className="flex justify-between text-[10px]">
                <span className="text-muted-foreground">Topic</span>
                <span className="font-medium truncate ml-4 max-w-[180px]">{customTopic}</span>
              </div>
            )}
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground">Video</span>
              <span className="font-medium">{VIDEO_MODES.find((m) => m.id === videoMode)?.label}</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground">TTS</span>
              <span className="font-medium">{ttsEnabled ? "Enabled" : "Disabled"}</span>
            </div>
          </div>

          <p className="text-[10px] text-muted-foreground text-center">
            AI will generate original content using your configured provider, then run the full pipeline.
          </p>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(2)} className="flex-1 gap-2">
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} className="flex-1 gap-2 glow-accent">
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Generate
            </Button>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) resetForm(); }}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2 border-accent/30 hover:border-accent/60 hover:bg-accent/5">
          <Sparkles className="h-4 w-4 text-accent" />
          Generate with AI
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-sm flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" />
            AI Content Generator
            <span className="text-[10px] text-muted-foreground font-normal ml-auto">
              Step {step + 1} of {totalSteps}
            </span>
          </DialogTitle>
        </DialogHeader>
        <div className="flex gap-1">
          {Array.from({ length: totalSteps }, (_, i) => (
            <div
              key={i}
              className={cn(
                "h-1 flex-1 rounded-full transition-colors",
                i <= step ? "bg-accent" : "bg-muted"
              )}
            />
          ))}
        </div>
        {renderStep()}
      </DialogContent>
    </Dialog>
  );
}
