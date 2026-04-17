import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PostCard } from "./PostCard";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search, RefreshCw, Loader2 } from "lucide-react";
import { useDiscoverPosts } from "@/hooks/use-api";
import type { RedditPost } from "@/lib/api";
import { CommentSelectionDialog } from "./CommentSelectionDialog";

function formatAge(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export function PostFeed() {
  const [search, setSearch] = useState("");
  const [selectedPost, setSelectedPost] = useState<RedditPost | null>(null);
  const { data, refetch, isFetching, isError, error } = useDiscoverPosts();

  const posts = data?.posts ?? [];
  const filteredPosts = posts.filter(
    (p) =>
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      p.subreddit.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      <Card className="border-border bg-card">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">
              Discovered Posts
              {posts.length > 0 && (
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  ({posts.filter((p) => p.meets_filters && !p.already_used).length} eligible)
                </span>
              )}
            </CardTitle>
            <Button
              size="sm"
              variant="outline"
              onClick={() => refetch()}
              disabled={isFetching}
              className="h-7 px-2 text-xs gap-1"
            >
              {isFetching ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3" />
              )}
              Scan
            </Button>
          </div>
          <div className="relative mt-2">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search posts..."
              className="h-8 pl-8 text-xs bg-secondary border-border"
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
          {isError && (
            <p className="text-xs text-destructive text-center py-4">
              {error?.message || "Failed to load posts"}
            </p>
          )}
          {!isFetching && posts.length === 0 && !isError && (
            <div className="text-center py-8 text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">Click "Scan" to discover posts</p>
              <p className="text-xs mt-1">from your configured subreddits</p>
            </div>
          )}
          {isFetching && posts.length === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              <Loader2 className="h-6 w-6 mx-auto mb-2 animate-spin text-primary" />
              <p className="text-xs">Scanning subreddits...</p>
            </div>
          )}
          {filteredPosts.map((post, i) => (
            <PostCard
              key={post.id}
              title={post.title}
              subreddit={post.subreddit}
              score={post.score}
              comments={post.num_comments}
              age={formatAge(post.age_hours)}
              selftext={post.selftext}
              isSelected={selectedPost?.id === post.id}
              onSelect={() => setSelectedPost(post)}
              index={i}
              meetsFilters={post.meets_filters}
              alreadyUsed={post.already_used}
              filterReason={post.filter_reason}
            />
          ))}
        </CardContent>
      </Card>

      <CommentSelectionDialog
        post={selectedPost}
        open={!!selectedPost}
        onOpenChange={(open) => { if (!open) setSelectedPost(null); }}
        actionLabel="Create Reel"
      />
    </>
  );
}
