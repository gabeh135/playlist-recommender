import { useState } from "react"
import { Sparkles } from "lucide-react"
import { useUser } from "@/hooks/useUser"
import { apiFetch } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import TrackRow from "@/components/TrackRow"
import EmptyState from "@/components/EmptyState"
import ScrollBox from "@/components/ScrollBox"

interface PlaylistTrack {
  position: number
  score: number
  spotify_id: string
  title: string
  artist: string
  album: string
  album_art_url: string | null
}

interface GenerateResponse {
  playlist_id: string
  name: string
  tracks: PlaylistTrack[]
}

export default function Generate() {
  const userId = useUser()

  const [prompt, setPrompt] = useState("")
  const [limit, setLimit] = useState(15)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault()
    if (!userId || !prompt.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await apiFetch<GenerateResponse>("/playlists/generate", userId, {
        method: "POST",
        body: JSON.stringify({ prompt, limit }),
      })
      setResult(data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong"
      setError(msg.includes("422") ? "Your collection doesn't have enough tracks yet. Add some first." : msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-10">
      <div className="space-y-6">
        <h2 className="text-lg font-semibold">Generate a playlist</h2>

        <form onSubmit={handleGenerate} className="space-y-5">
          <Input
            placeholder="e.g. late night drive, rainy day studying, upbeat workout..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />

          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">{limit} tracks</p>
            <Slider
              min={5}
              max={30}
              step={1}
              value={[limit]}
              onValueChange={([val]) => setLimit(val)}
              className="w-48"
            />
          </div>

          <Button type="submit" loading={loading} disabled={!userId || !prompt.trim()}>
            Generate
          </Button>
        </form>

        {error && (
          <div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
      </div>

      {loading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
          </CardHeader>
          <CardContent className="space-y-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-2">
                <Skeleton className="size-10 shrink-0 rounded-md" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-4 w-2/5" />
                  <Skeleton className="h-3 w-3/5" />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : result ? (
        <Card className="overflow-hidden p-0">
          <CardHeader className="shrink-0 border-b border-border/50 px-4 py-3">
            <CardTitle>{result.name}</CardTitle>
          </CardHeader>
          <ScrollBox className="max-h-[28rem]" contentClassName="space-y-1 p-2">
            {result.tracks.map((track) => (
              <TrackRow
                key={track.spotify_id}
                position={track.position + 1}
                albumArtUrl={track.album_art_url}
                title={track.title}
                artist={track.artist}
                album={track.album}
              />
            ))}
          </ScrollBox>
        </Card>
      ) : (
        <EmptyState
          icon={Sparkles}
          title="No playlist yet"
          description="Describe a vibe above and we'll pull matching tracks from your collection."
        />
      )}
    </div>
  )
}
