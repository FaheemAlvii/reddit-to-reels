import { motion } from "framer-motion";
import { Video, Flame, TrendingUp, Clock } from "lucide-react";
import { StatsCard } from "@/components/StatsCard";
import { PipelinePanel } from "@/components/PipelinePanel";
import { PostFeed } from "@/components/PostFeed";
import { RecentVideos } from "@/components/RecentVideos";
import { useStats } from "@/hooks/use-api";

export default function Index() {
  const { data: stats } = useStats();

  return (
    <div className="space-y-6">
      {/* Stats Row */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="grid grid-cols-2 lg:grid-cols-4 gap-3"
      >
        <StatsCard label="Videos Today" value={stats?.videos_today ?? "—"} icon={<Video className="h-4 w-4" />} accentColor="primary" index={0} />
        <StatsCard label="Posts Scanned" value={stats?.posts_scanned ?? "—"} icon={<TrendingUp className="h-4 w-4" />} accentColor="accent" index={1} />
        <StatsCard label="Avg. Render Time" value={stats?.avg_render_time_s ? `${stats.avg_render_time_s}s` : "—"} icon={<Clock className="h-4 w-4" />} accentColor="warning" index={2} />
        <StatsCard label="Success Rate" value={stats?.success_rate != null ? `${stats.success_rate}%` : "—"} icon={<Flame className="h-4 w-4" />} accentColor="success" index={3} />
      </motion.div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-3">
          <PipelinePanel />
        </div>
        <div className="lg:col-span-5">
          <PostFeed />
        </div>
        <div className="lg:col-span-4">
          <RecentVideos />
        </div>
      </div>
    </div>
  );
}
