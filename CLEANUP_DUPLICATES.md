# PhotoGenius AI - Cleanup Plan

## Files to Remove (Safe to Delete)

### 1. Obsolete Documentation (35 files)
These are outdated status files from old deployment attempts:

```bash
rm -f AI_BACKEND_COMPLETE.md
rm -f ALL_SERVICES_DEPLOYED.md
rm -f ALL_SERVICES_INTEGRATION.md
rm -f AWS_DEPLOYMENT_GUIDE.md
rm -f BROWSER_ERRORS_EXPLAINED.md
rm -f COMMANDS.md
rm -f COMPLETE_AI_SETUP.md
rm -f CRITICAL_DEPLOYMENT_GAPS.md
rm -f CURRENT_STATUS_SUMMARY.md
rm -f CURRENT_SYSTEM_STATUS.md
rm -f DELETE_RECREATE_STATUS.md
rm -f DEPLOYING_FIX.md
rm -f DEPLOYMENT_CHECKLIST.md
rm -f DEPLOYMENT_COMPLETE.md
rm -f DEPLOYMENT_ROADMAP.md
rm -f DEPLOYMENT_STATUS.md
rm -f DEV_SETUP.md
rm -f FINAL_FIX_STATUS.md
rm -f FINAL_STATUS_AND_NEXT_STEPS.md
rm -f FINAL_TESTING.md
rm -f INTEGRATION_STATUS.md
rm -f INTELLIGENT_SCALING_SYSTEM.md
rm -f ISSUE_1_FIXED.md
rm -f ISSUE_2_FIXED.md
rm -f MIDJOURNEY_QUALITY_SETUP.md
rm -f QUICK_START.md
rm -f README_FINAL.md
rm -f SAGEMAKER_FREE_DEPLOYMENT_GUIDE.md
rm -f SERVICES_INTEGRATION_STATUS.md
rm -f SETUP_COMPLETE.md
rm -f SETUP_REPLICATE_BEST.md
rm -f SIMPLE_FIX.md
rm -f SMART_AI_SYSTEM.md
rm -f STACK_DELETE_RECREATE.md
rm -f TEST_GENERATE.md
rm -f TROUBLESHOOT_GENERATE.md
```

### 2. Duplicate SageMaker Deploy Scripts (15 files)
Keep only: `aws/sagemaker/model/code/inference.py` (production handler)

```bash
cd aws/sagemaker
rm -f deploy_10gb.py
rm -f deploy_4k.py
rm -f deploy_endpoint.py
rm -f deploy_enhanced_endpoint.py
rm -f deploy_final.py
rm -f deploy_hybrid.py
rm -f deploy_model.py
rm -f deploy_prepackaged.py
rm -f deploy_production.py
rm -f deploy_simple.py
rm -f deploy_two_pass.py
rm -f deploy_with_larger_gpu.py
rm -f deploy_with_models.py
rm -f deploy_working_model.py
rm -f deploy_working_simple.py
rm -f fix_simple.py
rm -f hybrid_inference.py
rm -f production_inference.py
rm -f simple_inference.py
rm -f test_simple.py
```

### 3. Test JSON/Log Files (20+ files)
These are temporary test outputs:

```bash
rm -f cw_logs.json
rm -f logs_latest.json
rm -f logs_model.json
rm -f logs_output.json
rm -f logs_v7.json
rm -f logs_v8.json
rm -f logs_v8_latest.json
rm -f logs_v8_now.json
rm -f logs_v8_raw.json
rm -f logs_v8_start.json
rm -f test_fast_request.json
rm -f test_fast_result.json
rm -f test_payload.json
rm -f test_premium_request.json
rm -f test_premium_result.json
rm -f test_standard_request.json
rm -f test_standard_result.json
rm -f test_result_fast.png
rm -f test_result_premium.png
rm -f test_result_standard.png
rm -f test_local_generation.py
```

### 4. Static HTML Fallback Files (Optional)
If Next.js is working, these are not needed:

```bash
cd apps/web/public
# Keep home.html and start.html for dev fallback
rm -f dashboard.html
rm -f explore.html
rm -f generate.html
rm -f login.html
rm -f ok.html
```

### 5. Temporary Port Files
```bash
rm -f .api-port
rm -f .serve-home-port
rm -f .web-url
```

## Files to KEEP (Essential)

### Documentation
- `README.md` - Main readme
- `SAGEMAKER_COMPLETE_SETUP.md` - Current production setup
- `WORLD_CLASS_WEBSITE_GUIDE.md` - Production roadmap
- `docs/PROJECT_ARCHITECTURE.md` - Full architecture
- `DEVELOPMENT_FIXED.md` - Dev setup notes
- `CLERK_WEBHOOK_SETUP.md` - Clerk setup
- `UVICORN_PROTOBUF_FIXED.md` - Important protobuf fix
- `SMART_BALANCED_SYSTEM.md` - Smart AI system design
- `SMART_AI_SERVICES_IMPLEMENTED.md` - Implementation guide
- `V3_API_TESTING_GUIDE.md` - API testing guide

### Production Code
- `aws/sagemaker/model/code/inference.py` - Production inference handler
- `aws/sagemaker/model/code/requirements.txt` - Dependencies
- `aws/sagemaker/download_models_to_s3.py` - Model download script
- `aws/sagemaker/package_models_from_s3.py` - Packaging script
- `aws/sagemaker/test_endpoint.py` - Production testing
- `upload_models_to_s3.sh` - S3 upload script

### Dev Scripts
- `scripts/run-web-dev.mjs` - Next.js dev runner
- `scripts/run-api-dev.mjs` - FastAPI dev runner
- `scripts/run-ai-dev.mjs` - AI service runner
- `scripts/serve-home.mjs` - Standalone home server
- `scripts/cleanup-ports.mjs` - Port cleanup

### Config
- `package.json` - Root workspace
- `turbo.json` - Turborepo config
- `pyrightconfig.json` - Python type checking

## Summary

**Total Cleanup:**
- Remove 35 obsolete markdown files
- Remove 20 duplicate deploy scripts
- Remove 20+ test/log files
- Remove 5 optional HTML files
- Remove 3 temporary port files

**Result:**
- Clean project structure
- Only essential documentation
- Production-ready codebase
- ~83 files removed, ~15 files kept

## Execute Cleanup

```bash
cd "c:/desktop/PhotoGenius AI"

# Run cleanup script
bash cleanup_all.sh
```
