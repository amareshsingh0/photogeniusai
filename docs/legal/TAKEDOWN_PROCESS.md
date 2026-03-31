# PhotoGenius AI – Takedown & Data Deletion Process

**Last updated:** 2025-02-04

This document describes how we handle **withdrawal of consent**, **erasure requests**, and **takedown** of user data from our systems and from training datasets (GDPR Art. 17, CCPA, and similar rights).

## 1. Withdrawal of consent

- **How:** User can withdraw consent at any time via:
  - **In-app:** Settings → Privacy → Withdraw consent (or equivalent)
  - **API:** `POST /api/consent/withdraw` (authenticated)
- **Effect:**
  - We mark the user’s consent record(s) as withdrawn (e.g. `withdrawnAt` timestamp).
  - **New** generations are no longer flagged as eligible for training export (`allowTrainingDataExport = false`).
  - **Future exports** will exclude this user’s data (we filter out users who have any consent record with `withdrawnAt` set).
- **Already-exported data:** Anonymized records from **before** withdrawal may already exist in past export files. We do not re-identify them; if a user requests deletion of their data “everywhere,” we proceed as in Section 2.

## 2. Account and data deletion (right to erasure)

- **How:** User submits a request via:
  - In-app “Delete my account” or “Request data deletion”
  - Email to [privacy@photogenius.ai] or support
- **Verification:** We verify the requester’s identity (e.g. via account login or secure link).
- **Actions we take:**
  1. **Account and profile:** Delete or irreversibly anonymize the user account and profile data.
  2. **Generations:** Delete or irreversibly anonymize generation records (prompts, URLs, metadata) from our primary databases.
  3. **Consent records:** Retain only as needed for legal/audit purposes (e.g. proof of consent/withdrawal), then delete or anonymize.
  4. **Stored assets:** Remove or overwrite generated images associated with the user from our storage (e.g. S3) within a defined SLA (e.g. 30 days).
  5. **Training exports:**  
     - **Future exports:** User is already excluded (withdrawn or no consent).  
     - **Past exports:** Exports are anonymized (hashed user id). We do not store a mapping from hash back to user. If legally required to “remove” the user from past exports, we will:
       - Document the request and the fact that data was anonymized;
       - Where technically feasible (e.g. we still have a list of hashed IDs that belonged to the user), we can produce a “blocklist” of hashes to exclude from future use of that dataset;
       - We do not re-identify or reverse hashes; we only exclude by hash if we have recorded it at export time.
- **Timeline:** We aim to complete deletion from production systems within **30 days** and confirm to the user.

## 3. Takedown of specific content (e.g. showcase)

- If the user’s content was used in **showcase** (e.g. gallery, marketing) and they request removal:
  - We remove the content from public-facing surfaces within a defined SLA (e.g. 7 days).
  - We do not use that content for new training exports after the request.

## 4. Abuse and safety

- Content that violates our policies may be **removed** and **excluded** from training regardless of consent. We do not use quarantined or reported content in training exports.

## 5. Contact and log

- All deletion/withdrawal requests are logged (request date, channel, outcome) for compliance and audit.
- Contact for privacy and erasure: [privacy@photogenius.ai] or in-app support.

---

**Related:** [Data Usage Policy](./DATA_USAGE_POLICY.md) | [Training Data Manifest](./TRAINING_DATA_MANIFEST.md)
