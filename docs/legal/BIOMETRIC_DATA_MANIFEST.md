# Biometric Data Manifest

**Last updated:** 2025-02-04

This manifest describes the **biometric data** we process in the Identity Vault, for transparency and compliance (e.g. GDPR, BIPA, CCPA).

## 1. Categories of biometric data

| Category | Description | Stored where | Retention |
|----------|-------------|--------------|-----------|
| Reference photos | User-uploaded photos of a face used to create an identity | S3 (encrypted); URLs in DB | Deleted after LoRA training (data minimization) |
| Face embedding | 512-dim vector derived from reference photos (InstantID/face encoder) | PostgreSQL (Identity.faceEmbedding) | Until identity or account deletion |
| LoRA weights | Small model file trained on reference photos | S3 (encrypted); path in DB | Until identity or account deletion |

## 2. Purpose of processing

- **Identity creation**: Train a personal LoRA and extract a face embedding so the user can generate face-consistent images.
- **Inference**: Use the face embedding and LoRA when the user requests a generation with that identity.

We do **not** use biometric data for identification, surveillance, categorization, or marketing.

## 3. Legal basis

- **GDPR**: Explicit consent (Art. 9(2)(a)).
- **CCPA/CPRA**: Disclosure and consent; no sale of biometric information.
- **BIPA (Illinois)**: Written release (consent); retention and destruction policy as disclosed.

## 4. Security measures

- **Encryption at rest**: S3 objects (reference images, LoRA) use SSE-KMS (or equivalent); DB encryption as per our standards.
- **Access control**: Identity data is user-scoped; only the account owner can access their identities. Admin access is restricted and audited.
- **Audit**: Identity access (view, export, delete, train) is logged (IdentityAccessAuditLog).

## 5. Data subject rights

- **Access**: User can view identity details and export identity package (metadata, consent, URLs; face embedding excluded from export for security).
- **Erasure**: User can delete an identity (soft then hard-erase) or use “Delete my biometric data” to erase all identities.
- **Portability**: User can download identity export (JSON) from the app or data subject request form.

## 6. Deletion and retention

- **Reference photos**: Deleted after LoRA training; only LoRA + metadata (and face embedding for inference) retained.
- **On identity delete**: Soft-delete then hard-erase (clear embeddings, refs, LoRA path); S3 objects removed asynchronously.
- **On account deletion**: All identity-related data deleted within 24 hours.
- **On consent withdrawal (biometric)**: All identity data erased within 7 days (or immediately when user triggers “Delete my biometric data”).

## 7. Processors and subprocessors

If we use subprocessors (e.g. cloud providers) to store or process biometric data, we do so under a Data Processing Agreement (DPA) and only for the purposes and under the safeguards described in this manifest and our Privacy Policy.
