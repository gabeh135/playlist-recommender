import { NavLink, Outlet } from "react-router-dom"
import { Library, Sparkles, Shuffle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

const navLinks = [
  { to: "/", label: "Collection", icon: Library },
  { to: "/generate", label: "Generate", icon: Sparkles },
  { to: "/sort", label: "Sort Library", icon: Shuffle },
]

export default function Layout() {
  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <nav className="flex shrink-0 items-center gap-8 border-b border-border px-6 py-3">
        <div className="flex items-center gap-2">
          <img src="/favicon.svg" alt="" className="size-6" />
          <span className="font-semibold tracking-tight text-foreground">
            Playlist Recommender
          </span>
        </div>

        <div className="flex gap-1">
          {navLinks.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" disabled>
            Connect Spotify
          </Button>
          <Badge variant="secondary">Coming soon</Badge>
        </div>
      </nav>

      <main className="mx-auto min-h-0 w-full max-w-4xl flex-1 overflow-y-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
