# PhotoGenius AI – Data Usage Policy

**Last updated:** 2025-02-04

## 1. Scope

This policy describes how PhotoGenius AI (“we”, “our”) uses data you provide when you **opt in** to help improve our models and services. It applies to:

- Prompts and generated images you explicitly allow us to use for **training** and/or **showcase**
- Any data we derive or aggregate from that (e.g. quality scores, anonymized analytics)

We do **not** use your data for training or showcase unless you have given clear, granular consent.

## 2. What we collect (only if you opt in)

If you opt in to **“Allow training”**:

- **Prompts** (text you enter for image generation)
- **Generated image URLs** (references to outputs we store)
- **Quality scores** (automated or optional user ratings)
- **Mode/settings** (e.g. realism, creative) for balancing datasets

If you opt in to **“Allow showcase”**:

- We may ask separately before featuring any of your generations in marketing or public galleries.

All such data is **anonymized** for training: we do not associate it with your account or identity in training datasets (we use hashed identifiers only).

## 3. How we use it

- **Model improvement:** To train or fine-tune models (e.g. quality, safety, style) on anonymized, opted-in data only.
- **Research & development:** To evaluate and improve our pipelines and product.
- **Transparency:** We maintain a **Training data manifest** (see below) describing the nature and origin of data used for model training, in line with EU AI Act expectations.

We do **not** sell your data. We do **not** use it for advertising targeting.

## 4. Legal bases (GDPR)

- **Consent** (Art. 6(1)(a)): Your opt-in is the legal basis for using your data for training and (where applicable) showcase.
- You can **withdraw consent** at any time (see “Your rights” below). Withdrawal does not affect the lawfulness of processing before withdrawal.

## 5. Your rights (GDPR / CCPA)

- **Right to withdraw consent:** You can withdraw consent at any time in **Settings → Privacy** or via the consent withdrawal endpoint. After withdrawal, we will not use **new** data for training; existing exports may already contain anonymized records from before withdrawal.
- **Right to erasure / delete:** You can request deletion of your account and associated data (including any consent records and generations). We will remove or anonymize your data from our systems and, where feasible, from past training exports (takedown process).
- **Right to access / data portability:** You can request a copy of the data we hold about you.
- **CCPA:** We do not sell personal information. You may opt out of “sale” or request disclosure; we will honor requests as required.

Contact for requests: [privacy@photogenius.ai] or the in-app support channel.

## 6. Retention

- **Consent records:** Retained for as long as needed to demonstrate consent and handle withdrawals/disputes, then deleted or anonymized.
- **Exported training data:** Stored in secure buckets (e.g. `photogenius-training-data/`) with access controls; retained according to our data retention schedule. Anonymized records may be retained for model improvement; we do not re-identify them.

## 7. Security and safeguards

- Data in transit and at rest is encrypted.
- Access to training datasets is restricted and logged.
- We apply **data quality filters** before export (e.g. quality score thresholds, exclusion of reported/flagged content).

## 8. Changes

We may update this policy. We will notify you of material changes (e.g. by email or in-app notice) and, where required by law, ask for renewed consent.

---

**Training data manifest:** See [TRAINING_DATA_MANIFEST.md](./TRAINING_DATA_MANIFEST.md).  
**Takedown and deletion:** See [TAKEDOWN_PROCESS.md](./TAKEDOWN_PROCESS.md).
