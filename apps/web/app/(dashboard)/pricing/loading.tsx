export default function Loading() {
  return (
    <div className="max-w-7xl mx-auto space-y-12 p-4 lg:p-8">
      {/* Header Skeleton */}
      <div className="text-center space-y-4">
        <div className="h-6 w-32 bg-muted/50 rounded-full mx-auto animate-pulse" />
        <div className="h-12 w-64 bg-muted/50 rounded mx-auto animate-pulse" />
        <div className="h-6 w-96 bg-muted/30 rounded mx-auto animate-pulse" />
      </div>

      {/* Toggle Skeleton */}
      <div className="flex items-center justify-center space-x-4">
        <div className="h-6 w-16 bg-muted/30 rounded animate-pulse" />
        <div className="h-6 w-12 bg-muted/30 rounded animate-pulse" />
        <div className="h-6 w-20 bg-muted/30 rounded animate-pulse" />
      </div>

      {/* Plans Skeleton */}
      <div className="grid md:grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-96 bg-muted/30 rounded-lg animate-pulse" />
        ))}
      </div>
    </div>
  )
}
