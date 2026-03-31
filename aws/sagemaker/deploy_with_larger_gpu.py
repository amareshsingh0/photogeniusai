"""
Deploy with larger GPU instance for best quality.

Uses ml.g5.12xlarge with 4x A10G GPUs (96GB total GPU memory).
This allows loading all 3 models simultaneously for fastest generation.
"""

import boto3
import time
from pathlib import Path

# Configuration - USE LARGER INSTANCE
ENDPOINT_NAME = "photogenius-generation-dev"
S3_BUCKET = "photogenius-models-dev"
REGION = "us-east-1"
INSTANCE_TYPE = "ml.g5.12xlarge"  # 4x A10G, 96GB GPU memory, $7.09/hr

print(f"""
{'='*80}
PhotoGenius AI - Deploy with Larger GPU
{'='*80}

Instance Type: {INSTANCE_TYPE}
GPU Memory: 96GB (4x A10G GPUs)
Cost: $7.09/hour
Benefits:
  - All 3 models loaded simultaneously
  - Fastest generation (no model switching)
  - Best quality results
  - Best-of-N selection possible

{'='*80}
""")

response = input("Continue with ml.g5.12xlarge deployment? (yes/no): ")
if response.lower() != "yes":
    print("Deployment cancelled")
    exit(0)

# Use deploy_simple.py with updated instance type
import sys
sys.path.insert(0, str(Path(__file__).parent))

# Update instance type in deploy_simple
import deploy_simple
deploy_simple.INSTANCE_TYPE = INSTANCE_TYPE

print(f"\nDeploying with {INSTANCE_TYPE}...")
deploy_simple.main()
