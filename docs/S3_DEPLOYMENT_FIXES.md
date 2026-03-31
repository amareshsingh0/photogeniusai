# S3/R2 Connection & Deployment Fixes

## ✅ Fixed Issues

### 1. **S3 Service Implementation**
- ✅ Created complete `apps/api/app/services/storage/s3_service.py`
- ✅ Supports AWS S3, Cloudflare R2, and MinIO
- ✅ Sync and async upload/download methods
- ✅ Presigned URL generation for secure access
- ✅ R2 detection and proper URL handling

### 2. **Storage API Endpoints**
- ✅ `POST /api/v1/storage/upload` - Upload files
- ✅ `GET /api/v1/storage/presigned/{key}` - Get presigned URLs
- ✅ `DELETE /api/v1/storage/{key}` - Delete files
- ✅ Added to router: `apps/api/app/api/v1/router.py`

### 3. **Health Check**
- ✅ `/health` endpoint now tests S3/R2 connection
- ✅ Returns: `{ "status": "ok", "services": { "s3": "connected" } }`

### 4. **Next.js Image Config**
- ✅ Updated `apps/web/next.config.js` to allow R2 images
- ✅ Added `remotePatterns` for `**.r2.cloudflarestorage.com`

### 5. **Connection Test**
- ✅ `scripts/test-s3-connection.py` - Test R2 connection
- ✅ Verified: **R2 connection successful** ✅

## 📋 Your Current R2 Config

```env
S3_BUCKET_NAME=photogenius
S3_ACCESS_KEY=2e369a0ad7d280f2f1049099bf03b024
S3_SECRET_KEY=31ff128964b24772132eeb85a6f3c659d83f9c9a4b770ba9314e04d8b3b10741
S3_REGION=auto
S3_ENDPOINT=https://0d79d99bddc932a8de918acd84eb96f0.r2.cloudflarestorage.com
```

**Status:** ✅ Connected and working

## 🚀 How to Use

### Test Connection
```bash
python scripts/test-s3-connection.py
```

### Upload File (via API)
```bash
curl -X POST http://localhost:8000/api/v1/storage/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@photo.jpg" \
  -F "folder=uploads"
```

### Check Health
```bash
curl http://localhost:8000/health
```

## 📝 Notes

1. **R2 URLs**: Returns **presigned URLs** (valid 1 hour) for security
2. **Public Access**: If you want public URLs, enable "Public Access" in R2 dashboard
3. **Custom Domain**: Configure custom domain in R2 → use that in `S3_ENDPOINT`
4. **Redis Port**: Your `.env` has `REDIS_URL=redis://localhost:7379/0` - if using standard Redis, change to `6379`

## 🔧 Next Steps

1. **Test upload** via API endpoint
2. **Configure R2 bucket** permissions (public vs private)
3. **Set up custom domain** (optional) for public image URLs
4. **Deploy** - R2 connection will work in production with same `.env` values
