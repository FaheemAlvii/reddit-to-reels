import { motion } from "framer-motion";
import { ArrowUpCircle, MessageCircle, Clock, ExternalLink, Ban, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface PostCardProps {
  title: string;
  subreddit: string;
  score: number;
  comments: number;
  age: string;
  selftext?: string;
  isSelected?: boolean;
  onSelect?: () => void;
  index?: number;
  meetsFilters?: boolean;
  alreadyUsed?: boolean;
  filterReason?: string | null;
}

export function PostCard({
  title,
  subreddit,
  score,
  comments,
  age,
  selftext,
  isSelected,
  onSelect,
  index = 0,
  meetsFilters = true,
  alreadyUsed = false,
  filterReason,
}: PostCardProps) {
  const isDisabled = !meetsFilters || alreadyUsed;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      onClick={onSelect}
      className={cn(
        "group rounded-xl border bg-card p-4 transition-all duration-200 cursor-pointer",
        isDisabled
          ? "opacity-60 border-border hover:border-muted-foreground/30"
          : "hover:border-primary/40",
        isSelected && "border-primary bg-primary/5 glow-primary"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-2">
            <Badge variant="outline" className="text-xs font-mono border-accent/30 text-accent">
              r/{subreddit}
            </Badge>
            {alreadyUsed && (
              <Badge variant="secondary" className="text-[10px] gap-0.5">
                <CheckCircle2 className="h-2.5 w-2.5" /> Used
              </Badge>
            )}
            {!meetsFilters && !alreadyUsed && filterReason && (
              <Tooltip>
                <TooltipTrigger>
                  <Badge variant="outline" className="text-[10px] gap-0.5 border-destructive/30 text-destructive">
                    <Ban className="h-2.5 w-2.5" /> Filtered
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="top" className="text-xs max-w-xs">
                  {filterReason}
                </TooltipContent>
              </Tooltip>
            )}
          </div>
          <h3 className={cn(
            "font-semibold text-sm leading-snug line-clamp-2 transition-colors",
            isDisabled ? "text-muted-foreground" : "text-foreground group-hover:text-primary"
          )}>
            {title}
          </h3>
          {selftext && (
            <p className="mt-2 text-xs text-muted-foreground line-clamp-2">{selftext}</p>
          )}
        </div>
        {!isDisabled && (
          <Button
            size="icon"
            variant="ghost"
            className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <ExternalLink className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <ArrowUpCircle className="h-3.5 w-3.5 text-primary" />
          {score.toLocaleString()}
        </span>
        <span className="flex items-center gap-1">
          <MessageCircle className="h-3.5 w-3.5 text-accent" />
          {comments}
        </span>
        <span className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          {age}
        </span>
      </div>
    </motion.div>
  );
}
