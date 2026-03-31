export default function Loading() {
  return (
    <div className="max-w-7xl mx-auto space-y-6 p-4 lg:p-8">
      {/* Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-9 w-48 bg-muted/50 rounded animate-pulse" />
          <div className="h-5 w-64 bg-muted/30 rounded animate-pulse" />
        </div>
        <div className="h-10 w-40 bg-muted/30 rounded animate-pulse" />
      </div>

      {/* Grid Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="h-64 bg-muted/30 rounded-lg animate-pulse" />
        ))}
      </div>
    </div>
  )
}
