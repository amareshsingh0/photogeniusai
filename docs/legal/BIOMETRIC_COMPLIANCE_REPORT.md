# Biometric Data Compliance Report – Identity Vault

## 1. Legal requirements (research summary)

### GDPR (EU/EEA) – Article 9 special category data

- **Face embeddings** (biometric data for unique identification) are **special category data** under Art. 9(1).
- **Lawful basis**: Processing is permitted only under Art. 9(2), e.g. **explicit consent** (Art. 9(2)(a)).
- **Obligations**: Explicit opt-in, purpose limitation, storage limitation, encryption, right of access/erasure/portability, records of processing (Art. 30), DPA with processors.
- **Documentation**: Consent records, privacy notice, DPA, retention and deletion procedures.

### CCPA / CPRA (California)

- **Biometric information** is **sensitive personal information** (CPRA).
- **Disclosure**: Must disclose in privacy policy that biometric data is collected and used; purpose and retention.
- **Rights**: Right to know, delete, correct, limit use of sensitive personal information; no discrimination for exercising rights.
- **Contract**: If “selling” or “sharing” (as defined), contract may be required; identity vault use is typically not sale if used only for user’s own generations.

### Illinois BIPA (Biometric Information Privacy Act)

- **Applicable** if we have Illinois residents’ biometric data.
- **Requirements**: Written release (informed consent), retention schedule and destruction policy, no disclosure without consent (with limited exceptions).
- **Private right of action**: Statutory damages per violation; strict compliance (consent, retention, destruction) is critical.

### EU AI Act (biometric categorization)

- **Relevance**: Use of biometric data for “biometric categorization” or emotion recognition may fall under high-risk or prohibited.
- **Identity vault**: We use face embeddings to **generate personalized images** (one-to-one matching / “identity lock”), not mass categorization. This is closer to “biometric verification” (user-initiated). Document purpose clearly and avoid repurposing for categorization or emotion inference.

---

## 2. Compliance gaps (pre-implementation)

| Gap | Risk | Mitigation (this implementation) |
|-----|------|-----------------------------------|
| No explicit “biometric data” consent before creating identity | GDPR Art. 9, BIPA | Explicit opt-in in identity creation flow; separate consent for training and (optional) showcase. |
| Face embeddings / reference photos not encrypted at rest | GDPR security, BIPA | S3 SSE-KMS for identity-related objects; document and enforce. |
| No audit trail of who accessed which identity | Accountability, breach investigation | Identity access audit log (who, when, identity id). |
| Reference images kept indefinitely after training | Data minimization | Delete reference images after LoRA training; keep LoRA + metadata only; retention policy (e.g. 90 days after account deletion). |
| Soft-delete only; no hard delete of S3/DB | Right to erasure | Hard-delete pipeline: remove S3 objects (refs + LoRA) and DB row; automated on account deletion (24h) and optional on consent withdrawal (7 days). |
| No export (portability) for identity data | GDPR Art. 20 | Export identity package (metadata + consent + LoRA URL or placeholder); access API. |
| Privacy policy / ToS silent on biometrics | Transparency, CCPA/BIPA | Privacy policy biometric section; ToS identity vault; DPA template; biometric data manifest. |
| No single “withdraw biometric consent” action | GDPR, BIPA | One-click “Delete my biometric data” (erasure of all identities + embeddings + LoRAs). |
| Admin access to identities without 2FA | Access control | Document requirement: admin access to identity data requires 2FA; implement in admin auth. |

---

## 3. Compliance checklist

- [ ] **Explicit consent collected** – Biometric/identity consent before processing; separate consent for training and (if applicable) showcase.
- [ ] **Data encrypted at rest** – Face embeddings (in DB/backups), reference images and LoRA files in S3 using SSE-KMS (or equivalent).
- [ ] **Access logs maintained** – Audit log of identity access (who, when, which identity); retained per policy.
- [ ] **Deletion process tested** – Hard delete (S3 + DB) for identity and on account deletion; consent withdrawal triggers deletion within 7 days where implemented.
- [ ] **Privacy policy updated** – Section on biometric data (collection, purpose, retention, rights, legal basis).
- [ ] **Terms of service** – Identity vault usage, acceptable use, data handling.
- [ ] **Legal review completed** – Jurisdiction-specific review (GDPR, CCPA, BIPA, EU AI Act) by legal counsel before go-live in each region.

---

## 4. Retention and minimization

- **Reference photos**: Deleted after LoRA training completes (data minimization); only LoRA + metadata (and optionally face embedding for inference) retained.
- **Face embeddings**: Retained only as needed for identity-lock generation; deleted with identity (erasure).
- **After account deletion**: All identity-related data (DB + S3) deleted within **24 hours** (automated pipeline).
- **After consent withdrawal (biometric)**: Identity data deleted within **7 days** (scheduled job or on next “withdraw” action).

---

## 5. Model inversion and misuse defenses (documented)

- **Rate limiting**: Identity inference (generation with identity) should be rate-limited per user to reduce risk of mass extraction. Implement at API/Lambda (e.g. per-user request cap per hour).
- **Watermarking**: Generated images can be watermarked (visible or invisible) to deter extraction and misuse. Implement in post-processing (e.g. SageMaker or Lambda) and document in Privacy Policy.
- **Block face extraction from outputs**: Terms of service and acceptable use prohibit using third-party face extraction tools on generated images to recreate biometric data; enforce via policy and monitoring where feasible.

These are documented here; implementation of watermarking and extraction blocking can be added in a follow-up.

## 6. References

- GDPR: [Article 9](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679), Recitals 51–53.
- CCPA/CPRA: Cal. Civ. Code § 1798.100 et seq. (sensitive personal information).
- BIPA: 740 ILCS 14/1 et seq. (consent, retention, destruction).
- EU AI Act: Regulation (EU) 2024/1689 (biometric categorization, high-risk uses).
