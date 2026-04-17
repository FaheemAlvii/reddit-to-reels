import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface StatsCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: string;
  accentColor?: "primary" | "accent" | "success" | "warning";
  index?: number;
}

export function StatsCard({ label, value, icon, trend, accentColor = "primary", index = 0 }: StatsCardProps) {
  const colorMap = {
    primary: "from-primary/20 to-primary/5 border-primary/20",
    accent: "from-accent/20 to-accent/5 border-accent/20",
    success: "from-success/20 to-success/5 border-success/20",
    warning: "from-warning/20 to-warning/5 border-warning/20",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
      className={cn(
        "rounded-xl border bg-gradient-to-br p-5 transition-all hover:scale-[1.02]",
        colorMap[accentColor]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="mt-1.5 text-2xl font-bold text-foreground">{value}</p>
          {trend && <p className="mt-1 text-xs text-success">{trend}</p>}
        </div>
        <div className="rounded-lg bg-secondary p-2.5 text-muted-foreground">{icon}</div>
      </div>
    </motion.div>
  );
}
