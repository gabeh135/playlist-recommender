import { Spinner } from "@/components/ui/spinner"

export default function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
      <div className="flex flex-col items-center gap-3">
        <Spinner className="size-8 text-primary" />
        <p className="text-sm text-muted-foreground">Connecting...</p>
      </div>
    </div>
  )
}
