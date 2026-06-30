import { useState, useEffect, useRef, useCallback } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { useUser } from "@/hooks/useUser"
import { apiFetch } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

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

export default function Collection() {
  const userId = useUser()

  const [query, setQuery] = useState("")
  const [searchResults, setSearchResults] = useState<TrackCandidate[]>([])
  const [playlistUrl, setPlaylistUrl] = useState("")

  const [tracks, setTracks] = useState<CollectionTrack[]>([])
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)

  const [searching, setSearching] = useState(false)
  const [adding, setAdding] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)

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
      } catch (err) {
        console.error(err)
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
    estimateSize: () => 56,
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
      setSearchResults((prev) => prev.filter((t) => t.spotify_id !== track.spotify_id))
      // Reset to page 0 so the new track appears at the top (sorted by added_at desc)
      await fetchPage(0, true)
    } catch (err) {
      console.error(err)
    } finally {
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

  return (
    <div className="space-y-10">
      <div className="space-y-6">
        <h2 className="text-lg font-semibold">Add tracks</h2>

        <form onSubmit={handleSearch} className="flex gap-2">
          <Input
            placeholder="Search Spotify..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button type="submit" disabled={searching || !userId}>
            {searching ? "Searching..." : "Search"}
          </Button>
        </form>

        {searchResults.length > 0 && (
          <ul className="space-y-1">
            {searchResults.map((track) => (
              <li
                key={track.spotify_id}
                className="flex items-center gap-3 justify-between px-3 py-2 rounded-md hover:bg-muted"
              >
                <div className="flex items-center gap-3 min-w-0">
                  {track.album_art_url ? (
                    <img
                      src={track.album_art_url}
                      alt={track.album}
                      className="w-10 h-10 rounded object-cover shrink-0"
                    />
                  ) : (
                    <div className="w-10 h-10 rounded bg-muted shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="font-medium truncate">{track.title}</p>
                    <p className="text-sm text-muted-foreground truncate">
                      {track.artist} · {track.album}
                      {track.release_year ? ` · ${track.release_year}` : ""}
                    </p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleAddTrack(track)}
                  disabled={adding === track.spotify_id}
                  className="ml-4 shrink-0"
                >
                  {adding === track.spotify_id ? "Adding..." : "Add"}
                </Button>
              </li>
            ))}
          </ul>
        )}

        <form onSubmit={handleImport} className="flex gap-2">
          <Input
            placeholder="Spotify playlist URL or ID..."
            value={playlistUrl}
            onChange={(e) => setPlaylistUrl(e.target.value)}
          />
          <Button type="submit" disabled={importing || !userId}>
            {importing ? "Importing..." : "Import playlist"}
          </Button>
        </form>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">
          Your tracks{total > 0 ? ` (${total})` : ""}
        </h2>

        {total === 0 && !loadingMore ? (
          <p className="text-muted-foreground text-sm">
            No tracks yet. Search or import a playlist to get started.
          </p>
        ) : (
          <div
            ref={parentRef}
            className="h-[calc(100vh-22rem)] min-h-64 overflow-y-auto rounded-md"
          >
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
                        <span className="text-sm text-muted-foreground">
                          Loading...
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-muted">
                        {track.album_art_url ? (
                          <img
                            src={track.album_art_url}
                            alt={track.album}
                            className="w-10 h-10 rounded object-cover shrink-0"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded bg-muted shrink-0" />
                        )}
                        <div className="min-w-0">
                          <p className="font-medium truncate">{track.title}</p>
                          <p className="text-sm text-muted-foreground truncate">
                            {track.artist} · {track.album}
                            {track.release_year ? ` · ${track.release_year}` : ""}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
