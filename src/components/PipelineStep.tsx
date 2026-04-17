import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Circle, Loader2, AlertCircle, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";
import type { PipelineSubStep } from "@/lib/api";

export type StepStatus = "idle" | "running" | "done" | "error";

interface PipelineStepProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  status: StepStatus;
  index: number;
  isLast?: boolean;
  subSteps?: PipelineSubStep[];
}

const statusConfig: Record<StepStatus, { color: string; StatusIcon: typeof Circle }> = {
  idle: { color: "text-muted-foreground", StatusIcon: Circle },
  running: { color: "text-primary", StatusIcon: Loader2 },
  done: { color: "text-success", StatusIcon: CheckCircle2 },
  error: { color: "text-destructive", StatusIcon: AlertCircle },
};

const subStatusIcon: Record<string, React.ReactNode> = {
  pending: <Circle className="h-2.5 w-2.5 text-muted-foreground" />,
  running: <Loader2 className="h-2.5 w-2.5 animate-spin text-primary" />,
  done: <CheckCircle2 className="h-2.5 w-2.5 text-success" />,
  error: <AlertCircle className="h-2.5 w-2.5 text-destructive" />,
};

export function PipelineStep({ title, description, icon, status, index, isLast, subSteps }: PipelineStepProps) {
  const { color, StatusIcon } = statusConfig[status];
  const hasSubSteps = subSteps && subSteps.length > 0;
  const [expanded, setExpanded] = useState(true);

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className="flex gap-4"
    >
      {/* Connector line */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-xl border transition-all duration-300",
            status === "running" && "border-primary bg-primary/10 glow-primary",
            status === "done" && "border-success bg-success/10",
            status === "error" && "border-destructive bg-destructive/10",
            status === "idle" && "border-border bg-secondary"
          )}
        >
          {status === "running" ? (
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          ) : (
            <span className={cn("h-5 w-5", color)}>{icon}</span>
          )}
        </div>
        {!isLast && (
          <div
            className={cn(
              "w-px flex-1 min-h-[2rem] transition-colors duration-500",
              status === "done" ? "bg-success/50" : "bg-border"
            )}
          />
        )}
      </div>

      {/* Content */}
      <div className="pb-8 flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3
            className={cn(
              "font-semibold text-sm",
              status === "idle" ? "text-muted-foreground" : "text-foreground"
            )}
          >
            {title}
          </h3>
          <StatusIcon className={cn("h-3.5 w-3.5", color, status === "running" && "animate-spin")} />
          {hasSubSteps && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-180")} />
            </button>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>

        {/* Sub-steps */}
        <AnimatePresence>
          {hasSubSteps && expanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-2 space-y-1 border-l-2 border-border pl-3 ml-1">
                {subSteps.map((ss, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    {subStatusIcon[ss.status] || subStatusIcon.pending}
                    <span className={cn(
                      "font-medium",
                      ss.status === "done" ? "text-muted-foreground" :
                      ss.status === "running" ? "text-foreground" :
                      ss.status === "error" ? "text-destructive" :
                      "text-muted-foreground/70"
                    )}>
                      {ss.label}
                    </span>
                    {ss.detail && (
                      <span className="text-muted-foreground/60 truncate">{ss.detail}</span>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
