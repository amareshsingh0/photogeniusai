# Base Model Pilot – Deployment Plan

## 1. A/B test rollout

- **Traffic split:** 10% of generation requests to the new (fine-tuned) model; 90% to base SDXL.
- **Routing:** Use a feature flag or tier (e.g. `pilot_model=true` or a dedicated tier) so that 10% of users (or 10% of requests) hit an endpoint that loads the fine-tuned LoRA.
- **Duration:** Run for at least 1–2 weeks to gather enough preference and quality data.

## 2. Metrics to monitor

| Metric | Target | How to measure |
|--------|--------|----------------|
| Acceptance rate | Improve or neutral | % of generations that user keeps (e.g. save, download) vs base |
| User preference (A/B) | Fine-tuned preferred | Side-by-side preference (A/B test in UI or internal raters) |
| Anatomy accuracy | +15% vs base | Benchmark (evaluate_benchmark.py) + optional production sample |
| Composition quality | +15% vs base | Benchmark composition_score |
| Style consistency | +15% vs base | Benchmark style_score / CLIP alignment |
| Latency | No regression >10% | p50/p99 inference time base vs pilot |
| Error rate | No increase | 5xx and generation failures |

## 3. Rollout criteria

- **Proceed to full rollout:** Benchmark shows ≥ +15% on anatomy/composition/style and A/B shows user preference improvement (or at least neutral), with no meaningful latency or error regression.
- **Expand to 50%:** If 10% rollout shows improved acceptance and no issues for 1 week.
- **Full rollout:** Replace default SDXL with fine-tuned model for the relevant tier(s).
- **Rollback:** If error rate or latency degrades, or user feedback is negative, route traffic back to base model and investigate.

## 4. Infrastructure

- **SageMaker:** Deploy fine-tuned model as a new endpoint (e.g. `photogenius-sdxl-lora-v1`) or new variant; route 10% of traffic to it.
- **Lambda / API:** When `pilot_model=true` or equivalent, call the pilot endpoint instead of the default SDXL endpoint.
- **Feature flag:** Store rollout percentage and pilot endpoint in config (e.g. environment or database); API reads and routes accordingly.

## 5. Rollback and safety

- Keep base SDXL endpoint live; switching back is a config change (point traffic to base).
- Version LoRA checkpoints (e.g. v1.0, v1.1) and document which endpoint uses which version.
- Safety: Apply the same pre/post generation safety checks to pilot model outputs as for base.
