export default function Loading() {
  return (
    <div className="max-w-7xl mx-auto space-y-8 p-4 lg:p-8">
      {/* Header Skeleton */}
      <div className="space-y-2">
        <div className="h-9 w-64 bg-muted/50 rounded animate-pulse" />
        <div className="h-5 w-96 bg-muted/30 rounded animate-pulse" />
      </div>

      {/* Stats Grid Skeleton */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 bg-muted/30 rounded-lg animate-pulse" />
        ))}
      </div>

      {/* Content Grid Skeleton */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-64 bg-muted/30 rounded-lg animate-pulse" />
          ))}
        </div>
        <div className="space-y-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 bg-muted/30 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    </div>
  )
}
