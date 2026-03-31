# API Client Documentation

Complete API client setup with Axios, React Query, WebSocket, and File Upload services.

## Structure

```
lib/api/
├── axios-client.ts          # Axios instance with interceptors
├── react-query-config.ts    # React Query configuration
├── hooks/
│   ├── use-identities.ts    # Identity management hooks
│   ├── use-generation.ts    # Generation hooks
│   └── use-gallery.ts       # Gallery hooks
├── services/
│   ├── file-upload.ts       # File upload with progress
│   └── websocket.ts         # WebSocket integration
└── index.ts                 # Main exports
```

## Features

### ✅ Axios Instance
- Request/response interceptors
- Automatic Clerk JWT authentication
- Error handling with retry logic
- Request ID tracking
- Base URL configuration

### ✅ React Query Setup
- Optimized cache management
- Type-safe query keys
- Invalidation strategies
- Optimistic updates

### ✅ API Hooks

#### Identities
- `useIdentities()` - List all identities
- `useIdentity(id)` - Get single identity
- `useCreateIdentity()` - Create with photo uploads
- `useIdentityStatus(id)` - Poll training status
- `useStartTraining()` - Start training
- `useDeleteIdentity()` - Delete identity
- `useUpdateIdentity()` - Update identity

#### Generation
- `useGenerate()` - Trigger generation
- `useGenerationStatus(id)` - Poll generation progress
- `useGenerationHistory()` - Past generations (paginated)
- `useGeneration(id)` - Get single generation
- `useUpdateGeneration()` - Update generation
- `useDeleteGeneration()` - Delete generation
- `useDownloadImage()` - Download result

#### Gallery
- `useGalleryImages(page, limit)` - Paginated gallery
- `useImageDetail(id)` - Single image metadata
- `useDeleteImage()` - Delete image
- `useBulkActions()` - Bulk download/delete
- `useDownloadImage()` - Download image

### ✅ File Upload Service
- Multipart form data handling
- Progress tracking
- S3 pre-signed URLs
- Image compression
- File validation

### ✅ WebSocket Integration
- Socket.io client setup
- Real-time training progress
- Real-time generation progress
- Connection management
- Automatic reconnection

## Usage Examples

### Basic Query

```tsx
import { useIdentities } from "@/lib/api"

function IdentityList() {
  const { data: identities, isLoading, error } = useIdentities()
  
  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>
  
  return (
    <div>
      {identities?.map(identity => (
        <div key={identity.id}>{identity.name}</div>
      ))}
    </div>
  )
}
```

### Mutation with Optimistic Update

```tsx
import { useCreateIdentity } from "@/lib/api"

function CreateIdentityForm() {
  const createIdentity = useCreateIdentity({
    onSuccess: () => {
      toast.success("Identity created!")
    },
    onError: (error) => {
      toast.error(error.message)
    }
  })
  
  const handleSubmit = async (data) => {
    await createIdentity.mutateAsync({
      name: data.name,
      imageUrls: data.imageUrls
    })
  }
  
  return <form onSubmit={handleSubmit}>...</form>
}
```

### File Upload with Progress

```tsx
import { uploadFile } from "@/lib/api/services/file-upload"
import { useState } from "react"

function FileUploader() {
  const [progress, setProgress] = useState(0)
  
  const handleUpload = async (file: File) => {
    try {
      const result = await uploadFile(file, {
        onProgress: (progress) => {
          setProgress(progress.percentage)
        },
        compress: true,
        maxSize: 10 * 1024 * 1024, // 10MB
      })
      console.log("Uploaded:", result.url)
    } catch (error) {
      console.error("Upload failed:", error)
    }
  }
  
  return (
    <div>
      <input type="file" onChange={(e) => handleUpload(e.target.files[0])} />
      {progress > 0 && <progress value={progress} max={100} />}
    </div>
  )
}
```

### WebSocket Real-time Updates

```tsx
import { useTrainingProgress } from "@/lib/api/services/websocket"

function TrainingStatus({ identityId }: { identityId: string }) {
  const { connected } = useTrainingProgress(identityId, (data) => {
    console.log("Training progress:", data.progress, data.message)
    // Update UI with progress
  })
  
  return (
    <div>
      {connected ? "Connected" : "Disconnected"}
    </div>
  )
}
```

### Polling Status

```tsx
import { useIdentityStatus } from "@/lib/api"

function IdentityTrainingStatus({ identityId }: { identityId: string }) {
  const { data: status } = useIdentityStatus(identityId)
  
  if (!status) return null
  
  return (
    <div>
      Status: {status.status}
      {status.progress && <div>Progress: {status.progress}%</div>}
      {status.message && <div>{status.message}</div>}
    </div>
  )
}
```

## Configuration

### Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Query Client Configuration

The query client is configured in `react-query-config.ts` with:
- Default stale time: 1 minute
- Garbage collection time: 5 minutes
- Retry logic for network errors
- No retry for 4xx errors

## Error Handling

All hooks use consistent error handling:

```tsx
import { getErrorMessage } from "@/lib/api"

try {
  await createIdentity.mutateAsync(data)
} catch (error) {
  const message = getErrorMessage(error)
  toast.error(message)
}
```

## Type Safety

All hooks are fully typed with TypeScript:

```tsx
import type { Identity, Generation, GalleryImage } from "@/lib/api"

const identity: Identity = {
  id: "123",
  name: "John Doe",
  status: "READY",
  // ... fully typed
}
```
