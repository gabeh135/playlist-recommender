import { useState, useEffect } from "react"
import { useUser } from "@/hooks/useUser"
import { apiFetch } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"

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
  const [autoMode, setAutoMode] = useState(true)
  const [nClusters, setNClusters] = useState(4)
  const [completeness, setCompleteness] = useState(1.5)
  const [loading, setLoading] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState(LOADING_MESSAGES[0])
  const [result, setResult] = useState<ClusterResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!userId) return
    apiFetch<{ track_id: string }[]>("/collection/tracks", userId)
      .then((tracks) => setCollectionSize(tracks.length))
      .catch(() => {})
  }, [userId])

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
              <span className="text-xs">(coming soon)</span>
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
              <button
                onClick={() => setAutoMode(true)}
                className={`text-sm px-3 py-1 rounded-md border transition-colors ${
                  autoMode
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                Auto
              </button>
              <button
                onClick={() => setAutoMode(false)}
                className={`text-sm px-3 py-1 rounded-md border transition-colors ${
                  !autoMode
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                Manual
              </button>
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

          <Button onClick={handleSort} disabled={loading || !userId || collectionSize < 10}>
            {loading ? loadingMsg : "Sort library"}
          </Button>

          {collectionSize > 0 && collectionSize < 10 && (
            <p className="text-sm text-muted-foreground">
              Add at least {10 - collectionSize} more tracks to use this feature.
            </p>
          )}
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>

      {result && (
        <div className="space-y-6">
          <p className="text-sm text-muted-foreground">
            {result.n_clusters} playlists · {result.tracks_placed} tracks placed
            {result.outliers_excluded > 0 && ` · ${result.outliers_excluded} outliers excluded`}
          </p>
          {result.playlists.map((playlist) => (
            <div key={playlist.id} className="space-y-2">
              <h3 className="font-semibold">{playlist.name}</h3>
              <ul className="space-y-1">
                {playlist.tracks.map((track) => (
                  <li
                    key={track.track_id}
                    className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-muted"
                  >
                    <span className="text-sm text-muted-foreground w-5 shrink-0 text-right">
                      {track.position + 1}
                    </span>
                    {track.album_art_url ? (
                      <img
                        src={track.album_art_url}
                        alt=""
                        className="w-10 h-10 rounded object-cover shrink-0"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded bg-muted shrink-0" />
                    )}
                    <div className="min-w-0">
                      <p className="font-medium truncate">{track.title}</p>
                      <p className="text-sm text-muted-foreground truncate">{track.artist}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
