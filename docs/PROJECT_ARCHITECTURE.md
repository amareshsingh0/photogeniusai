# PhotoGenius AI – Complete Project Architecture

**Comprehensive documentation of all files, subfiles, and their connections.**

**Last updated:** 2026-02-04

**File Counts:**
- AI Pipeline Services: 83+ Python files
- AI Pipeline Tests: 47 test files
- Apps/API: 79+ Python files
- Apps/Web: 220+ TypeScript/TSX files
- AWS Lambda: 8 handlers
- Documentation: 46 files
- **Total: 400+ source files**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Data Flow Architecture](#3-data-flow-architecture)
4. [Component Connections](#4-component-connections)
5. [AI Pipeline Details](#5-ai-pipeline-details)
6. [Backend API Details](#6-backend-api-details)
7. [Frontend Details](#7-frontend-details)
8. [AWS Infrastructure](#8-aws-infrastructure)
9. [Database Schema](#9-database-schema)
10. [Service Dependencies](#10-service-dependencies)

---

## 1. Project Overview

PhotoGenius AI is a full-stack AI image generation platform built on:

- **Frontend:** Next.js 14 (App Router), React, Tailwind CSS, shadcn/ui
- **Backend:** FastAPI (Python), PostgreSQL, Redis
- **AI Engine:** SDXL, InstantID, LoRA, Custom Models
- **Infrastructure:** AWS (SageMaker, Lambda, S3, API Gateway)
- **Database:** PostgreSQL with Prisma + SQLAlchemy/Alembic

### Tech Stack Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                │
│  Next.js 14 · React · Tailwind · shadcn/ui · Zustand · Socket.IO│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                 │
│     FastAPI · SQLAlchemy · Alembic · Redis · S3 · Clerk Auth    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AWS INFRASTRUCTURE                         │
│  API Gateway · Lambda · SageMaker · S3 · DynamoDB · CloudWatch  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AI PIPELINE                               │
│  SDXL · InstantID · LoRA · Quality Scoring · Safety · Two-Pass  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

```
PhotoGenius AI/
│
├── apps/                          # Application code
│   ├── api/                       # FastAPI backend (main API)
│   │   ├── alembic/               # Database migrations
│   │   │   └── versions/          # Migration files
│   │   ├── app/                   # Application code
│   │   │   ├── api/v1/            # API endpoints
│   │   │   │   └── endpoints/     # Route handlers
│   │   │   ├── core/              # Config, database, auth
│   │   │   ├── models/            # SQLAlchemy models
│   │   │   ├── schemas/           # Pydantic schemas
│   │   │   ├── services/          # Business logic
│   │   │   │   ├── ai/            # AI-related services
│   │   │   │   ├── safety/        # Safety services
│   │   │   │   └── storage/       # Storage services
│   │   │   ├── workers/           # Background workers
│   │   │   └── tests/             # Unit tests
│   │   └── tests/                 # Integration tests
│   │
│   ├── web/                       # Next.js frontend
│   │   ├── app/                   # App Router pages
│   │   │   ├── (dashboard)/       # Dashboard routes
│   │   │   │   ├── generate/      # Generation page
│   │   │   │   ├── gallery/       # Gallery page
│   │   │   │   ├── identity-vault/# Identity management
│   │   │   │   └── settings/      # Settings page
│   │   │   └── api/               # API routes
│   │   ├── components/            # React components
│   │   │   ├── generate/          # Generation components
│   │   │   ├── identity/          # Identity components
│   │   │   └── landing/           # Landing page components
│   │   └── lib/                   # Utilities and stores
│   │       ├── stores/            # Zustand stores
│   │       └── types/             # TypeScript types
│   │
│   └── ai-service/                # Optional AI service
│       ├── app/                   # FastAPI app
│       │   ├── routers/           # API routers
│       │   ├── services/          # Services
│       │   │   ├── ai/            # AI services
│       │   │   └── safety/        # Safety services
│       │   └── models/            # Models
│       └── tests/                 # Tests
│
├── ai-pipeline/                   # Core AI pipeline
│   ├── api/                       # Standalone API
│   │   └── v1/                    # V1 endpoints + storage.py
│   ├── services/                  # AI services (83+ files)
│   │   └── finish/                # Finish/post-processing (flux, replicate)
│   ├── models/                    # Model download scripts
│   ├── caching/                   # Smart caching
│   ├── monitoring/                # Logging, metrics, storage
│   ├── optimization/              # Model optimization
│   ├── training/                  # Training scripts
│   ├── tests/                     # Test suite (47 files)
│   ├── scripts/                   # Utility scripts (10 files)
│   ├── demo_refinement.py         # Interactive refinement demo
│   ├── demo_self_improvement.py   # Self-improvement demo
│   ├── requirements-reward.txt    # Reward model deps
│   └── requirements-tri-model.txt # Tri-model validator deps
│
├── aws/                           # AWS infrastructure
│   ├── lambda/                    # Lambda functions (8 handlers)
│   │   ├── generation/            # Generation + midjourney concepts
│   │   ├── orchestrator/          # Orchestrator v1 (820 lines)
│   │   ├── orchestrator_v2/       # Orchestrator v2 (464 lines)
│   │   ├── post_processor/        # RealESRGAN + CodeFormer
│   │   ├── prompt_enhancer/       # 10,000+ patterns
│   │   ├── refinement/            # Stub for img2img
│   │   ├── safety/                # Context-sensitive safety
│   │   └── training/              # LoRA training orchestration
│   ├── sagemaker/                 # SageMaker endpoints
│   │   ├── model/code/            # 6 inference scripts
│   │   └── training/              # LoRA training scripts
│   ├── monitoring/                # CloudWatch alarms
│   ├── layers/                    # Lambda layers
│   └── scripts/                   # 17 deployment scripts
│
├── packages/                      # Shared packages
│   ├── database/                  # Prisma schema (11 models, 8 enums)
│   │   └── prisma/                # Schema and migrations
│   ├── types/                     # Shared TypeScript types
│   │   └── src/                   # generation, identity, user, index
│   └── ui/                        # Shared UI (Button, Card)
│
├── deploy/                        # NEW: Deployment configs
│   ├── endpoint_config.yaml       # Multi-tier SageMaker config
│   ├── sagemaker_deployment.py    # Production deployment
│   ├── sagemaker_jumpstart.py     # JumpStart alternative
│   ├── lambda/                    # Lambda orchestrator
│   │   ├── orchestrator.py        # Serverless handler
│   │   ├── template.yaml          # SAM template
│   │   └── deploy.sh              # One-command deploy
│   └── sagemaker/                 # SageMaker deployment
│       ├── package_model.py       # Bundle model.tar.gz
│       └── deploy_to_sagemaker.py # All-in-one deploy
│
├── frontend/                      # NEW: Alternative frontend
│   └── photogenius-ui-v2.jsx      # World-class React component
│
├── infra/                         # Infrastructure
│   ├── docker/                    # Docker configurations
│   ├── k8s/                       # Kubernetes manifests
│   └── terraform/                 # Terraform configs
│
├── config/                        # Configuration files
├── scripts/                       # Root-level scripts
└── docs/                          # Documentation (46 files)
```

---

## 3. Data Flow Architecture

### 3.1 Generation Request Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │────▶│  Next.js │────▶│  FastAPI │────▶│   AWS   │
│  Input   │     │  Web     │     │  Backend │     │  Lambda  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                │                 │
                      ▼                ▼                 ▼
               ┌──────────┐     ┌──────────┐     ┌──────────┐
               │ Zustand  │     │  Safety  │     │ SageMaker│
               │  Store   │     │ Pipeline │     │ Endpoint │
               └──────────┘     └──────────┘     └──────────┘
                      │                │                 │
                      ▼                ▼                 ▼
               ┌──────────┐     ┌──────────┐     ┌──────────┐
               │ Progress │     │  Redis   │     │   SDXL   │
               │ Display  │◀────│  Cache   │◀────│ Pipeline│
               └──────────┘     └──────────┘     └──────────┘
```

### 3.2 Two-Pass Generation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        TWO-PASS PIPELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. FAST PASS (Turbo)          2. QUALITY PASS (Base)           │
│  ┌─────────────────────┐       ┌─────────────────────┐          │
│  │ SDXL Turbo          │       │ SDXL Base           │          │
│  │ - 4 steps           │  ───▶ │ - 25-50 steps       │         │
│  │ - ~5 seconds        │       │ - LoRA applied      │          │
│  │ - Preview quality   │       │ - High quality      │          │
│  └─────────────────────┘       └─────────────────────┘          │
│                                         │                       │
│                                         ▼                       │
│                                3. REFINER (Optional)            │
│                                ┌─────────────────────┐          │
│                                │ SDXL Refiner        │          │
│                                │ - Detail enhancement│          │
│                                │ - Final polish      │          │
│                                └─────────────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Identity V2 Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                     IDENTITY ENGINE V2                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: Face Image + Prompt                                     │
│            │                                                    │
│            ▼                                                    │
│  ┌─────────────────────┐                                        │
│  │   Face Detection    │◀── InsightFace                        │
│  │   & Embedding       │                                        │
│  └─────────────────────┘                                        │
│            │                                                    │
│            ▼                                                    │
│  ┌─────────────────────────────────────────────┐                │
│  │              METHOD SELECTION               │                │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────────┐    │                │
│  │  │InstantID│ │FaceAdapt│ │ PhotoMaker  │    │                │
│  │  │  (90%+) │ │   (85%) │ │   (80%+)    │    │                │
│  │  └─────────┘ └─────────┘ └─────────────┘    │                │
│  │                    OR                       │                │
│  │           ┌──────────────┐                  │                │
│  │           │   ENSEMBLE   │                  │                │
│  │           │  (99%+ acc)  │                  │                │
│  │           └──────────────┘                  │                │
│  └─────────────────────────────────────────────┘                │
│            │                                                    │
│            ▼                                                    │
│  ┌─────────────────────┐                                        │
│  │  ArcFace Scoring    │── Similarity > 0.75 = PASS             │
│  └─────────────────────┘                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Connections

### 4.1 Frontend → Backend Connections

```
apps/web/                          apps/api/
─────────────────────────────────────────────────────────────────
app/api/generate/route.ts    ───▶  app/api/v1/endpoints/generation.py
app/api/identities/route.ts  ───▶  app/api/v1/endpoints/identities.py
app/api/refine/route.ts      ───▶  app/api/v1/endpoints/generation.py
app/api/preferences/route.ts ───▶  app/api/v1/endpoints/preferences.py
app/api/variants/route.ts    ───▶  app/api/v1/endpoints/variants.py

lib/cloud-config.ts          ───▶  AWS API Gateway / FastAPI
lib/stores/generation-store  ───▶  /api/generate (local), AWS (direct)
lib/socket.ts                ───▶  Socket.IO server
```

### 4.2 Backend → AI Pipeline Connections

```
apps/api/                          ai-pipeline/
─────────────────────────────────────────────────────────────────
services/aws_gpu_client.py   ───▶  AWS SageMaker endpoints
services/ai/generation_service ─▶  services/generation_service.py
services/ai/quality_scorer   ───▶  services/quality_scorer.py
services/ai/prompt_builder   ───▶  services/midjourney_prompt_enhancer.py
services/ai/lora_trainer     ───▶  services/lora_trainer.py

services/safety/dual_pipeline ──▶  services/safety_service.py
services/safety/nsfw_classifier ─▶  services/adversarial_defense.py
```

### 4.3 Backend → AWS Connections

```
apps/api/                          aws/
─────────────────────────────────────────────────────────────────
services/aws_gpu_client.py   ───▶  sagemaker/model/code/inference.py
                             ───▶  sagemaker/model/code/inference_two_pass.py
                             ───▶  sagemaker/model/code/inference_identity_v2.py
                             ───▶  lambda/generation/handler.py
                             ───▶  lambda/orchestrator/handler.py
```

### 4.4 AI Pipeline Internal Connections

```
ai-pipeline/services/
─────────────────────────────────────────────────────────────────

orchestrator_aws.py
    ├── two_pass_generation.py
    ├── semantic_prompt_enhancer.py
    ├── midjourney_prompt_enhancer.py
    └── quality_scorer.py

deterministic_pipeline.py
    ├── scene_graph_compiler.py
    ├── camera_occlusion_solver.py
    ├── physics_micro_sim.py
    ├── tri_model_validator.py
    ├── iterative_refinement_v2.py
    ├── failure_memory_system.py
    └── prompt_enhancement_v3.py

identity_engine_v2.py
    ├── instantid_service.py
    ├── quality_scorer.py (ArcFace)
    └── lora_trainer.py

generation_service.py
    ├── composition_engine.py
    ├── creative_engine.py
    ├── realtime_engine.py
    └── ultra_high_res_engine.py
```

---

## 5. AI Pipeline Details

### 5.1 Core Services (`ai-pipeline/services/`)

#### Generation Services
| File | Imports From | Exports | Purpose |
|------|--------------|---------|---------|
| `generation_service.py` | `composition_engine`, `creative_engine`, `quality_scorer` | `GenerationService`, `generate_images` | Main generation orchestration |
| `two_pass_generation.py` | `torch`, `diffusers` | `generate_fast`, `generate_two_pass` | Two-pass pipeline |
| `realtime_engine.py` | `diffusers` (LCM) | `RealtimeEngine` | 8-10s preview generation |
| `ultra_high_res_engine.py` | `torch`, `diffusers` | `generate_4k_native_latent`, `generate_4k_iterative` | Native 4K generation |

#### Identity Services
| File | Imports From | Exports | Purpose |
|------|--------------|---------|---------|
| `identity_engine.py` | `insightface`, `instantid` | `IdentityEngine` | Identity V1 (90%+) |
| `identity_engine_v2.py` | `insightface`, `instantid`, `arcface` | `IdentityEngineV2`, `FaceConsistencyScorer` | Identity V2 ensemble |
| `instantid_service.py` | `diffusers`, `insightface` | `InstantIDService` | InstantID generation |
| `lora_trainer.py` | `torch`, `diffusers`, `insightface` | `LoRATrainer`, `train_lora_advanced` | LoRA training |

#### Prompt Services
| File | Imports From | Exports | Purpose |
|------|--------------|---------|---------|
| `semantic_prompt_enhancer.py` | `sentence_transformers` | `SemanticPromptEnhancer` | Semantic enhancement |
| `midjourney_prompt_enhancer.py` | `midjourney_concepts` | `enhance_prompt`, `build_negative_prompt` | Midjourney-style prompts |
| `universal_prompt_classifier.py` | `re`, pattern matching | `UniversalPromptClassifier`, `ClassificationResult` | Prompt classification |
| `smart_prompt_engine.py` | `universal_prompt_classifier` | `SmartPromptEngine`, `build_prompts` | Smart prompt building |
| `prompt_enhancement_v3.py` | scene graph, physics | `enhance_v3`, `PromptEnhancementV3Result` | V3 enhancement |

#### Deterministic Pipeline Services
| File | Imports From | Exports | Purpose |
|------|--------------|---------|---------|
| `deterministic_pipeline.py` | All deterministic services | `DeterministicPipeline` | Main deterministic orchestration |
| `scene_graph_compiler.py` | parsing, layout | `SceneGraphCompiler` | Scene graph creation |
| `camera_occlusion_solver.py` | geometry | `CameraOcclusionSolver` | Camera/occlusion resolution |
| `physics_micro_sim.py` | physics simulation | `PhysicsMicroSim` | Physics simulation |
| `tri_model_validator.py` | YOLO, OpenPose, SAM | `TriModelValidator`, `validate_anatomy` | Anatomy validation |
| `iterative_refinement_v2.py` | image analysis | `IterativeRefinementV2` | Issue localization, inpainting |
| `failure_memory_system.py` | `pattern_matcher` | `FailureMemorySystem` | Failure pattern storage |

#### Quality & Safety Services
| File | Imports From | Exports | Purpose |
|------|--------------|---------|---------|
| `quality_scorer.py` | `torch`, aesthetic model | `QualityScorer`, `score_image` | Multi-dimensional scoring |
| `quality_assessment.py` | `quality_scorer` | `assess_quality` | Quality verdicts |
| `safety_service.py` | classifiers | `SafetyService` | Content safety |
| `adversarial_defense.py` | detection models | `AdversarialDefense` | Attack defense |

### 5.2 Test Suite (`ai-pipeline/tests/`)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_end_to_end.py` | Full pipeline E2E | Simple, multi-person, weather, fantasy |
| `test_improvements.py` | Core improvements | InstantID, semantic, two-pass, quality |
| `test_identity_v2.py` | Identity V2 | Face scoring, ensemble, benchmark |
| `test_typography_engine.py` | Typography | Text overlay, watermark |
| `test_smart_prompt_engine.py` | Prompt engine | Classification, building |
| `test_dimension_manager.py` | Dimensions | Validation, resolution |
| `test_camera_occlusion_solver.py` | Camera/occlusion | Hat, prop, furniture |
| `test_tri_model_validator.py` | Tri-model | Anatomy validation |
| `test_failure_memory_system.py` | Failure memory | Pattern matching, fixes |
| `comprehensive_test_suite.py` | 1000-image benchmark | All categories |

---

## 6. Backend API Details

### 6.1 API Structure (`apps/api/`)

```
apps/api/
├── alembic/                       # Database migrations
│   └── versions/
│       ├── 001_add_safety_audit_logs.py
│       ├── 002_add_credit_transactions_and_usage.py
│       ├── 003_add_adversarial_logs.py
│       ├── 004_make_identity_nullable_in_generations.py
│       └── 005_add_generation_modes.py
│
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── router.py          # Main router
│   │       └── endpoints/
│   │           ├── admin.py       # Admin operations
│   │           ├── auth.py        # Authentication
│   │           ├── gallery.py     # Gallery endpoints
│   │           ├── generation.py  # Generation endpoints
│   │           ├── identities.py  # Identity management
│   │           ├── preferences.py # User preferences
│   │           ├── unified_generate.py # Unified API
│   │           └── variants.py    # Variant generation
│   │
│   ├── core/
│   │   ├── config.py              # Settings
│   │   ├── database.py            # DB connection
│   │   └── db.py                  # Session management
│   │
│   ├── models/
│   │   ├── generation.py          # Generation models
│   │   ├── safety.py              # Safety models
│   │   └── user.py                # User model (stub)
│   │
│   ├── schemas/
│   │   ├── generation.py          # Generation schemas
│   │   ├── identity.py            # Identity schemas
│   │   ├── responses.py           # Response schemas
│   │   └── user.py                # User schemas
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── aws_gpu_client.py      # AWS SageMaker/Lambda
│   │   ├── gpu_client.py          # GPU abstraction
│   │   ├── modal_client.py        # Modal (reference)
│   │   ├── tier_enforcer.py       # Tier enforcement
│   │   ├── midjourney_prompt_enhancer.py
│   │   ├── midjourney_concepts.py
│   │   │
│   │   ├── ai/
│   │   │   ├── generation_service.py
│   │   │   ├── lora_trainer.py
│   │   │   ├── prompt_builder.py
│   │   │   └── quality_scorer.py
│   │   │
│   │   ├── safety/
│   │   │   ├── dual_pipeline.py   # Pre+post safety
│   │   │   ├── nsfw_classifier.py # NSFW detection
│   │   │   ├── age_estimator.py   # Age estimation
│   │   │   ├── rate_limiter.py    # Rate limiting
│   │   │   ├── audit_logger.py    # Audit logging
│   │   │   └── adversarial_defense_bridge.py
│   │   │
│   │   └── storage/
│   │       └── s3_service.py      # S3 operations
│   │
│   ├── workers/
│   │   ├── worker_manager.py      # Worker management
│   │   └── metrics.py             # Worker metrics
│   │
│   └── tests/                     # Unit tests
│
└── tests/                         # Integration tests
```

### 6.2 API Endpoints

| Endpoint | Method | Handler | Purpose |
|----------|--------|---------|---------|
| `/api/v1/generation/sync` | POST | `generation.py` | Synchronous generation |
| `/api/v1/generation/async` | POST | `generation.py` | Async generation |
| `/api/v1/generation/{id}` | GET | `generation.py` | Get generation status |
| `/api/v1/identities` | GET/POST | `identities.py` | List/create identities |
| `/api/v1/identities/{id}` | GET/PUT/DELETE | `identities.py` | Identity CRUD |
| `/api/v1/identities/{id}/train` | POST | `identities.py` | Train LoRA |
| `/api/v1/gallery` | GET | `gallery.py` | Get gallery images |
| `/api/v1/preferences` | GET/PUT | `preferences.py` | User preferences |
| `/api/v1/variants` | POST | `variants.py` | Generate variants |
| `/api/v1/admin/*` | Various | `admin.py` | Admin operations |
| `/api/v1/auth/*` | Various | `auth.py` | Authentication |

### 6.3 Service Dependencies

```
apps/api/app/services/

aws_gpu_client.py
    └── Uses: boto3 (SageMaker, Lambda)
    └── Calls: AWS endpoints for generation

generation_service.py
    ├── Uses: aws_gpu_client.py
    ├── Uses: prompt_builder.py
    └── Uses: quality_scorer.py

safety/dual_pipeline.py
    ├── Uses: nsfw_classifier.py
    ├── Uses: age_estimator.py
    ├── Uses: rate_limiter.py
    └── Uses: audit_logger.py

storage/s3_service.py
    └── Uses: boto3 (S3)
```

---

## 7. Frontend Details

### 7.1 Page Structure (`apps/web/`)

```
apps/web/
├── app/
│   ├── (dashboard)/               # Dashboard layout group
│   │   ├── layout.tsx             # Dashboard layout
│   │   ├── dashboard-layout-client.tsx
│   │   │
│   │   ├── generate/
│   │   │   ├── page.tsx           # Generation page
│   │   │   └── GenerateClient.tsx # Client component
│   │   │
│   │   ├── gallery/
│   │   │   └── page.tsx           # Gallery page
│   │   │
│   │   ├── identity-vault/
│   │   │   └── page.tsx           # Identity management
│   │   │
│   │   └── settings/
│   │       └── page.tsx           # Settings page
│   │
│   ├── api/                       # API routes
│   │   ├── generate/
│   │   │   └── route.ts           # Generation API
│   │   ├── identities/
│   │   │   ├── route.ts           # Identities list
│   │   │   ├── upload/
│   │   │   │   └── route.ts       # Upload images
│   │   │   └── [id]/
│   │   │       ├── route.ts       # Single identity
│   │   │       └── train/
│   │   │           └── route.ts   # Train LoRA
│   │   ├── refine/
│   │   │   └── route.ts           # Refinement
│   │   ├── preferences/
│   │   │   └── route.ts           # Preferences
│   │   └── variants/
│   │       └── route.ts           # Variants
│   │
│   ├── globals.css                # Global styles
│   └── layout.tsx                 # Root layout
│
├── components/
│   ├── generate/
│   │   ├── index.ts               # Exports
│   │   ├── ModeSelector.tsx       # Mode selection
│   │   ├── PromptInput.tsx        # Prompt input
│   │   ├── GenerationProgress.tsx # Progress display
│   │   ├── two-pass-preview.tsx   # Two-pass preview
│   │   ├── QualityTierSlider.tsx  # Quality tier
│   │   ├── PhysicsToggles.tsx     # Physics options
│   │   ├── IterationSelector.tsx  # Iterations
│   │   ├── VariantsPanel.tsx      # Variants display
│   │   └── style-selector.tsx     # Style selection
│   │
│   ├── identity/
│   │   ├── create-identity-modal.tsx
│   │   └── delete-identity-dialog.tsx
│   │
│   └── landing/
│       ├── Navbar.tsx
│       ├── Hero.tsx
│       ├── Features.tsx
│       └── Footer.tsx
│
└── lib/
    ├── ai-service.ts              # AI service client
    ├── cloud-config.ts            # Cloud configuration
    ├── socket.ts                  # Socket.IO client
    │
    ├── stores/
    │   └── generation-store.ts    # Zustand store
    │
    └── types/
        └── generation.ts          # Generation types
```

### 7.2 Component Connections

```
GenerateClient.tsx
    ├── Uses: ModeSelector
    ├── Uses: PromptInput
    ├── Uses: GenerationProgress
    ├── Uses: QualityTierSlider
    ├── Uses: PhysicsToggles
    ├── Uses: IterationSelector
    ├── Uses: VariantsPanel
    ├── Uses: style-selector
    ├── Uses: two-pass-preview
    │
    ├── Imports: generation-store (Zustand)
    └── Calls: /api/generate, /api/variants

identity-vault/page.tsx
    ├── Uses: create-identity-modal
    ├── Uses: delete-identity-dialog
    │
    └── Calls: /api/identities
```

### 7.3 State Management

```
lib/stores/generation-store.ts (Zustand)
│
├── State:
│   ├── prompt: string
│   ├── mode: GenerationMode
│   ├── qualityTier: QualityTier
│   ├── isGenerating: boolean
│   ├── progress: number
│   ├── currentImage: string | null
│   ├── previewImage: string | null
│   └── variants: string[]
│
├── Actions:
│   ├── setPrompt(prompt)
│   ├── setMode(mode)
│   ├── setQualityTier(tier)
│   ├── generate()
│   ├── generateWithQualityTier(params)
│   └── reset()
│
└── Subscriptions:
    └── Socket.IO progress updates
```

---

## 8. AWS Infrastructure

### 8.1 Lambda Functions (`aws/lambda/`)

| Function | Handler | Memory | Timeout | Purpose |
|----------|---------|--------|---------|---------|
| `orchestrator` | `handler.lambda_handler` | 512MB | 600s | Quality tier routing |
| `orchestrator_v2` | `handler.lambda_handler` | 512MB | 600s | Smart routing + progress |
| `generation` | `handler.lambda_handler` | 1024MB | 300s | Direct generation |
| `post_processor` | `handler.lambda_handler` | 512MB | 120s | Post-processing |
| `prompt_enhancer` | `handler.lambda_handler` | 256MB | 30s | Prompt enhancement |
| `safety` | `handler.lambda_handler` | 512MB | 60s | Safety checks |
| `refinement` | `handler.lambda_handler` | 512MB | 300s | Refinement (placeholder) |
| `training` | `handler.lambda_handler` | 512MB | 600s | Training (placeholder) |

### 8.2 SageMaker Endpoints (`aws/sagemaker/`)

| Endpoint | Instance | Model | Purpose |
|----------|----------|-------|---------|
| `photogenius-generation-{env}` | ml.g5.2xlarge | SDXL Base | Single-pass generation |
| `photogenius-two-pass-{env}` | ml.g5.2xlarge | SDXL Turbo+Base+Refiner | Two-pass pipeline |
| `photogenius-identity-v2-{env}` | ml.g5.2xlarge | InstantID ensemble | Identity V2 |
| `photogenius-4k-{env}` | ml.g5.4xlarge | SDXL + upscale | Native 4K |
| `photogenius-realtime-{env}` | ml.g5.xlarge | LCM | Fast preview |
| `photogenius-aesthetic-{env}` | ml.g4dn.xlarge | Aesthetic model | Quality scoring |

### 8.3 SAM Template Structure (`aws/template.yaml`)

```yaml
Resources:
  # Lambda Functions
  SafetyFunction
  PromptEnhancerFunction
  PostProcessorFunction
  OrchestratorFunction
  GenerationFunction
  RefinementFunction
  TrainingFunction
  HealthFunction

  # API Gateway
  ApiGateway
  ApiGatewayDeployment

  # S3 Buckets
  ImagesBucket
  ModelsBucket
  LorasBucket

  # DynamoDB Tables
  GenerationTable

  # IAM Roles
  LambdaExecutionRole
  SageMakerRole

Parameters:
  Environment (dev/staging/prod)
  SageMakerEndpoint
  SageMakerTwoPassEndpoint
  SageMakerIdentityV2Endpoint
  IdentityEngineVersion
  IdentityMethod
```

---

## 9. Database Schema

### 9.1 Prisma Schema (`packages/database/prisma/schema.prisma`)

```prisma
// 13 Models

model User {
  id                String              @id @default(cuid())
  clerkId           String?             @unique
  email             String              @unique
  name              String?
  tier              Tier                @default(FREE)
  creditBalance     CreditBalance?
  identities        Identity[]
  generations       Generation[]
  transactions      Transaction[]
  stylePreferences  StylePreference[]
  generationPrefs   GenerationPreference[]
  apiKeys           ApiKey[]
  notifications     Notification[]
  createdAt         DateTime            @default(now())
  updatedAt         DateTime            @updatedAt
}

model Identity {
  id              String       @id @default(cuid())
  name            String
  userId          String
  user            User         @relation(fields: [userId], references: [id])
  loraPath        String?
  embeddingPath   String?
  referenceImages String[]
  status          IdentityStatus @default(PENDING)
  generations     Generation[]
  createdAt       DateTime     @default(now())
  updatedAt       DateTime     @updatedAt
}

model Generation {
  id              String       @id @default(cuid())
  userId          String
  user            User         @relation(fields: [userId], references: [id])
  identityId      String?
  identity        Identity?    @relation(fields: [identityId], references: [id])
  prompt          String
  negativePrompt  String?
  imageUrl        String
  thumbnailUrl    String?
  mode            GenerationMode
  qualityTier     QualityTier?
  width           Int
  height          Int
  steps           Int
  seed            Int?
  metadata        Json?
  status          GenerationStatus @default(COMPLETED)
  creditsUsed     Int          @default(1)
  createdAt       DateTime     @default(now())
}

model Transaction { ... }
model CreditBalance { ... }
model StylePreference { ... }
model GenerationPreference { ... }
model SafetyAuditLog { ... }
model AdversarialLog { ... }
model Webhook { ... }
model ApiKey { ... }
model UsageMetrics { ... }
model Notification { ... }

enum Tier { FREE, BASIC, PRO, ENTERPRISE }
enum IdentityStatus { PENDING, TRAINING, READY, FAILED }
enum GenerationMode { STANDARD, CREATIVE, REALISTIC, ARTISTIC }
enum QualityTier { FAST, STANDARD, PREMIUM, PERFECT }
enum GenerationStatus { PENDING, PROCESSING, COMPLETED, FAILED }
```

### 9.2 SQLAlchemy Models (`apps/api/app/models/`)

```python
# generation.py - Full implementation
class Generation(Base):
    __tablename__ = "generations"
    id: str
    user_id: str
    identity_id: Optional[str]
    prompt: str
    negative_prompt: Optional[str]
    image_url: str
    mode: str
    quality_tier: Optional[str]
    width: int
    height: int
    steps: int
    metadata: dict
    status: str
    credits_used: int
    created_at: datetime

# safety.py - Full implementation
class SafetyAuditLog(Base):
    __tablename__ = "safety_audit_logs"
    id: str
    user_id: str
    prompt: str
    result: str
    flags: list
    metadata: dict
    created_at: datetime
```

---

## 10. Service Dependencies

### 10.1 Python Dependencies

```
# Core AI
torch>=2.0.0
diffusers>=0.24.0
transformers>=4.35.0
accelerate>=0.24.0
safetensors>=0.4.0

# Face/Identity
insightface>=0.7.3
onnxruntime>=1.16.0

# Prompt Enhancement
sentence-transformers>=2.2.0

# Image Processing
Pillow>=10.0.0
opencv-python>=4.8.0

# Web Framework
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0

# Database
sqlalchemy>=2.0.0
alembic>=1.12.0
psycopg2-binary>=2.9.9

# AWS
boto3>=1.28.0

# Caching
redis>=5.0.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

### 10.2 NPM Dependencies

```json
{
  "dependencies": {
    "next": "14.x",
    "react": "18.x",
    "tailwindcss": "3.x",
    "@tanstack/react-query": "5.x",
    "zustand": "4.x",
    "socket.io-client": "4.x",
    "@clerk/nextjs": "4.x"
  }
}
```

### 10.3 External Services

| Service | Purpose | Configuration |
|---------|---------|---------------|
| AWS SageMaker | GPU inference | `SAGEMAKER_*` env vars |
| AWS Lambda | Serverless compute | SAM template |
| AWS S3 | Image storage | `S3_BUCKET`, `AWS_*` |
| AWS DynamoDB | Fast key-value | SAM template |
| PostgreSQL | Main database | `DATABASE_URL` |
| Redis/Upstash | Caching | `REDIS_URL` |
| Clerk | Authentication | `CLERK_*` env vars |
| Stripe | Payments | `STRIPE_*` (commented) |

---

## Appendix A: File Count Summary (Updated 2026-02-04)

| Directory | Python Files | TypeScript Files | Total |
|-----------|--------------|------------------|-------|
| `ai-pipeline/services/` | 83+ | - | 83+ |
| `ai-pipeline/tests/` | 47 | - | 47 |
| `apps/api/` | 79+ | - | 79+ |
| `apps/web/` | - | 220+ | 220+ |
| `apps/ai-service/` | 25+ | - | 25+ |
| `aws/` | 35+ | - | 35+ |
| `deploy/` | 10+ | - | 10+ |
| `frontend/` | - | 1 | 1 |
| `packages/` | - | 10+ | 10+ |
| **Total** | **279+** | **231+** | **510+** |

---

## Appendix B: Quick Reference

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# AWS
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
SAGEMAKER_ENDPOINT=photogenius-generation-dev
SAGEMAKER_TWO_PASS_ENDPOINT=photogenius-two-pass-dev
SAGEMAKER_IDENTITY_V2_ENDPOINT=photogenius-identity-v2-dev
S3_BUCKET=photogenius-images

# Auth
CLERK_SECRET_KEY=...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...

# AI
HUGGINGFACE_TOKEN=...
GPU_WORKER_PRIMARY=aws

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
AWS_API_GATEWAY_URL=https://...
```

### Key Commands

```bash
# Development
pnpm dev                    # Start all services
pnpm build                  # Build all packages

# AI Pipeline
cd ai-pipeline
pytest tests/ -v -s         # Run tests
pytest tests/ -m "not gpu"  # Skip GPU tests

# AWS Deployment
cd aws
./deploy.sh                 # Deploy SAM stack
python sagemaker/deploy_two_pass.py  # Deploy SageMaker

# Database
cd apps/api
alembic upgrade head        # Run migrations
```

---

**End of Document**

*For more details, see [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) and [ARCHITECTURE.md](ARCHITECTURE.md).*
