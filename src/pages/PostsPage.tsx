import { useState } from "react";
import { motion } from "framer-motion";
import { Search, RefreshCw, Loader2, Play, Filter, ArrowUpDown, ExternalLink, CheckCircle2, XCircle, AlertTriangle, Flame, TrendingUp, Clock, Star, Trophy } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { useDiscoverPosts } from "@/hooks/use-api";
import { GenerateFromUrlDialog } from "@/components/GenerateFromUrlDialog";
import { GenerateFromCustomDialog } from "@/components/GenerateFromCustomDialog";
import { CommentSelectionDialog } from "@/components/CommentSelectionDialog";
import type { RedditPost } from "@/lib/api";

const REDDIT_SORTS = [
  { id: "hot", label: "Hot", icon: Flame },
  { id: "best", label: "Best", icon: Star },
  { id: "new", label: "New", icon: Clock },
  { id: "rising", label: "Rising", icon: TrendingUp },
  { id: "top", label: "Top", icon: Trophy },
] as const;

type RedditSort = typeof REDDIT_SORTS[number]["id"];

function formatAge(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export default function PostsPage() {
  const [redditSort, setRedditSort] = useState<RedditSort>("hot");
  const { data, refetch, isFetching, isError, error } = useDiscoverPosts(redditSort);
  const [selectedPost, setSelectedPost] = useState<RedditPost | null>(null);
  const [search, setSearch] = useState("");
  const [filterEligible, setFilterEligible] = useState(false);
  const [sortBy, setSortBy] = useState<"score" | "comments" | "age">("score");

  const posts = data?.posts ?? [];

  const filtered = posts
    .filter((p) => {
      if (filterEligible && (!p.meets_filters || p.already_used)) return false;
      if (search) {
        const q = search.toLowerCase();
        return p.title.toLowerCase().includes(q) || p.subreddit.toLowerCase().includes(q);
      }
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "score") return b.score - a.score;
      if (sortBy === "comments") return b.num_comments - a.num_comments;
      return a.age_hours - b.age_hours;
    });

  const eligible = posts.filter((p) => p.meets_filters && !p.already_used).length;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold">Post Discovery</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Scan configured subreddits for eligible posts
            {posts.length > 0 && (
              <span> — {eligible} eligible of {posts.length} total</span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <GenerateFromCustomDialog />
          <GenerateFromUrlDialog />
          <Button onClick={() => refetch()} disabled={isFetching} className="gap-2">
            {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Scan Subreddits
          </Button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Reddit Sort */}
        <div className="flex items-center gap-1.5">
          {REDDIT_SORTS.map((s) => (
            <Button
              key={s.id}
              size="sm"
              variant={redditSort === s.id ? "default" : "outline"}
              onClick={() => setRedditSort(s.id)}
              className="h-7 px-2 text-xs gap-1"
            >
              <s.icon className="h-3 w-3" />
              {s.label}
            </Button>
          ))}
        </div>

        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by title or subreddit..."
            className="h-9 pl-8 text-xs bg-secondary border-border"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-muted-foreground" />
          <label className="text-xs text-muted-foreground">Eligible only</label>
          <Switch checked={filterEligible} onCheckedChange={setFilterEligible} />
        </div>
        <div className="flex items-center gap-1.5">
          <ArrowUpDown className="h-3.5 w-3.5 text-muted-foreground" />
          {(["score", "comments", "age"] as const).map((s) => (
            <Button
              key={s}
              size="sm"
              variant={sortBy === s ? "default" : "outline"}
              onClick={() => setSortBy(s)}
              className="h-7 px-2 text-xs capitalize"
            >
              {s}
            </Button>
          ))}
        </div>
      </div>

      {isError && (
        <p className="text-sm text-destructive text-center py-4">{(error as Error)?.message}</p>
      )}

      {!isFetching && posts.length === 0 && !isError && (
        <Card className="border-border bg-card">
          <CardContent className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Search className="h-12 w-12 mb-3 opacity-20" />
            <p className="text-sm font-medium">No posts loaded</p>
            <p className="text-xs mt-1">Click "Scan Subreddits" to discover posts</p>
          </CardContent>
        </Card>
      )}

      {isFetching && posts.length === 0 && (
        <Card className="border-border bg-card">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-3" />
            <p className="text-xs text-muted-foreground">Scanning subreddits...</p>
          </CardContent>
        </Card>
      )}

      {/* Posts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {filtered.map((post, i) => {
          const isEligible = post.meets_filters && !post.already_used;
          return (
            <motion.div
              key={post.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.02 }}
            >
              <Card className={`border-border bg-card hover:border-primary/30 transition-all ${!isEligible ? "opacity-50" : ""}`}>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-xs font-semibold leading-snug line-clamp-2">{post.title}</h3>
                      <p className="text-[10px] font-mono text-muted-foreground mt-1">
                        r/{post.subreddit} · {formatAge(post.age_hours)} ago
                      </p>
                    </div>
                    {isEligible ? (
                      <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
                    ) : post.already_used ? (
                      <AlertTriangle className="h-4 w-4 text-warning shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 text-destructive shrink-0" />
                    )}
                  </div>

                  {post.selftext && (
                    <p className="text-[10px] text-muted-foreground line-clamp-3 leading-relaxed">{post.selftext}</p>
                  )}

                  <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                    <span>▲ {post.score.toLocaleString()}</span>
                    <span>💬 {post.num_comments}</span>
                    {post.over_18 && <Badge variant="destructive" className="text-[9px] px-1 py-0">NSFW</Badge>}
                  </div>

                  {!isEligible && (
                    <p className="text-[10px] text-destructive font-mono">
                      {post.already_used ? "Already used" : post.filter_reason}
                    </p>
                  )}

                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!isEligible}
                      onClick={() => setSelectedPost(post)}
                      className="h-7 text-xs gap-1 flex-1"
                    >
                      <Play className="h-3 w-3" />
                      Use This Post
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2"
                      onClick={() => window.open(`https://reddit.com${post.permalink}`, "_blank")}
                    >
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      <CommentSelectionDialog
        post={selectedPost}
        open={!!selectedPost}
        onOpenChange={(open) => { if (!open) setSelectedPost(null); }}
        actionLabel="Use This Post"
      />
    </motion.div>
  );
}
