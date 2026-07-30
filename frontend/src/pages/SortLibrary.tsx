import { useState, useEffect } from "react"
import { Shuffle } from "lucide-react"
import { useUser } from "@/hooks/useUser"
import { apiFetch } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Card, CardContent, CardHeader, CardTitle, CardAction } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import TrackRow from "@/components/TrackRow"
import EmptyState from "@/components/EmptyState"

interface ClusterTrack {
  position: number
  track_id: string
  title: string
  artist: string
  album_art_url: string | null
}

interface ClusterPlaylist {
  id: string
  name: string
  tracks: ClusterTrack[]
}

interface ClusterResponse {
  clustering_run_id: string
  n_clusters: number
  tracks_placed: number
  outliers_excluded: number
  playlists: ClusterPlaylist[]
}

const LOADING_MESSAGES = [
  "Analyzing your collection...",
  "Finding patterns in your music...",
  "Building playlists...",
]

export default function SortLibrary() {
  const userId = useUser()

  const [collectionSize, setCollectionSize] = useState<number>(0)
  const [collectionSizeError, setCollectionSizeError] = useState(false)
  const [autoMode, setAutoMode] = useState(true)
  const [nClusters, setNClusters] = useState(4)
  const [completeness, setCompleteness] = useState(1.5)
  const [loading, setLoading] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState(LOADING_MESSAGES[0])
  const [result, setResult] = useState<ClusterResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchCollectionSize = () => {
    if (!userId) return
    apiFetch<{ track_id: string }[]>("/collection/tracks", userId)
      .then((tracks) => {
        setCollectionSize(tracks.length)
        setCollectionSizeError(false)
      })
      .catch(() => setCollectionSizeError(true))
  }

  useEffect(fetchCollectionSize, [userId])

  const maxClusters = Math.max(2, Math.floor(collectionSize / 8))

  useEffect(() => {
    if (!loading) return
    let i = 0
    const interval = setInterval(() => {
      i = (i + 1) % LOADING_MESSAGES.length
      setLoadingMsg(LOADING_MESSAGES[i])
    }, 2500)
    return () => clearInterval(interval)
  }, [loading])

  async function handleSort() {
    if (!userId) return
    setLoading(true)
    setError(null)
    setResult(null)
    setLoadingMsg(LOADING_MESSAGES[0])
    try {
      const data = await apiFetch<ClusterResponse>("/cluster", userId, {
        method: "POST",
        body: JSON.stringify({
          n_clusters: autoMode ? null : nClusters,
          outlier_threshold: completeness,
        }),
      })
      setResult(data)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong"
      setError(msg.includes("400") ? `Not enough tracks to sort (need at least 10).` : msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-10">
      <div className="space-y-6">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Sort library</h2>
          <p className="text-sm text-muted-foreground">
            Proof of concept. Results will vary significantly based on collection size and diversity.
          </p>
        </div>

        <div className="space-y-5">
          <div className="space-y-2">
            <p className="text-sm font-medium text-muted-foreground">
              Describe how you want your library sorted{" "}
              <Badge variant="secondary">Coming soon</Badge>
            </p>
            <textarea
              disabled
              placeholder='e.g. "split by era and energy — one playlist for late night stuff, one for workouts, one for background music..."'
              className="w-full h-16 px-3 py-2 text-sm rounded-md border border-border bg-muted/40 text-muted-foreground resize-none cursor-not-allowed"
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">Number of playlists</p>
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                variant={autoMode ? "default" : "outline"}
                onClick={() => setAutoMode(true)}
              >
                Auto
              </Button>
              <Button
                size="sm"
                variant={!autoMode ? "default" : "outline"}
                onClick={() => setAutoMode(false)}
              >
                Manual
              </Button>
              {!autoMode && (
                <div className="flex items-center gap-3">
                  <Slider
                    min={2}
                    max={maxClusters}
                    step={1}
                    value={[nClusters]}
                    onValueChange={([val]) => setNClusters(val)}
                    className="w-36"
                  />
                  <span className="text-sm tabular-nums w-4">{nClusters}</span>
                  {nClusters === maxClusters && (
                    <span className="text-xs text-muted-foreground">
                      (~{Math.floor(collectionSize / nClusters)} tracks/playlist)
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium">
              Completeness — {completeness <= 1.0 ? "Strict" : completeness >= 1.8 ? "Loose" : "Balanced"}
            </p>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground w-10">Strict</span>
              <Slider
                min={0.8}
                max={2.0}
                step={0.1}
                value={[completeness]}
                onValueChange={([val]) => setCompleteness(val)}
                className="w-48"
              />
              <span className="text-xs text-muted-foreground w-10">Loose</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              loading={loading}
              onClick={handleSort}
              disabled={!userId || collectionSizeError || collectionSize < 10}
            >
              Sort library
            </Button>
            {loading && <p className="text-sm text-muted-foreground">{loadingMsg}</p>}
          </div>

          {collectionSizeError ? (
            <p className="text-sm text-muted-foreground">
              Couldn't check your collection size.{" "}
              <button onClick={fetchCollectionSize} className="underline underline-offset-2 hover:text-foreground">
                Retry
              </button>
            </p>
          ) : (
            collectionSize > 0 &&
            collectionSize < 10 && (
              <p className="text-sm text-muted-foreground">
                Add at least {10 - collectionSize} more tracks to use this feature.
              </p>
            )
          )}
        </div>

        {error && (
          <div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
      </div>

      {loading ? (
        <div className="space-y-6">
          {Array.from({ length: 2 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
              </CardHeader>
              <CardContent className="space-y-1">
                {Array.from({ length: 3 }).map((_, j) => (
                  <div key={j} className="flex items-center gap-3 px-3 py-2">
                    <Skeleton className="size-10 shrink-0 rounded-md" />
                    <div className="min-w-0 flex-1 space-y-2">
                      <Skeleton className="h-4 w-2/5" />
                      <Skeleton className="h-3 w-3/5" />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : result ? (
        <div className="space-y-6">
          <p className="text-sm text-muted-foreground">
            {result.n_clusters} playlists · {result.tracks_placed} tracks placed
            {result.outliers_excluded > 0 && ` · ${result.outliers_excluded} outliers excluded`}
          </p>
          {result.playlists.map((playlist) => (
            <Card key={playlist.id} className="transition-shadow hover:shadow-md">
              <CardHeader>
                <CardTitle>{playlist.name}</CardTitle>
                <CardAction>
                  <Badge variant="secondary">{playlist.tracks.length} tracks</Badge>
                </CardAction>
              </CardHeader>
              <CardContent className="space-y-1">
                {playlist.tracks.map((track) => (
                  <TrackRow
                    key={track.track_id}
                    position={track.position + 1}
                    albumArtUrl={track.album_art_url}
                    title={track.title}
                    artist={track.artist}
                  />
                ))}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={Shuffle}
          title="No playlists yet"
          description="Run the sorter above to split your collection into playlists automatically."
        />
      )}
    </div>
  )
}
