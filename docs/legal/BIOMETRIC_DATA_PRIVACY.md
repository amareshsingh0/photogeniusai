# Privacy Policy – Biometric Data (Identity Vault)

**Last updated:** 2025-02-04

This section describes how we collect, use, and protect **biometric data** in the Identity Vault feature. It supplements our main Privacy Policy and Data Usage Policy.

## 1. What we treat as biometric data

- **Face embeddings**: Numerical vectors (e.g. 512 dimensions) derived from your face in reference photos, used only to generate images that reflect your likeness (“identity lock”).
- **Reference photos**: Photos you upload to create an identity. These are used to train a personal LoRA and to extract a face embedding. We treat them as biometric source data.
- **LoRA weights**: Small model files trained on your photos. They are tied to your identity and are considered personal/biometric-related data.

We do **not** use your biometric data for identification, surveillance, or categorization of you in the general population. We use it only to provide the identity-lock generation feature you request.

## 2. Legal basis (GDPR)

- We process biometric data on the basis of your **explicit consent** (GDPR Article 9(2)(a)).
- You give consent when you create an identity and confirm the biometric consent step (e.g. “I agree to the use of my face data for this identity”).
- You can withdraw consent at any time by deleting the identity or using “Delete my biometric data” in Settings → Privacy. Withdrawal leads to erasure of your biometric data within the timeframes stated below.

## 3. How we use biometric data

- To **train** a personal LoRA and extract a face embedding for the identity you create.
- To **run inference** when you request an image with that identity (face-consistent generation).
- We do **not** sell, share, or use your biometric data for advertising, profiling, or any purpose other than providing the Identity Vault service.

## 4. Retention and minimization

- **Reference photos**: Deleted from our systems after LoRA training completes (data minimization). Only the LoRA file and metadata (and, where needed for inference, the face embedding) are retained.
- **Face embeddings and LoRA**: Retained until you delete the identity or your account, or withdraw consent.
- **After account deletion**: All identity-related data (including any remaining references, embeddings, and LoRA pointers) is deleted within **24 hours**.
- **After consent withdrawal (biometric)**: All your identity data is erased within **7 days** (or immediately when you use “Delete my biometric data”).

## 5. Security

- Biometric data and related assets are **encrypted at rest** (e.g. S3 with SSE-KMS; database fields as per our security standards).
- Access is **user-scoped**: only you can access your identities. We **audit** access (who viewed or exported which identity and when).
- Admin access to identity data requires elevated controls (e.g. 2FA) where applicable.

## 6. Your rights

- **Right to access**: You can request a copy of the identity data we hold (e.g. via the export feature or data subject request form).
- **Right to erasure**: You can delete each identity from the Identity Vault, or use “Delete my biometric data” to erase all identities at once.
- **Right to portability**: You can export your identity metadata and references (e.g. JSON export) from the app or via the data subject request form.

For requests we cannot fulfill in-app, contact **privacy@photogenius.ai**.

## 7. US state laws (CCPA, BIPA)

- We disclose here that we collect and use **biometric information** (face embeddings and source photos) for the Identity Vault, with your consent.
- We do not sell or share biometric information. We retain it only as long as needed and delete it as described above.
- If you are an Illinois resident, we comply with BIPA by obtaining your written release (consent) before collecting biometric data and by following a retention and destruction schedule as described in this section.
