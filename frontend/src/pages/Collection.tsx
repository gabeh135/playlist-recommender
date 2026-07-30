import { useState, useEffect, useRef, useCallback } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { Check, Library, SearchX, ServerCrash } from "lucide-react"
import { useUser } from "@/hooks/useUser"
import { apiFetch } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import TrackRow from "@/components/TrackRow"
import EmptyState from "@/components/EmptyState"

interface TrackCandidate {
  spotify_id: string
  title: string
  artist: string
  album: string
  release_year: number | null
  album_art_url: string | null
}

interface CollectionTrack {
  track_id: string
  spotify_id: string
  title: string
  artist: string
  album: string
  release_year: number | null
  album_art_url: string | null
  added_at: string
  source: string
}

interface CollectionPage {
  items: CollectionTrack[]
  total: number
}

const PAGE_SIZE = 50

const SOURCE_LABELS: Record<string, string> = {
  SEARCH: "Search",
  PLAYLIST_IMPORT: "Playlist import",
  LIKED_SONGS: "Liked Songs",
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 px-3 py-2">
      <Skeleton className="size-10 shrink-0 rounded-md" />
      <div className="min-w-0 flex-1 space-y-2">
        <Skeleton className="h-4 w-2/5" />
        <Skeleton className="h-3 w-3/5" />
      </div>
    </div>
  )
}

