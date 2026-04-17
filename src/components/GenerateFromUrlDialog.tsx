import { useState } from "react";
import { Link2, ArrowRight, ArrowLeft, Play, Loader2, Film, Scissors, MessageSquare, BookOpen, Mic, MicOff, Search, CheckSquare, Square, Filter } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

interface Comment {
  index: number;
  author: string;
  body: string;
  score: number;
  char_count: number;
}

const TTS_MAX_CHARS = 200;
function estimateSegments(charCount: number): number {
  if (charCount <= TTS_MAX_CHARS) return 1;
  return Math.ceil(charCount / TTS_MAX_CHARS);
}

export function GenerateFromUrlDialog() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [url, setUrl] = useState("");
  const [videoMode, setVideoMode] = useState("short_reel");
  const [formatMode, setFormatMode] = useState("qa");
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Comment selection state
  const [comments, setComments] = useState<Comment[]>([]);
  const [selectedComments, setSelectedComments] = useState<number[]>([]);
  const [maxCharLimit, setMaxCharLimit] = useState(0);
  const [loadingComments, setLoadingComments] = useState(false);
  const [postTitle, setPostTitle] = useState("");

  const { toast } = useToast();
  const qc = useQueryClient();

  const isValidUrl = url.trim().length > 0 && (url.includes("reddit.com") || url.includes("redd.it"));
  const totalSteps = formatMode === "qa" ? 4 : 3;

  const filteredComments = maxCharLimit > 0
    ? comments.filter((c) => c.char_count <= maxCharLimit)
    : comments;

  const fetchComments = async () => {
    setLoadingComments(true);
    try {
      const res = await api.fetchPostComments({ url });
      setComments(res.comments);
      setPostTitle(res.title);
      setSelectedComments(res.comments.map((c) => c.index));
    } catch (e: any) {
      toast({ title: "Failed to fetch comments", description: e.message, variant: "destructive" });
    } finally {
      setLoadingComments(false);
    }
  };

  const toggleComment = (index: number) => {
    setSelectedComments((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const selectAll = () => setSelectedComments(filteredComments.map((c) => c.index));
  const deselectAll = () => setSelectedComments([]);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const params: any = { url, video_mode: videoMode, format_mode: formatMode, tts_enabled: ttsEnabled };
      if (formatMode === "qa") {
        // Send selected in the order user picked (which is the order they appear in selectedComments)
        params.selected_comments = selectedComments;
        if (maxCharLimit > 0) params.max_comment_chars = maxCharLimit;
      }
      await api.runPipelineFromUrl(params);
      toast({ title: "Pipeline started", description: "Generating video from URL..." });
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
    setUrl("");
    setVideoMode("short_reel");
    setFormatMode("qa");
    setTtsEnabled(true);
    setComments([]);
    setSelectedComments([]);
    setMaxCharLimit(0);
    setPostTitle("");
  };

  const handleFormatNext = () => {
    if (formatMode === "qa") {
      fetchComments();
      setStep(3);
    } else {
      // Skip comment selection for story mode, go to final
      setStep(3);
    }
  };

  // Dynamic step rendering
  const renderStep = () => {
    // Step 0: URL
    if (step === 0) {
      return (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Reddit Post URL</Label>
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://reddit.com/r/AskReddit/comments/..."
              className="h-9 text-xs bg-secondary border-border font-mono"
              autoFocus
            />
            <p className="text-[10px] text-muted-foreground">Paste any Reddit post URL (reddit.com or redd.it links)</p>
          </div>
          <Button onClick={() => setStep(1)} disabled={!isValidUrl} className="w-full gap-2">
            Next <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      );
    }

    // Step 1: Video Mode
    if (step === 1) {
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

    // Step 2: Format & TTS
    if (step === 2) {
      return (
        <div className="space-y-4">
          <Label className="text-xs text-muted-foreground uppercase tracking-wider">Content Style</Label>
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
            <Button onClick={handleFormatNext} className="flex-1 gap-2">
              {formatMode === "qa" ? (
                <>Next <ArrowRight className="h-3.5 w-3.5" /></>
              ) : (
                <>
                  {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                  Generate
                </>
              )}
            </Button>
          </div>
        </div>
      );
    }

    // Step 3: Comment Selection (Q&A only) or Generate (story mode)
    if (step === 3) {
      if (formatMode !== "qa") {
        // Story mode - just generate
        return (
          <div className="space-y-4 text-center py-4">
            <p className="text-xs text-muted-foreground">Ready to generate in Story Mode</p>
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

      // Q&A mode - show comment picker
      return (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs text-muted-foreground uppercase tracking-wider">Select Comments</Label>
            <span className="text-[10px] text-muted-foreground">
              {selectedComments.length}/{filteredComments.length} selected
            </span>
          </div>

          {/* Total stats */}
          {selectedComments.length > 0 && (
            <div className="flex items-center gap-3 px-2 py-1.5 rounded-md bg-primary/5 border border-primary/20">
              {(() => {
                const selComments = comments.filter((c) => selectedComments.includes(c.index));
                const totalChars = selComments.reduce((sum, c) => sum + c.char_count, 0);
                const totalSegments = selComments.reduce((sum, c) => sum + estimateSegments(c.char_count), 0);
                return (
                  <>
                    <span className="text-[10px] text-foreground font-medium">
                      {totalChars.toLocaleString()} total chars
                    </span>
                    <span className="text-[10px] text-muted-foreground">•</span>
                    <span className="text-[10px] text-foreground font-medium">
                      ~{totalSegments} TTS segment{totalSegments !== 1 ? "s" : ""}
                    </span>
                  </>
                );
              })()}
            </div>
          )}

          {/* Char limit filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <Input
              type="number"
              value={maxCharLimit || ""}
              onChange={(e) => {
                const v = parseInt(e.target.value) || 0;
                setMaxCharLimit(v);
                // Re-filter selections
                if (v > 0) {
                  setSelectedComments((prev) =>
                    prev.filter((i) => {
                      const c = comments.find((c) => c.index === i);
                      return c && c.char_count <= v;
                    })
                  );
                }
              }}
              placeholder="Max character limit (0 = no limit)"
              className="h-7 text-[10px] bg-secondary border-border"
            />
          </div>

          {/* Select/Deselect all */}
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={selectAll} className="h-6 text-[10px] px-2">
              Select All
            </Button>
            <Button variant="outline" size="sm" onClick={deselectAll} className="h-6 text-[10px] px-2">
              Deselect All
            </Button>
          </div>

          {loadingComments ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-xs text-muted-foreground">Fetching comments...</span>
            </div>
          ) : (
            <ScrollArea className="h-[280px] rounded-lg border border-border">
              <div className="space-y-1 p-2">
                {filteredComments.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-4">No comments match the filter</p>
                ) : (
                  filteredComments.map((c) => {
                    const isSelected = selectedComments.includes(c.index);
                    return (
                      <button
                        key={c.index}
                        onClick={() => toggleComment(c.index)}
                        className={cn(
                          "w-full flex items-start gap-2 p-2 rounded-md border text-left transition-all",
                          isSelected
                            ? "border-primary/50 bg-primary/5"
                            : "border-transparent bg-secondary/30 hover:bg-secondary/60"
                        )}
                      >
                        {isSelected ? (
                          <CheckSquare className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
                        ) : (
                          <Square className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                             <span className="text-[10px] font-medium text-foreground">{c.author}</span>
                             <span className="text-[10px] text-primary">▲ {c.score}</span>
                             <span className="text-[10px] text-muted-foreground ml-auto">
                               {c.char_count} chars · ~{estimateSegments(c.char_count)} seg
                             </span>
                           </div>
                          <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">{c.body}</p>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </ScrollArea>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setStep(2)} className="flex-1 gap-2">
              <ArrowLeft className="h-3.5 w-3.5" /> Back
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={submitting || selectedComments.length === 0}
              className="flex-1 gap-2 glow-primary"
            >
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Generate ({selectedComments.length})
            </Button>
          </div>
        </div>
      );
    }

    return null;
  };

  const currentStepLabel = step === 3 && formatMode === "qa" ? "Select Comments" : `Step ${step + 1}`;

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) resetForm(); }}>
      <DialogTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Link2 className="h-4 w-4" />
          Generate from URL
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-sm flex items-center gap-2">
            <Link2 className="h-4 w-4 text-primary" />
            Generate from URL
            <span className="text-[10px] text-muted-foreground font-normal ml-auto">
              Step {Math.min(step + 1, totalSteps)} of {totalSteps}
            </span>
          </DialogTitle>
        </DialogHeader>
        {/* Step indicator */}
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
