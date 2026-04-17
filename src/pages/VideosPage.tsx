import { useState } from "react";
import { motion } from "framer-motion";
import {
  Play, Clock, CheckCircle2, XCircle, Loader2, Film, Trash2,
  Download, Eye, HardDrive, Layers
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog";
import { useVideos, useUsedPosts, useDeleteVideo } from "@/hooks/use-api";
import { formatDistanceToNow } from "date-fns";
import { useToast } from "@/hooks/use-toast";
import type { VideoRecord } from "@/lib/api";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function formatFileSize(bytes?: number) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function VideoCard({ video, index, onPreview, onDelete }: {
  video: VideoRecord; index: number;
  onPreview: (video: VideoRecord, part: number) => void;
  onDelete: (video: VideoRecord) => void;
}) {
  const partCount = video.part_files?.length || (video.parts ?? (video.has_video ? 1 : 0));

  // Extract display label and sort number from filename e.g. "xxx_part1.mp4" → "Part 1"
  const getPartLabel = (idx: number) => {
    const filename = video.part_files?.[idx];
    if (filename) {
      const match = filename.match(/_part(\d+)\.mp4$/i);
      if (match) return `Part ${match[1]}`;
    }
    return `Part ${idx + 1}`;
  };

  const getPartNum = (idx: number) => {
    const filename = video.part_files?.[idx];
    const match = filename?.match(/_part(\d+)\.mp4$/i);
    return match ? parseInt(match[1], 10) : idx + 1;
  };

  // Sorted indices by part number
  const sortedIndices = Array.from({ length: partCount }, (_, i) => i)
    .sort((a, b) => getPartNum(a) - getPartNum(b));

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
    >
      <Card className="border-border bg-card hover:border-primary/30 transition-all overflow-hidden">
        <div className="relative h-36 bg-secondary flex items-center justify-center overflow-hidden">
          {video.has_thumbnails ? (
            <img
              src={`${API_BASE}/api/videos/${video.id}/thumbnail?part=0`}
              alt={video.title}
              className="absolute inset-0 w-full h-full object-cover"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          ) : (
            <>
              <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-accent/10" />
              <Play className="h-10 w-10 text-foreground/30" />
            </>
          )}
          <Badge
            variant={video.status === "published" ? "default" : "destructive"}
            className="absolute top-2 right-2 text-[10px] gap-1"
          >
            {video.status === "published" ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
            {video.status}
          </Badge>
          {video.render_time_s && (
            <span className="absolute bottom-2 right-2 rounded bg-background/80 px-1.5 py-0.5 text-[10px] font-mono">
              {video.render_time_s}s render
            </span>
          )}
        </div>

        <CardContent className="p-4 space-y-2">
          <h3 className="text-xs font-semibold line-clamp-2 leading-snug">{video.title}</h3>
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            <span className="font-mono">r/{video.subreddit}</span>
            <span>▲ {video.score.toLocaleString()}</span>
            <span>💬 {video.num_comments}</span>
          </div>

          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
            {partCount > 1 && (
              <span className="flex items-center gap-0.5">
                <Layers className="h-3 w-3" /> {partCount} parts
              </span>
            )}
            {video.file_size_bytes && (
              <span className="flex items-center gap-0.5">
                <HardDrive className="h-3 w-3" /> {formatFileSize(video.file_size_bytes)}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            <Clock className="h-3 w-3" />
            {video.created_at
              ? formatDistanceToNow(new Date(video.created_at), { addSuffix: true })
              : "—"}
          </div>

          <div className="flex flex-wrap gap-1.5 pt-1">
            {video.has_audio && <Badge variant="outline" className="text-[9px] px-1.5 py-0">Audio</Badge>}
            {video.has_video && <Badge variant="outline" className="text-[9px] px-1.5 py-0">Video</Badge>}
          </div>

          {/* Per-part buttons */}
          {video.has_video && (
            <div className="space-y-1.5 pt-2 border-t border-border mt-2">
              {partCount > 1 ? (
                sortedIndices.map((i) => (
                  <div key={i} className="flex gap-1.5 items-center">
                    <span className="text-[10px] text-muted-foreground w-12 shrink-0">{getPartLabel(i)}</span>
                    <Button size="sm" variant="outline" className="h-6 text-[10px] gap-1 flex-1"
                      onClick={() => onPreview(video, i)}>
                      <Eye className="h-3 w-3" /> Preview
                    </Button>
                    <Button size="sm" variant="outline" className="h-6 text-[10px] gap-1 flex-1"
                      onClick={() => window.open(`${API_BASE}/api/videos/${video.id}/download?part=${i}`, "_blank")}>
                      <Download className="h-3 w-3" /> Download
                    </Button>
                  </div>
                ))
              ) : (
                <div className="flex gap-1.5">
                  <Button size="sm" variant="outline" className="h-7 text-xs gap-1 flex-1"
                    onClick={() => onPreview(video, 0)}>
                    <Eye className="h-3 w-3" /> Preview
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 text-xs gap-1 flex-1"
                    onClick={() => window.open(`${API_BASE}/api/videos/${video.id}/download?part=0`, "_blank")}>
                    <Download className="h-3 w-3" /> Download
                  </Button>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end pt-1">
            <Button size="sm" variant="ghost" className="h-7 px-2 text-destructive hover:text-destructive"
              onClick={() => onDelete(video)}>
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function VideosPage() {
  const { data, isLoading } = useVideos();
  const { data: usedData } = useUsedPosts();
  const deleteMutation = useDeleteVideo();
  const { toast } = useToast();
  const videos = data?.videos ?? [];
  const usedPosts = usedData?.used_posts ?? [];

  const [preview, setPreview] = useState<{ video: VideoRecord; part: number } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<VideoRecord | null>(null);

  const published = videos.filter((v) => v.status === "published").length;
  const failed = videos.filter((v) => v.status === "failed").length;

  const handleDelete = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget.id, {
      onSuccess: () => { toast({ title: "Video deleted" }); setDeleteTarget(null); },
      onError: (e) => toast({ title: "Delete failed", description: e.message, variant: "destructive" }),
    });
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
      <div>
        <h2 className="text-xl font-bold">Video History</h2>
        <p className="text-xs text-muted-foreground mt-1">
          {videos.length} videos total · {published} published · {failed} failed
          {usedPosts.length > 0 && ` · ${usedPosts.length} posts used`}
        </p>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {!isLoading && videos.length === 0 && (
        <Card className="border-border bg-card">
          <CardContent className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Film className="h-12 w-12 mb-3 opacity-20" />
            <p className="text-sm font-medium">No videos generated yet</p>
            <p className="text-xs mt-1">Run the pipeline from the Dashboard to create your first video</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {videos.map((video, i) => (
          <VideoCard
            key={video.id} video={video} index={i}
            onPreview={(v, part) => setPreview({ video: v, part })}
            onDelete={setDeleteTarget}
          />
        ))}
      </div>

      {usedPosts.length > 0 && (
        <div className="space-y-3 pt-4">
          <h3 className="text-sm font-semibold text-muted-foreground">Used Post IDs</h3>
          <div className="flex flex-wrap gap-1.5">
            {usedPosts.map((id) => (
              <Badge key={id} variant="secondary" className="font-mono text-[10px]">{id}</Badge>
            ))}
          </div>
        </div>
      )}

      {/* Preview Dialog */}
      <Dialog open={!!preview} onOpenChange={() => setPreview(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-sm">{preview?.video.title}</DialogTitle>
            <DialogDescription className="text-xs">
              r/{preview?.video.subreddit} · {preview?.video.status}
              {(preview?.video.part_files?.length ?? 0) > 1 &&
                (() => {
                  const f = preview?.video.part_files?.[preview?.part ?? 0];
                  const m = f?.match(/_part(\d+)\.mp4$/i);
                  const label = m ? `Part ${m[1]}` : `Part ${(preview?.part ?? 0) + 1}`;
                  return ` · ${label} of ${preview?.video.part_files?.length}`;
                })()}
            </DialogDescription>
          </DialogHeader>
          {preview && (
            <div className="space-y-3">
              <video
                key={`${preview.video.id}-${preview.part}`}
                controls autoPlay
                className="w-full rounded-lg bg-secondary max-h-[50vh]"
                src={`${API_BASE}/api/videos/${preview.video.id}/stream?part=${preview.part}`}
              />
              <div className="flex flex-wrap items-center gap-2">
                {(preview.video.part_files?.length ?? 0) > 1 && (
                  <div className="flex flex-wrap gap-1 mr-auto">
                    {Array.from({ length: preview.video.part_files!.length }, (_, i) => {
                      const f = preview.video.part_files![i];
                      const m = f?.match(/_part(\d+)\.mp4$/i);
                      const num = m ? parseInt(m[1], 10) : i + 1;
                      const label = m ? `Part ${m[1]}` : `Part ${i + 1}`;
                      return { idx: i, num, label };
                    })
                      .sort((a, b) => a.num - b.num)
                      .map(({ idx, label }) => (
                        <Button key={idx} size="sm"
                          variant={idx === preview.part ? "default" : "outline"}
                          className="h-7 text-xs px-2.5"
                          onClick={() => setPreview({ ...preview, part: idx })}
                        >
                          {label}
                        </Button>
                      ))}
                  </div>
                )}
                <Button size="sm" variant="outline" className="gap-1"
                  onClick={() => window.open(`${API_BASE}/api/videos/${preview.video.id}/download?part=${preview.part}`, "_blank")}>
                  <Download className="h-3 w-3" /> Download
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Video</DialogTitle>
            <DialogDescription className="text-xs">
              This will permanently delete "{deleteTarget?.title}" and all associated files.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4 mr-1" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
