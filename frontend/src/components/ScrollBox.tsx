import { forwardRef } from "react"
import { cn } from "@/lib/utils"

interface ScrollBoxProps extends React.HTMLAttributes<HTMLDivElement> {
  contentClassName?: string
}

const ScrollBox = forwardRef<HTMLDivElement, ScrollBoxProps>(
  ({ className, contentClassName, children, ...props }, ref) => (
    <div className={cn("relative min-h-0", className)}>
      <div
        ref={ref}
        className={cn("scrollbar-thin h-full overflow-y-auto p-2", contentClassName)}
        {...props}
      >
        {children}
      </div>
      <div className="pointer-events-none absolute inset-x-0 top-0 h-4 bg-gradient-to-b from-card to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-4 bg-gradient-to-t from-card to-transparent" />
    </div>
  )
)
ScrollBox.displayName = "ScrollBox"

export default ScrollBox