export default function Collection() {
  const userId = useUser()

  const [query, setQuery] = useState("")
  const [searchResults, setSearchResults] = useState<TrackCandidate[] | null>(null)
  const [playlistUrl, setPlaylistUrl] = useState("")

  const [tracks, setTracks] = useState<CollectionTrack[]>([])
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const [searching, setSearching] = useState(false)
  const [adding, setAdding] = useState<string | null>(null)
  const [justAdded, setJustAdded] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [loadingDemo, setLoadingDemo] = useState(false)

  const hasMore = tracks.length < total

  const fetchPage = useCallback(
    async (offset: number, replace = false) => {
      if (!userId) return
      setLoadingMore(true)
      try {
        const data = await apiFetch<CollectionPage>(
          `/collection/tracks?limit=${PAGE_SIZE}&offset=${offset}`,
          userId
        )
        setTracks((prev) => (replace ? data.items : [...prev, ...data.items]))
        setTotal(data.total)
        if (offset === 0) setLoadError(false)
      } catch (err) {
        console.error(err)
        if (offset === 0) setLoadError(true)
      } finally {
        setLoadingMore(false)
      }
    },
    [userId]
  )

  // Initial load
  useEffect(() => {
    fetchPage(0, true)
  }, [fetchPage])

  // Virtualized list
  const parentRef = useRef<HTMLDivElement>(null)
  const rowVirtualizer = useVirtualizer({
    count: hasMore ? tracks.length + 1 : tracks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 60,
    overscan: 5,
  })

  const virtualItems = rowVirtualizer.getVirtualItems()
  const lastVirtualItem = virtualItems[virtualItems.length - 1]

  useEffect(() => {
    if (!lastVirtualItem) return
    if (lastVirtualItem.index >= tracks.length && !loadingMore) {
      fetchPage(tracks.length)
    }
  }, [lastVirtualItem?.index, loadingMore, tracks.length, fetchPage])

  async function handleLoadDemo() {
    if (!userId) return
    setLoadingDemo(true)
    try {
      await apiFetch("/collection/demo", userId, { method: "POST" })
      await fetchPage(0, true)
    } catch (err) {
      console.error(err)
    } finally {
      setLoadingDemo(false)
    }
  }

  async function handleSearch(e: React.SyntheticEvent) {
    e.preventDefault()
    if (!userId || !query.trim()) return
    setSearching(true)
    try {
      const results = await apiFetch<TrackCandidate[]>(
        `/tracks/search?q=${encodeURIComponent(query)}`,
        userId
      )
      setSearchResults(results)
    } catch (err) {
      console.error(err)
    } finally {
      setSearching(false)
    }
  }

  async function handleAddTrack(track: TrackCandidate) {
    if (!userId) return
    setAdding(track.spotify_id)
    try {
      await apiFetch("/collection/tracks", userId, {
        method: "POST",
        body: JSON.stringify({ spotify_id: track.spotify_id }),
      })
      setAdding(null)
      setJustAdded(track.spotify_id)
      // Reset to page 0 so the new track appears at the top (sorted by added_at desc)
      await fetchPage(0, true)
      setTimeout(() => {
        setJustAdded((current) => (current === track.spotify_id ? null : current))
        setSearchResults((prev) => prev?.filter((t) => t.spotify_id !== track.spotify_id) ?? prev)
      }, 1200)
    } catch (err) {
      console.error(err)
      setAdding(null)
    }
  }

  async function handleImport(e: React.SyntheticEvent) {
    e.preventDefault()
    if (!userId || !playlistUrl.trim()) return
    setImporting(true)
    try {
      await apiFetch("/collection/import/playlist", userId, {
        method: "POST",
        body: JSON.stringify({ playlist_url: playlistUrl }),
      })
      setPlaylistUrl("")
      await fetchPage(0, true)
    } catch (err) {
      console.error(err)
    } finally {
      setImporting(false)
    }
  }

  const showSearchPanel = searching || searchResults !== null

  return (
    <div className="flex h-full min-h-0 flex-col gap-6">
      <div className="shrink-0 space-y-6">
        <h2 className="text-lg font-semibold">Add tracks</h2>

        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Search Spotify..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button type="submit" loading={searching} disabled={!userId}>
            Search
          </Button>
        </form>

        {showSearchPanel && (
          <Card className="max-h-80 overflow-y-auto p-2">
            {searching ? (
              <div className="space-y-1">
                {Array.from({ length: 3 }).map((_, i) => (
                  <SkeletonRow key={i} />
                ))}
              </div>
            ) : searchResults && searchResults.length === 0 ? (
              <EmptyState
                icon={SearchX}
                title={`No matches for "${query}"`}
                description="Try a different search term."
                className="border-0 ring-0"
              />
            ) : (
              <div className="space-y-1">
                {searchResults?.map((track) => (
                  <TrackRow
                    key={track.spotify_id}
                    albumArtUrl={track.album_art_url}
                    title={track.title}
                    artist={track.artist}
                    album={track.album}
                    year={track.release_year}
                    trailing={
                      justAdded === track.spotify_id ? (
                        <Button size="sm" variant="outline" disabled className="text-primary">
                          <Check className="size-3.5" />
                          Added
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          loading={adding === track.spotify_id}
                          onClick={() => handleAddTrack(track)}
                        >
                          Add
                        </Button>
                      )
                    }
                  />
                ))}
              </div>
            )}
          </Card>
        )}

        <form onSubmit={handleImport} className="flex gap-2">
          <Input
            placeholder="Spotify playlist URL or ID..."
            value={playlistUrl}
            onChange={(e) => setPlaylistUrl(e.target.value)}
          />
          <Button type="submit" loading={importing} disabled={!userId}>
            Import playlist
          </Button>
        </form>
      </div>

      <Separator />

      <div className="flex min-h-0 flex-1 flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Your tracks{total > 0 ? ` (${total})` : ""}
          </h2>
          {total > 0 && (
            <Button
              size="sm"
              variant="outline"
              loading={loadingDemo}
              onClick={handleLoadDemo}
              disabled={!userId}
            >
              Load sample collection
            </Button>
          )}
        </div>

        {total === 0 && loadingMore ? (
          <Card className="p-2">
            <div className="space-y-1">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonRow key={i} />
              ))}
            </div>
          </Card>
        ) : loadError ? (
          <EmptyState
            icon={ServerCrash}
            title="Couldn't load your collection"
            description="Something went wrong reaching the server."
            action={
              <Button size="sm" variant="outline" onClick={() => fetchPage(0, true)}>
                Retry
              </Button>
            }
          />
        ) : total === 0 ? (
          <EmptyState
            icon={Library}
            title="No tracks yet"
            description="Search above to add tracks, or load a sample collection to explore the app."
            action={
              <Button variant="outline" loading={loadingDemo} onClick={handleLoadDemo}>
                Load sample collection
              </Button>
            }
          />
        ) : (
          <Card className="min-h-0 flex-1 overflow-hidden p-0">
            <div className="relative h-full">
              <div ref={parentRef} className="h-full overflow-y-auto p-2">
                <div
                  style={{ height: rowVirtualizer.getTotalSize() }}
                  className="relative"
                >
                  {virtualItems.map((virtualRow) => {
                    const isLoader = virtualRow.index >= tracks.length
                    const track = tracks[virtualRow.index]

                    return (
                      <div
                        key={virtualRow.key}
                        data-index={virtualRow.index}
                        ref={rowVirtualizer.measureElement}
                        style={{ transform: `translateY(${virtualRow.start}px)` }}
                        className="absolute top-0 left-0 right-0"
                      >
                        {isLoader ? (
                          <div className="flex items-center justify-center py-4">
                            <Spinner className="size-4 text-muted-foreground" />
                          </div>
                        ) : (
                          <TrackRow
                            albumArtUrl={track.album_art_url}
                            title={track.title}
                            artist={track.artist}
                            album={track.album}
                            year={track.release_year}
                            sourceLabel={SOURCE_LABELS[track.source]}
                          />
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
              <div className="pointer-events-none absolute inset-x-0 top-0 h-4 bg-gradient-to-b from-card to-transparent" />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-4 bg-gradient-to-t from-card to-transparent" />
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
