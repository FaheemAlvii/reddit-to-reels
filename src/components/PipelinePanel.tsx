import { Search, FileText, Mic, Film, Send, XCircle, Sparkles, Image } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PipelineStep } from "./PipelineStep";
import { GenerateWithAIDialog } from "./GenerateWithAIDialog";
import { usePipelineStatus, useRunPipeline, useResetPipeline, useCancelPipeline } from "@/hooks/use-api";
import { useToast } from "@/hooks/use-toast";
import type { StepStatus } from "./PipelineStep";

const STEP_ICONS: Record<string, React.ReactNode> = {
  ai_generate: <Sparkles className="h-5 w-5" />,
  fetch: <Search className="h-5 w-5" />,
  format: <FileText className="h-5 w-5" />,
  tts: <Mic className="h-5 w-5" />,
  video: <Film className="h-5 w-5" />,
  thumbnail: <Image className="h-5 w-5" />,
  notify: <Send className="h-5 w-5" />,
};

const STEP_DESCRIPTIONS: Record<string, string> = {
  ai_generate: "Generate content using AI provider",
  fetch: "Scan subreddits and find a post matching filters",
  format: "Clean and structure the story for narration",
  tts: "Convert story text to speech with chosen voice",
  video: "Compose video with captions over background footage",
  thumbnail: "Generate Reddit-style thumbnails for each part",
  notify: "Send Discord notification and upload output",
};

export function PipelinePanel() {
  const { data: pipeline } = usePipelineStatus();
  const runMutation = useRunPipeline();
  const resetMutation = useResetPipeline();
  const cancelMutation = useCancelPipeline();
  const { toast } = useToast();

  const steps = pipeline?.steps ?? [];
  const isRunning = pipeline?.is_running ?? false;
  const allDone = steps.length > 0 && steps.every((s) => s.status === "done");
  const hasError = pipeline?.error != null;

  const handleCancel = () => {
    cancelMutation.mutate(undefined, {
      onSuccess: () => toast({ title: "Pipeline cancelled", description: "The current run has been aborted." }),
      onError: (e) => toast({ title: "Cancel failed", description: e.message, variant: "destructive" }),
    });
  };

  return (
    <Card className="border-border bg-card">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Pipeline</CardTitle>
          {(allDone || hasError) && !isRunning && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => resetMutation.mutate()}
              className="text-xs"
            >
              Reset
            </Button>
          )}
        </div>
        {pipeline?.current_post && (
          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">
            ▸ {pipeline.current_post.title}
          </p>
        )}
      </CardHeader>
      <CardContent>
        <div className="space-y-0">
          {steps.map((step, i) => (
            <PipelineStep
              key={step.id}
              title={step.title}
              description={step.detail || STEP_DESCRIPTIONS[step.id] || ""}
              icon={STEP_ICONS[step.id] || <Search className="h-5 w-5" />}
              status={step.status as StepStatus}
              index={i}
              isLast={i === steps.length - 1}
              subSteps={step.sub_steps}
            />
          ))}
        </div>

        {pipeline?.error && (
          <p className="text-xs text-destructive mt-2 mb-2 font-mono">{pipeline.error}</p>
        )}

        <div className="flex gap-2 mt-2">
          <Button
            onClick={() => runMutation.mutate(undefined)}
            disabled={isRunning || runMutation.isPending}
            className="flex-1 glow-primary font-semibold"
          >
            {isRunning ? "Running Pipeline..." : allDone ? "Run Again" : "Start Pipeline"}
          </Button>
          {isRunning && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleCancel}
              disabled={cancelMutation.isPending}
              className="gap-1 px-3"
            >
              <XCircle className="h-4 w-4" />
              Cancel
            </Button>
          )}
        </div>

        <div className="mt-2">
          <GenerateWithAIDialog />
        </div>
      </CardContent>
    </Card>
  );
}
