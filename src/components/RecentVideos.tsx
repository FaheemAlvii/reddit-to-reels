import { useState } from "react";
import { motion } from "framer-motion";
import { Play, Clock, CheckCircle2, XCircle, Loader2, Download, Eye, Layers, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useVideos, useResumeVideo } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";
import { formatDistanceToNow } from "date-fns";
import type { VideoRecord } from "@/lib/api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const statusStyles: Record<string, string> = {
  published: "",
  rendering: "border-warning text-warning animate-pulse-glow",
  failed: "border-destructive text-destructive",
  audio_only: "border-warning text-warning",
};

const StatusIcon = ({ status }: { status: string }) => {
  if (status === "published") return <CheckCircle2 className="h-3 w-3 text-success" />;
  if (status === "rendering") return <Loader2 className="h-3 w-3 animate-spin text-warning" />;
  if (status === "audio_only") return <RefreshCw className="h-3 w-3 text-warning" />;
  return <XCircle className="h-3 w-3 text-destructive" />;
};

function getPartLabel(video: VideoRecord, index: number) {
  const filename = video.part_files?.[index];
  if (filename) {
    const match = filename.match(/_part(\d+)\.mp4$/i);
    if (match) return `Part ${match[1]}`;
  }
  return `Part ${index + 1}`;
}

export function RecentVideos() {
  const { data, isLoading } = useVideos();
  const videos = data?.videos ?? [];
  const [selected, setSelected] = useState<{ video: VideoRecord; part: number } | null>(null);
  const resumeMutation = useResumeVideo();
  const { toast } = useToast();

  const partCount = (v?: VideoRecord) => v?.part_files?.length || (v?.parts ?? (v?.has_video ? 1 : 0));

  const handleResume = (e: React.MouseEvent, videoId: string) => {
    e.stopPropagation();
    resumeMutation.mutate(videoId, {
      onSuccess: () => toast({ title: "Resuming video", description: "Video generation started from existing audio." }),
      onError: (err) => toast({ title: "Resume failed", description: err.message, variant: "destructive" }),
    });
  };

  return (
    <>
      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            Recent Videos
            {videos.length > 0 && (
              <span className="ml-2 text-xs font-normal text-muted-foreground">({videos.length})</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 max-h-[600px] overflow-y-auto">
          {isLoading && (
            <div className="text-center py-6">
              <Loader2 className="h-5 w-5 mx-auto animate-spin text-muted-foreground" />
            </div>
          )}
          {!isLoading && videos.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Play className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No videos generated yet</p>
              <p className="text-xs mt-1">Run the pipeline to create your first video</p>
            </div>
          )}
          {videos.map((video, i) => (
            <motion.div
              key={video.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="group flex items-start gap-3 rounded-lg border border-border bg-secondary/30 p-3 hover:border-primary/30 transition-all cursor-pointer"
              onClick={() => video.has_video && setSelected({ video, part: 0 })}
            >
              <div className="relative flex h-16 w-24 shrink-0 items-center justify-center rounded-md bg-secondary overflow-hidden">
                {video.has_thumbnails ? (
                  <img
                    src={`${API_BASE}/api/videos/${video.id}/thumbnail?part=0`}
                    alt={video.title}
                    className="absolute inset-0 w-full h-full object-cover"
                    onError={(e) => { e.currentTarget.style.display = 'none'; }}
                  />
                ) : (
                  <>
                    <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-accent/20" />
                    <Play className="h-5 w-5 text-foreground/60 group-hover:text-primary transition-colors" />
                  </>
                )}
                {video.render_time_s && (
                  <span className="absolute bottom-1 right-1 rounded bg-background/80 px-1 py-0.5 text-[10px] font-mono">
                    {video.render_time_s}s
                  </span>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <h4 className="text-xs font-semibold leading-snug line-clamp-2 text-foreground">
                  {video.title}
                </h4>
                <div className="mt-1.5 flex items-center gap-2">
                  <Badge
                    variant={video.status === "published" ? "default" : "outline"}
                    className={`text-[10px] px-1.5 py-0 gap-0.5 ${statusStyles[video.status] || ""}`}
                  >
                    <StatusIcon status={video.status} />
                    {video.status}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground font-mono">r/{video.subreddit}</span>
                </div>
                <div className="mt-1 flex items-center gap-3 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-0.5">
                    <Clock className="h-3 w-3" />
                    {video.created_at
                      ? formatDistanceToNow(new Date(video.created_at), { addSuffix: true })
                      : "—"}
                  </span>
                  {partCount(video) > 1 && (
                    <span className="flex items-center gap-0.5">
                      <Layers className="h-3 w-3" /> {partCount(video)} parts
                    </span>
                  )}
                </div>
                {video.status === "audio_only" && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-1.5 h-6 text-[10px] gap-1 px-2 border-primary/40 text-primary hover:bg-primary/10"
                    onClick={(e) => handleResume(e, video.id)}
                    disabled={resumeMutation.isPending}
                  >
                    <RefreshCw className="h-3 w-3" />
                    {resumeMutation.isPending ? "Resuming..." : "Resume Video"}
                  </Button>
                )}
              </div>
            </motion.div>
          ))}
        </CardContent>
      </Card>

      {/* Video Preview/Download Dialog */}
      <Dialog open={!!selected} onOpenChange={() => setSelected(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-sm">{selected?.video.title}</DialogTitle>
            <DialogDescription className="text-xs">
              r/{selected?.video.subreddit} · {selected?.video.status}
              {partCount(selected?.video!) > 1 && ` · ${getPartLabel(selected?.video!, selected?.part ?? 0)}`}
            </DialogDescription>
          </DialogHeader>
          {selected && (
            <div className="space-y-3">
              <video
                key={`${selected.video.id}-${selected.part}`}
                controls
                autoPlay
                className="w-full rounded-lg bg-secondary max-h-[60vh]"
                src={`${API_BASE}/api/videos/${selected.video.id}/stream?part=${selected.part}`}
              />
              <div className="flex items-center gap-2">
                {partCount(selected.video) > 1 && (
                  <div className="flex gap-1 mr-auto flex-wrap">
                    {Array.from({ length: partCount(selected.video) }, (_, i) => ({
                      index: i,
                      label: getPartLabel(selected.video, i),
                      num: (() => {
                        const f = selected.video.part_files?.[i];
                        const m = f?.match(/_part(\d+)\.mp4$/i);
                        return m ? parseInt(m[1], 10) : i + 1;
                      })(),
                    }))
                      .sort((a, b) => a.num - b.num)
                      .map(({ index: idx, label }) => (
                        <Button
                          key={idx}
                          size="sm"
                          variant={idx === selected.part ? "default" : "outline"}
                          className="h-7 text-xs px-2.5"
                          onClick={() => setSelected({ ...selected, part: idx })}
                        >
                          {label}
                        </Button>
                      ))}
                  </div>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1"
                  onClick={() =>
                    window.open(
                      `${API_BASE}/api/videos/${selected.video.id}/download?part=${selected.part}`,
                      "_blank"
                    )
                  }
                >
                  <Download className="h-3 w-3" /> Download
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
