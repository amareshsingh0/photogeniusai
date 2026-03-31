# S3 / R2 Storage Setup

## Cloudflare R2 (Current Setup)

Your `.env` is configured for **Cloudflare R2**:

```env
S3_BUCKET_NAME=photogenius
S3_ACCESS_KEY=2e369a0ad7d280f2f1049099bf03b024
S3_SECRET_KEY=31ff128964b24772132eeb85a6f3c659d83f9c9a4b770ba9314e04d8b3b10741
S3_REGION=auto
S3_ENDPOINT=https://0d79d99bddc932a8de918acd84eb96f0.r2.cloudflarestorage.com
```

### Connection Test

```bash
# Test R2 connection
python scripts/test-s3-connection.py
```

Or via API health endpoint:
```bash
curl http://localhost:8000/health
# Should show: "services": { "s3": "connected" }
```

### Upload Files

**API Endpoint:** `POST /api/v1/storage/upload`

```bash
curl -X POST http://localhost:8000/api/v1/storage/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@image.jpg" \
  -F "folder=uploads"
```

**Response:**
```json
{
  "url": "https://...presigned-url...",
  "key": "uploads/user-id/uuid.jpg",
  "filename": "image.jpg"
}
```

### Public URLs vs Presigned URLs

- **R2**: Returns **presigned URLs** (valid 1 hour) by default for security
- **AWS S3**: Returns public URLs if bucket is public
- **Custom domain**: Configure in R2 dashboard → Custom Domains → use that domain in `S3_ENDPOINT`

### Make R2 Bucket Public (Optional)

If you want public URLs instead of presigned:

1. Cloudflare Dashboard → R2 → `photogenius` bucket
2. **Settings → Public Access** → Enable
3. Update `apps/api/app/services/storage/s3_service.py` to return direct URLs for R2

### Next.js Image Optimization

R2 URLs are already configured in `apps/web/next.config.js`:

```js
images: {
  remotePatterns: [
    { protocol: "https", hostname: "**.r2.cloudflarestorage.com" },
    // ...
  ],
}
```

## Troubleshooting

- **"S3 storage not configured"** → Check `.env` has `S3_BUCKET_NAME` and `S3_ACCESS_KEY`
- **"Connection failed"** → Verify R2 credentials and bucket name
- **"Presigned URL expired"** → URLs expire after 1 hour; generate new ones via `/api/v1/storage/presigned/{key}`
- **Images not loading** → Check Next.js `remotePatterns` includes your R2 domain
