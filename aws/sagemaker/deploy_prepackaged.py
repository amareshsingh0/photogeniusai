#!/usr/bin/env python3
"""
Deploy pre-packaged SageMaker endpoint
Models already in S3, model.tar.gz ready
"""

import boto3
import time
from sagemaker.huggingface import HuggingFaceModel
from sagemaker import get_execution_role

# Configuration
ENDPOINT_NAME = "photogenius-generation-dev"
S3_BUCKET = "photogenius-models-dev"
REGION = "us-east-1"
INSTANCE_TYPE = "ml.g5.2xlarge"

print("="*80)
print("PhotoGenius AI - SageMaker Deployment")
print("="*80)
print(f"\nEndpoint: {ENDPOINT_NAME}")
print(f"Instance: {INSTANCE_TYPE}")
print(f"Region: {REGION}\n")

# Get latest model.tar.gz from S3
s3 = boto3.client('s3', region_name=REGION)
sm = boto3.client('sagemaker', region_name=REGION)

print("Step 1: Finding latest model.tar.gz in S3...")
response = s3.list_objects_v2(
    Bucket=S3_BUCKET,
    Prefix='sagemaker/models/preloaded-',
    Delimiter='/'
)

if 'CommonPrefixes' not in response or not response['CommonPrefixes']:
    print("ERROR: No model.tar.gz found in S3!")
    print("\nExpected path: s3://{}/sagemaker/models/preloaded-*/model.tar.gz".format(S3_BUCKET))
    print("\nPlease upload model.tar.gz first.")
    exit(1)

# Get latest folder
folders = sorted([p['Prefix'] for p in response['CommonPrefixes']], reverse=True)
latest_folder = folders[0]
model_data_url = f"s3://{S3_BUCKET}/{latest_folder}model.tar.gz"

print(f"✓ Found: {model_data_url}\n")

# Get execution role
print("Step 2: Getting IAM execution role...")
try:
    role = get_execution_role()
    print(f"✓ Using session role")
except:
    # Fallback to named role
    iam = boto3.client('iam')
    role_response = iam.get_role(RoleName='SageMakerExecutionRole')
    role = role_response['Role']['Arn']
    print(f"✓ Using SageMakerExecutionRole")

print(f"   {role}\n")

# Delete old endpoint config if exists
print("Step 3: Cleaning up old configs...")
timestamp = int(time.time())
new_config_name = f"{ENDPOINT_NAME}-{timestamp}"

try:
    # Try to delete old config with same name as endpoint
    sm.delete_endpoint_config(EndpointConfigName=ENDPOINT_NAME)
    print(f"✓ Deleted old config: {ENDPOINT_NAME}")
    time.sleep(2)
except:
    pass  # Doesn't exist, that's fine

print(f"✓ Will create new config: {new_config_name}\n")

# Create HuggingFace Model
print("Step 4: Creating HuggingFace Model...")
huggingface_model = HuggingFaceModel(
    model_data=model_data_url,
    role=role,
    transformers_version='4.37.0',
    pytorch_version='2.1.0',
    py_version='py310',
    name=f"{ENDPOINT_NAME}-model-{timestamp}",
    sagemaker_session=None,  # Use default
)
print("✓ Model configured\n")

# Check if endpoint exists
print("Step 5: Checking existing endpoint...")
endpoint_exists = False
try:
    response = sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
    endpoint_exists = True
    current_status = response['EndpointStatus']
    print(f"✓ Endpoint exists (Status: {current_status})")

    if current_status == 'Creating' or current_status == 'Updating':
        print("\nWARNING: Endpoint is already being created/updated!")
        print("Wait for it to finish or delete it first:")
        print(f"  aws sagemaker delete-endpoint --endpoint-name {ENDPOINT_NAME}")
        exit(1)
except sm.exceptions.ClientError:
    print("✓ Endpoint doesn't exist (will create new)\n")

# Deploy
print("Step 6: Deploying endpoint...")
print("This takes 10-15 minutes...\n")

try:
    if endpoint_exists:
        print("Updating existing endpoint...")
        # For update, need to create config first then update endpoint
        config_name = new_config_name

        # Create endpoint config
        sm.create_endpoint_config(
            EndpointConfigName=config_name,
            ProductionVariants=[
                {
                    'VariantName': 'AllTraffic',
                    'ModelName': huggingface_model.name,
                    'InitialInstanceCount': 1,
                    'InstanceType': INSTANCE_TYPE,
                }
            ]
        )

        # Update endpoint
        sm.update_endpoint(
            EndpointName=ENDPOINT_NAME,
            EndpointConfigName=config_name
        )
        print(f"✓ Update initiated")
    else:
        # Deploy new endpoint (this handles config creation automatically)
        predictor = huggingface_model.deploy(
            initial_instance_count=1,
            instance_type=INSTANCE_TYPE,
            endpoint_name=ENDPOINT_NAME,
            wait=False,  # Don't wait, return immediately
        )
        print(f"✓ Deployment initiated")

    print("\n" + "="*80)
    print("Deployment Started Successfully!")
    print("="*80)
    print(f"\nEndpoint: {ENDPOINT_NAME}")
    print(f"Status: Creating (10-15 minutes)")
    print("\nMonitor progress:")
    print(f"  watch -n 5 'aws sagemaker describe-endpoint --endpoint-name {ENDPOINT_NAME} --query EndpointStatus --output text'")
    print("\nOr check logs:")
    print(f"  aws logs tail /aws/sagemaker/Endpoints/{ENDPOINT_NAME} --follow")
    print()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
