import { NavLink } from "react-router-dom";
import { Video, LayoutDashboard, Newspaper, Settings2, Film } from "lucide-react";
import { useHealth } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/posts", label: "Posts", icon: Newspaper },
  { to: "/videos", label: "Videos", icon: Film },
  { to: "/config", label: "Configuration", icon: Settings2 },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { data: health } = useHealth();
  const isOnline = health?.status === "online";

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-6">
            <NavLink to="/" className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 glow-primary">
                <Video className="h-4 w-4 text-primary" />
              </div>
              <h1 className="text-lg font-bold tracking-tight">
                <span className="text-gradient">Reddit</span>
                <span className="text-foreground"> Video Engine</span>
              </h1>
            </NavLink>

            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                    )
                  }
                >
                  <item.icon className="h-3.5 w-3.5" />
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1",
                isOnline
                  ? "border-success/30 bg-success/10"
                  : "border-destructive/30 bg-destructive/10"
              )}
            >
              <div
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  isOnline ? "bg-success animate-pulse" : "bg-destructive"
                )}
              />
              <span
                className={cn(
                  "text-xs font-medium",
                  isOnline ? "text-success" : "text-destructive"
                )}
              >
                {isOnline ? "Online" : "Offline"}
              </span>
            </div>
          </div>
        </div>

        {/* Mobile nav */}
        <div className="md:hidden border-t border-border flex overflow-x-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-1.5 px-4 py-2 text-xs font-medium whitespace-nowrap transition-colors border-b-2",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground"
                )
              }
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </NavLink>
          ))}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 lg:px-6 py-6">{children}</main>
      <div className="fixed bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
    </div>
  );
}
