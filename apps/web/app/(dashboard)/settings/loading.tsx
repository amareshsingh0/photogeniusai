export default function Loading() {
  return (
    <div className="max-w-4xl mx-auto space-y-6 p-4 lg:p-8">
      {/* Header Skeleton */}
      <div className="space-y-2">
        <div className="h-9 w-48 bg-muted/50 rounded animate-pulse" />
        <div className="h-5 w-64 bg-muted/30 rounded animate-pulse" />
      </div>

      {/* Tabs Skeleton */}
      <div className="flex gap-4 border-b">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-10 w-24 bg-muted/30 rounded-t animate-pulse" />
        ))}
      </div>

      {/* Content Skeleton */}
      <div className="space-y-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 bg-muted/30 rounded-lg animate-pulse" />
        ))}
      </div>
    </div>
  )
}
