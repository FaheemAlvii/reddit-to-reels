import { useState } from "react";
import { PenLine, ArrowRight, ArrowLeft, Play, Loader2, Film, Scissors, MessageSquare, BookOpen, Mic, MicOff, Plus, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";

const VIDEO_MODES = [
  { id: "short_reel", label: "Short Reel", icon: Scissors, desc: "< 60s vertical video" },
  { id: "full_video", label: "Full Video", icon: Film, desc: "Full-length horizontal" },
  { id: "reel", label: "Reel", icon: Film, desc: "60-90s vertical format" },
];

const FORMAT_MODES = [
  { id: "story", label: "Story Mode", icon: BookOpen, desc: "Narrated story format" },
  { id: "qa", label: "Q&A Mode", icon: MessageSquare, desc: "Question & answer style" },
];

interface QaComment {
  author: string;
  body: string;
}

export function GenerateFromCustomDialog() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [formatMode, setFormatMode] = useState("story");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [comments, setComments] = useState<QaComment[]>([{ author: "", body: "" }]);
  const [videoMode, setVideoMode] = useState("short_reel");
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const { toast } = useToast();
  const qc = useQueryClient();

  const totalSteps = 4;

  const addComment = () => setComments((prev) => [...prev, { author: "", body: "" }]);
  const removeComment = (i: number) => setComments((prev) => prev.filter((_, idx) => idx !== i));
  const updateComment = (i: number, field: keyof QaComment, value: string) =>
    setComments((prev) => prev.map((c, idx) => (idx === i ? { ...c, [field]: value } : c)));

  const canProceedContent = title.trim().length > 0 && content.trim().length > 0;
  const canProceedComments = formatMode === "story" || comments.some((c) => c.body.trim().length > 0);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const params: Parameters<typeof api.runPipelineCustom>[0] = {
        title, content, format_mode: formatMode,
        video_mode: videoMode, tts_enabled: ttsEnabled,
      };
      if (formatMode === "qa") {
        params.comments = comments.filter((c) => c.body.trim()).map((c) => ({
          author: c.author.trim() || "Anonymous",
          body: c.body.trim(),
        }));
      }
      await api.runPipelineCustom(params);
      toast({ title: "Pipeline started", description: "Generating video from custom content..." });
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
    setFormatMode("story");
    setTitle("");
    setContent("");
    setComments([{ author: "", body: "" }]);
    setVideoMode("short_reel");
    setTtsEnabled(true);
  };

  const renderStep = () => {
    // Step 0: Choose mode
    if (step === 0) {
      return (
        <div className="space-y-4">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Content Type</Label>
          <div className="grid grid-cols-1 gap-2">
            {FORMAT_MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => setFormatMode(m.id)}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border text-left transition-all",
                  formatMode === m.id
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
          <Button onClick={() => setStep(1)} className="w-full gap-2">
            Next <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      );
    }

    // Step 1: Enter content
    if (step === 1) {
      return (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Title</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={formatMode === "qa" ? "What's the craziest thing that happened at your job?" : "The neighbor's midnight ritual"}
              className="h-9 text-xs bg-secondary border-border"
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">
              {formatMode === "qa" ? "Question / Context" : "Story Content"}
            </Label>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={formatMode === "qa" ? "Describe your question or add context..." : "Write your story here..."}
              className="min-h-[120px] text-xs bg-secondary border-border resize-none"
            />
            <p className="text-[10px] text-muted-foreground text-right">{content.length} chars</p>
          </div>

          {formatMode === "qa" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs text-muted-foreground">Answers / Comments</Label>
                <Button variant="outline" size="sm" onClick={addComment} className="h-6 text-[10px] px-2 gap-1">
                  <Plus className="h-3 w-3" /> Add
                </Button>
              </div>
              <ScrollArea className="max-h-[180px]">
                <div className="space-y-2 pr-2">
                  {comments.map((c, i) => (
                    <div key={i} className="flex gap-2 items-start">
                      <div className="flex-1 space-y-1">
                        <Input
                          value={c.author}
                          onChange={(e) => updateComment(i, "author", e.target.value)}
                          placeholder={`Author ${i + 1}`}
                          className="h-7 text-[10px] bg-secondary border-border"
                        />
                        <Textarea
                          value={c.body}
                          onChange={(e) => updateComment(i, "body", e.target.value)}
                          placeholder="Write the answer..."
                          className="min-h-[50px] text-[10px] bg-secondary border-border resize-none"
                        />
                      </div>
                      {comments.length > 1 && (
                        <Button variant="ghost" size="sm" onClick={() => removeComment(i)} className="h-7 w-7 p-0 text-destructive">
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(0)} className="flex-1 gap-2">
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <Button onClick={() => setStep(2)} disabled={!canProceedContent || !canProceedComments} className="flex-1 gap-2">
              Next <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      );
    }

    // Step 2: Video mode & TTS
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
      const validComments = comments.filter((c) => c.body.trim());
      return (
        <div className="space-y-4">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Review</Label>
          <div className="space-y-2 rounded-lg border border-border bg-secondary/30 p-3">
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground">Type</span>
              <span className="font-medium">{formatMode === "qa" ? "Q&A" : "Story"}</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground">Title</span>
              <span className="font-medium truncate ml-4 max-w-[200px]">{title}</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="text-muted-foreground">Content</span>
              <span className="font-medium">{content.length} chars</span>
            </div>
            {formatMode === "qa" && (
              <div className="flex justify-between text-[10px]">
                <span className="text-muted-foreground">Answers</span>
                <span className="font-medium">{validComments.length}</span>
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

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(2)} className="flex-1 gap-2">
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <Button onClick={handleSubmit} disabled={submitting} className="flex-1 gap-2 glow-primary">
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
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
        <Button variant="outline" className="gap-2">
          <PenLine className="h-4 w-4" />
          Write Your Own
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-sm flex items-center gap-2">
            <PenLine className="h-4 w-4 text-primary" />
            Custom Content
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
                i <= step ? "bg-primary" : "bg-muted"
              )}
            />
          ))}
        </div>
        {renderStep()}
      </DialogContent>
    </Dialog>
  );
}