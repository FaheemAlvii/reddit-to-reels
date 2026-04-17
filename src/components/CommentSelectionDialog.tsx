import { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Loader2, Play, Filter, CheckSquare, Square, MessageSquare, ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useRunPipeline } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";
import type { RedditPost } from "@/lib/api";

interface Comment {
  index: number;
  author: string;
  body: string;
  score: number;
  char_count: number;
}

const TTS_MAX_CHARS = 200; // matches backend StreamlabsTTS.MAX_TEXT_LENGTH

function estimateSegments(charCount: number): number {
  if (charCount <= TTS_MAX_CHARS) return 1;
  return Math.ceil(charCount / TTS_MAX_CHARS);
}

interface CommentSelectionDialogProps {
  post: RedditPost | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Label for the action button */
  actionLabel?: string;
}

export function CommentSelectionDialog({
  post,
  open,
  onOpenChange,
  actionLabel = "Create Reel",
}: CommentSelectionDialogProps) {
  const [selectComments, setSelectComments] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [selectedComments, setSelectedComments] = useState<number[]>([]);
  const [maxCharLimit, setMaxCharLimit] = useState(0);
  const [loadingComments, setLoadingComments] = useState(false);
  const [commentsLoaded, setCommentsLoaded] = useState(false);

  const runPipeline = useRunPipeline();
  const { toast } = useToast();

  const filteredComments = maxCharLimit > 0
    ? comments.filter((c) => c.char_count <= maxCharLimit)
    : comments;

  const handleToggle = async (enabled: boolean) => {
    setSelectComments(enabled);
    if (enabled && !commentsLoaded && post) {
      setLoadingComments(true);
      try {
        const res = await api.fetchPostComments({ post_id: post.id });
        setComments(res.comments);
        setSelectedComments(res.comments.map((c) => c.index));
        setCommentsLoaded(true);
      } catch (e: any) {
        toast({ title: "Failed to fetch comments", description: e.message, variant: "destructive" });
        setSelectComments(false);
      } finally {
        setLoadingComments(false);
      }
    }
  };

  const toggleComment = (index: number) => {
    setSelectedComments((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  };

  const handleRun = () => {
    if (!post) return;
    const params: { post_id: string; selected_comments?: number[]; max_comment_chars?: number } = {
      post_id: post.id,
    };
    if (selectComments) {
      params.selected_comments = selectedComments;
      if (maxCharLimit > 0) params.max_comment_chars = maxCharLimit;
    }
    runPipeline.mutate(params, {
      onSuccess: () => {
        toast({ title: "Pipeline started", description: `Creating reel from "${post.title}"` });
        handleClose();
      },
      onError: (e) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
    });
  };

  const handleClose = () => {
    onOpenChange(false);
    // Reset state
    setTimeout(() => {
      setSelectComments(false);
      setComments([]);
      setSelectedComments([]);
      setMaxCharLimit(0);
      setCommentsLoaded(false);
    }, 200);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-sm leading-snug">{post?.title}</DialogTitle>
          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
            <Badge variant="outline" className="text-[10px] font-mono">r/{post?.subreddit}</Badge>
            <span>▲ {post?.score?.toLocaleString()}</span>
            <span>💬 {post?.num_comments}</span>
          </div>
        </DialogHeader>

        {post?.selftext && (
          <div className="max-h-32 overflow-y-auto rounded-md bg-secondary p-3 text-xs text-muted-foreground leading-relaxed">
            {post.selftext}
          </div>
        )}

        {/* Comment Selection Toggle */}
        <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/50">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary" />
            <div>
              <p className="text-xs font-medium">Select Comments</p>
              <p className="text-[10px] text-muted-foreground">Choose which comments to include</p>
            </div>
          </div>
          <Switch checked={selectComments} onCheckedChange={handleToggle} />
        </div>

        {/* Comment Selection Panel */}
        {selectComments && (
          <div className="space-y-3">
            {/* Char limit filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <Input
                type="number"
                value={maxCharLimit || ""}
                onChange={(e) => {
                  const v = parseInt(e.target.value) || 0;
                  setMaxCharLimit(v);
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

            {/* Select/Deselect all + stats */}
            <div className="flex items-center gap-2 flex-wrap">
              <Button variant="outline" size="sm" onClick={() => setSelectedComments(filteredComments.map((c) => c.index))} className="h-6 text-[10px] px-2">
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={() => setSelectedComments([])} className="h-6 text-[10px] px-2">
                Deselect All
              </Button>
              <span className="text-[10px] text-muted-foreground ml-auto">
                {selectedComments.length}/{filteredComments.length} selected
              </span>
            </div>

            {/* Total stats for selected comments */}
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

            {loadingComments ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="ml-2 text-xs text-muted-foreground">Fetching comments...</span>
              </div>
            ) : (
              <ScrollArea className="h-[240px] rounded-lg border border-border">
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
          </div>
        )}

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            size="sm"
            variant="outline"
            className="gap-1"
            onClick={() => window.open(`https://reddit.com${post?.permalink}`, "_blank")}
          >
            <ExternalLink className="h-3 w-3" /> Open on Reddit
          </Button>
          <Button
            size="sm"
            className="gap-1"
            disabled={runPipeline.isPending || (selectComments && selectedComments.length === 0)}
            onClick={handleRun}
          >
            {runPipeline.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Play className="h-3 w-3" />
            )}
            {actionLabel}
            {selectComments && ` (${selectedComments.length})`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
