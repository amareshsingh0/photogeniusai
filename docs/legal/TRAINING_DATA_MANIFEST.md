# PhotoGenius AI – Training Data Manifest

**Last updated:** 2025-02-04

This manifest describes the datasets we use (or intend to use) for training or fine-tuning our image generation models, in line with **EU AI Act** transparency and documentation requirements.

## 1. Purpose

- To improve **quality**, **safety**, and **style alignment** of our models.
- To document the **origin**, **scope**, and **processing** of training-related data for accountability and audits.

## 2. Data source

| Field | Description |
|-------|-------------|
| **Source** | PhotoGenius AI product: user generations (prompts + images) created on our platform |
| **Eligibility** | Only generations where the user has **opted in** to “Allow training” and has **not withdrawn** consent |
| **Collection** | Via explicit consent flow (modal / settings); consent version and timestamp recorded |

## 3. Schema of exported data (JSONL)

Each record in our training export contains (anonymized):

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | string | User’s text prompt for the generation |
| `image_url` | string | URL of the selected or primary generated image |
| `quality_score` | number (0–100) | Automated or aggregated quality score |
| `user_rating` | number (1–5) or null | Optional user rating |
| `mode` | string | Generation mode (e.g. REALISM, CREATIVE) |
| `anonymized_user_id` | string | One-way hash of user ID (no re-identification) |

**No** direct user identifiers (email, name, IP, account id) are included in the export.

## 4. Data quality filters (pre-export)

Before inclusion in training exports we apply:

- **Quality:** Only generations with `overallScore` (or equivalent) above a threshold (e.g. 70/100).
- **Safety:** Exclude generations that are **quarantined** or **reported** (abuse reports); exclude users who have **withdrawn** consent.
- **Balance (optional):** We may balance by category/mode to avoid over-representation of a single style.

## 5. Storage and access

- Exports are written to a dedicated bucket (e.g. `photogenius-training-data/`) with access restricted to authorized pipelines and roles.
- Paths are versioned by date (e.g. `YYYY-MM-DD/export.jsonl`).
- Access and usage are logged for accountability.

## 6. Retention and deletion

- Exports are retained according to our data retention policy.
- **Takedown:** If a user withdraws consent or requests erasure, we follow the [Takedown Process](./TAKEDOWN_PROCESS.md); where feasible, we remove or exclude their data from future exports and, if legally required, from existing datasets.

## 7. Versioning

- **Consent version** is stored with each consent record (e.g. `1.0.0`).
- This manifest is versioned by “Last updated” date; significant changes will be documented here.

---

**Related:** [Data Usage Policy](./DATA_USAGE_POLICY.md) | [Takedown Process](./TAKEDOWN_PROCESS.md)
