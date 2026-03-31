# Biometric Data – Encryption at Rest Implementation

## 1. Objective

All **biometric-related assets** (reference photos, LoRA files, and any exports containing identity data) must be **encrypted at rest**. This supports GDPR, BIPA, and general security expectations.

## 2. S3 (reference images and LoRA files)

### Option A: Bucket default encryption (SSE-S3 or SSE-KMS)

- Enable **default encryption** on the bucket used for identity/reference and LoRA objects (e.g. `photogenius-images-*`, `photogenius-loras-*`, or a dedicated `photogenius-biometric-*` bucket).
- **AWS**: Bucket → Properties → Default encryption → SSE-S3 or **SSE-KMS** (preferred for audit and key control).
- New objects inherit the bucket default. Existing objects: re-upload or use S3 Batch to copy with encryption.

### Option B: Per-request ServerSideEncryption (SSE-KMS)

When uploading from application code (e.g. Lambda, API):

```python
# Python (boto3)
s3_client.put_object(
    Bucket=bucket,
    Key=key,
    Body=body,
    ContentType=content_type,
    ServerSideEncryption="aws:kms",
    SSEKMSKeyId="alias/photogenius-biometric",  # optional; else default key
)
```

```typescript
// Node (AWS SDK v3)
await s3Client.send(new PutObjectCommand({
  Bucket: bucket,
  Key: key,
  Body: body,
  ContentType: contentType,
  ServerSideEncryption: "aws:kms",
  // SSEKMSKeyId: "alias/photogenius-biometric",
}));
```

- Ensure the IAM role used for uploads has `kms:GenerateDataKey` and `kms:Decrypt` on the KMS key.

### Recommendation

- Use **SSE-KMS** for identity and LoRA buckets so access is logged in CloudTrail (key usage) and keys can be rotated or revoked.
- Create a dedicated KMS key (e.g. `alias/photogenius-biometric`) and restrict its use to the identity/LoRA buckets and the roles that need to read/write them.

## 3. Database (face embeddings and metadata)

- **PostgreSQL**: Identity table stores `faceEmbedding` (JSONB) and metadata. Ensure the database is **encrypted at rest** (e.g. RDS encryption, or equivalent for your provider).
- Application-level encryption of the `faceEmbedding` column (e.g. encrypt before write, decrypt after read) is optional if the DB is already encrypted and access is tightly controlled; it can be added for defense in depth.

## 4. Access control

- **S3**: Bucket policy and IAM limit read/write to the application and backend roles that need it. No public read for identity/LoRA objects.
- **DB**: Identity rows are queried only by `userId` (user-scoped). Admin access should require 2FA and be audited.
- **Audit**: Identity access (view, export, delete, train) is logged in `IdentityAccessAuditLog`; S3/KMS access can be reviewed via CloudTrail.

## 5. Checklist

- [ ] S3 bucket(s) for reference images and LoRA use default encryption (SSE-KMS preferred).
- [ ] Upload code uses `ServerSideEncryption: "aws:kms"` when writing identity-related objects (if not relying solely on bucket default).
- [ ] KMS key exists and IAM roles are granted minimal required permissions.
- [ ] Database (Identity, audit logs) is encrypted at rest.
- [ ] Access to identity data is user-scoped and admin access is protected (e.g. 2FA) and audited.
