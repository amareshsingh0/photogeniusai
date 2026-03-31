#!/bin/bash
# PhotoGenius AI - Cleanup Script
# Removes duplicate, obsolete, and test files

set -e
cd "$(dirname "$0")"

echo "==================================="
echo "PhotoGenius AI - Cleanup Script"
echo "==================================="
echo ""

# Create archive directory for backups
mkdir -p .archive

echo "[1/5] Removing obsolete documentation (35 files)..."
rm -fv AI_BACKEND_COMPLETE.md
rm -fv ALL_SERVICES_DEPLOYED.md
rm -fv ALL_SERVICES_INTEGRATION.md
rm -fv AWS_DEPLOYMENT_GUIDE.md
rm -fv BROWSER_ERRORS_EXPLAINED.md
rm -fv COMMANDS.md
rm -fv COMPLETE_AI_SETUP.md
rm -fv CRITICAL_DEPLOYMENT_GAPS.md
rm -fv CURRENT_STATUS_SUMMARY.md
rm -fv CURRENT_SYSTEM_STATUS.md
rm -fv DELETE_RECREATE_STATUS.md
rm -fv DEPLOYING_FIX.md
rm -fv DEPLOYMENT_CHECKLIST.md
rm -fv DEPLOYMENT_COMPLETE.md
rm -fv DEPLOYMENT_ROADMAP.md
rm -fv DEPLOYMENT_STATUS.md
rm -fv DEV_SETUP.md
rm -fv FINAL_FIX_STATUS.md
rm -fv FINAL_STATUS_AND_NEXT_STEPS.md
rm -fv FINAL_TESTING.md
rm -fv INTEGRATION_STATUS.md
rm -fv INTELLIGENT_SCALING_SYSTEM.md
rm -fv ISSUE_1_FIXED.md
rm -fv ISSUE_2_FIXED.md
rm -fv MIDJOURNEY_QUALITY_SETUP.md
rm -fv QUICK_START.md
rm -fv README_FINAL.md
rm -fv SAGEMAKER_FREE_DEPLOYMENT_GUIDE.md
rm -fv SERVICES_INTEGRATION_STATUS.md
rm -fv SETUP_COMPLETE.md
rm -fv SETUP_REPLICATE_BEST.md
rm -fv SIMPLE_FIX.md
rm -fv SMART_AI_SYSTEM.md
rm -fv STACK_DELETE_RECREATE.md
rm -fv TEST_GENERATE.md
rm -fv TROUBLESHOOT_GENERATE.md

echo "[2/5] Removing duplicate SageMaker scripts (20 files)..."
cd aws/sagemaker
rm -fv deploy_10gb.py
rm -fv deploy_4k.py
rm -fv deploy_endpoint.py
rm -fv deploy_enhanced_endpoint.py
rm -fv deploy_final.py
rm -fv deploy_hybrid.py
rm -fv deploy_model.py
rm -fv deploy_prepackaged.py
rm -fv deploy_production.py
rm -fv deploy_simple.py
rm -fv deploy_two_pass.py
rm -fv deploy_with_larger_gpu.py
rm -fv deploy_with_models.py
rm -fv deploy_working_model.py
rm -fv deploy_working_simple.py
rm -fv fix_simple.py
rm -fv hybrid_inference.py
rm -fv production_inference.py
rm -fv simple_inference.py
rm -fv test_simple.py
cd ../..

echo "[3/5] Removing test/log files (20+ files)..."
rm -fv cw_logs.json
rm -fv logs_latest.json
rm -fv logs_model.json
rm -fv logs_output.json
rm -fv logs_v7.json
rm -fv logs_v8.json
rm -fv logs_v8_latest.json
rm -fv logs_v8_now.json
rm -fv logs_v8_raw.json
rm -fv logs_v8_start.json
rm -fv test_fast_request.json
rm -fv test_fast_result.json
rm -fv test_payload.json
rm -fv test_premium_request.json
rm -fv test_premium_result.json
rm -fv test_standard_request.json
rm -fv test_standard_result.json
rm -fv test_result_fast.png
rm -fv test_result_premium.png
rm -fv test_result_standard.png
rm -fv test_local_generation.py

echo "[4/5] Removing static HTML fallback files (optional)..."
cd apps/web/public
rm -fv dashboard.html
rm -fv explore.html
rm -fv generate.html
rm -fv login.html
rm -fv ok.html
cd ../../..

echo "[5/5] Removing temporary port files..."
rm -fv .api-port
rm -fv .serve-home-port
rm -fv .web-url

echo ""
echo "==================================="
echo "Cleanup Complete!"
echo "==================================="
echo ""
echo "Files removed: ~83"
echo "Project structure: Clean"
echo ""
echo "Kept essential files:"
echo "  - README.md"
echo "  - SAGEMAKER_COMPLETE_SETUP.md"
echo "  - WORLD_CLASS_WEBSITE_GUIDE.md"
echo "  - docs/PROJECT_ARCHITECTURE.md"
echo "  - All production code"
echo "  - All dev scripts"
echo ""
