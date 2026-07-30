import { Music } from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

interface TrackRowProps {
  albumArtUrl: string | null
  title: string
  artist: string
  album?: string
  year?: number | null
  position?: number
  sourceLabel?: string
  trailing?: React.ReactNode
}

export default function TrackRow({
  albumArtUrl,
  title,
  artist,
  album,
  year,
  position,
  sourceLabel,
  trailing,
}: TrackRowProps) {
  const meta = [artist, album, year ? String(year) : null].filter(Boolean).join(" · ")

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 transition-all",
        trailing && "hover:scale-[1.01] hover:bg-muted"
      )}
    >
      {position !== undefined && (
        <span className="w-5 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
          {position}
        </span>
      )}

      <Avatar size="lg" className="rounded-md after:rounded-md">
        <AvatarImage src={albumArtUrl ?? undefined} alt="" className="rounded-md" />
        <AvatarFallback className="rounded-md">
          <Music className="size-4" />
        </AvatarFallback>
      </Avatar>

      <Tooltip>
        <TooltipTrigger asChild>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{title}</p>
            <div className="flex items-center gap-2">
              <p className="truncate text-sm text-muted-foreground">{meta}</p>
              {sourceLabel && (
                <Badge variant="secondary" className="shrink-0">
                  {sourceLabel}
                </Badge>
              )}
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top">
          {title} · {artist}
        </TooltipContent>
      </Tooltip>

      {trailing && <div className="ml-2 shrink-0">{trailing}</div>}
    </div>
  )
}
