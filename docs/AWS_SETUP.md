# ☁️ AWS Setup Guide

PhotoGenius AI ko AWS pe setup karne ka complete guide.
Development aur Production dono environments ke liye.

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Development Setup](#development-setup)
4. [Production Setup](#production-setup)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Monitoring & Logging](#monitoring--logging)
7. [Cost Optimization](#cost-optimization)
8. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

### Development Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Local Laptop   │────▶│   AWS Lambda    │────▶│   SageMaker     │
│  (Frontend)     │     │  (API Gateway)  │     │  (GPU/ML)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │   S3 Bucket     │
                        │  (Models/LoRA)  │
                        └─────────────────┘
```

### Production Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CloudFront    │────▶│   API Gateway   │────▶│   Lambda/ECS    │
│   (CDN)         │     │   (REST API)    │     │   (Backend)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   S3 Bucket     │     │   RDS/Aurora    │     │   SageMaker     │
│   (Static)      │     │   (Database)    │     │   (AI/GPU)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 🔑 Prerequisites

### 1. AWS Account
- Sign up at https://aws.amazon.com
- Enable billing alerts
- Create IAM user with programmatic access

### 2. AWS CLI Installation

```bash
# Windows (PowerShell)
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# Mac
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### 3. Configure AWS CLI

```bash
aws configure
```
Enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region: `us-east-1`
- Output format: `json`

### 4. Install Additional Tools

```bash
# SAM CLI (Serverless)
pip install aws-sam-cli

# CDK (Infrastructure as Code)
npm install -g aws-cdk

# Verify
aws --version
sam --version
cdk --version
```

---

## 💻 Development Setup

### Step 1: Create S3 Buckets

```bash
# Models bucket
aws s3 mb s3://photogenius-models-dev --region us-east-1

# LoRA weights bucket
aws s3 mb s3://photogenius-loras-dev --region us-east-1

# Generated images bucket
aws s3 mb s3://photogenius-images-dev --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket photogenius-models-dev \
  --versioning-configuration Status=Enabled
```

### Step 2: Create IAM Role for Lambda

Create `aws/iam-lambda-role.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

```bash
# Create role
aws iam create-role \
  --role-name photogenius-lambda-role \
  --assume-role-policy-document file://aws/iam-lambda-role.json

# Attach policies
aws iam attach-role-policy \
  --role-name photogenius-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam attach-role-policy \
  --role-name photogenius-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam attach-role-policy \
  --role-name photogenius-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
```

### Step 3: Create Lambda Functions

Create `aws/lambda/safety/handler.py`:

```python
import json
import re

BLOCKED_KEYWORDS = [
    "nude", "naked", "nsfw", "explicit",
    "child", "minor", "underage",
]

def lambda_handler(event, context):
    """Safety check Lambda function"""
    body = json.loads(event.get("body", "{}"))
    prompt = body.get("prompt", "").lower()
    mode = body.get("mode", "REALISM")

    violations = []
    for keyword in BLOCKED_KEYWORDS:
        if keyword in prompt:
            violations.append(f"Blocked keyword: {keyword}")

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "allowed": len(violations) == 0,
            "violations": violations,
        })
    }
```

Create `aws/lambda/safety/requirements.txt`:
```
# No dependencies for safety check
```

### Step 4: Deploy Lambda with SAM

Create `aws/template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: PhotoGenius AI Lambda Functions

Globals:
  Function:
    Timeout: 30
    MemorySize: 256
    Runtime: python3.11
    Environment:
      Variables:
        ENVIRONMENT: development
        S3_BUCKET: photogenius-images-dev

Resources:
  # Safety Check Function
  SafetyFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: photogenius-safety-dev
      CodeUri: lambda/safety/
      Handler: handler.lambda_handler
      Events:
        SafetyApi:
          Type: Api
          Properties:
            Path: /safety
            Method: post

  # Generation Trigger Function (calls SageMaker)
  GenerationFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: photogenius-generation-dev
      CodeUri: lambda/generation/
      Handler: handler.lambda_handler
      Timeout: 300
      MemorySize: 1024
      Policies:
        - AmazonSageMakerFullAccess
        - AmazonS3FullAccess
      Events:
        GenerationApi:
          Type: Api
          Properties:
            Path: /generate
            Method: post

  # Refinement Function
  RefinementFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: photogenius-refinement-dev
      CodeUri: lambda/refinement/
      Handler: handler.lambda_handler
      Timeout: 300
      MemorySize: 1024
      Events:
        RefinementApi:
          Type: Api
          Properties:
            Path: /refine
            Method: post

  # Training Trigger Function
  TrainingFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: photogenius-training-dev
      CodeUri: lambda/training/
      Handler: handler.lambda_handler
      Timeout: 60
      Policies:
        - AmazonSageMakerFullAccess
        - AmazonS3FullAccess
      Events:
        TrainingApi:
          Type: Api
          Properties:
            Path: /train
            Method: post

Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint
    Value: !Sub "https://${ServerlessRestApi}.execute-api.${AWS::Region}.amazonaws.com/Prod"
```

Deploy:

```bash
cd aws

# Build
sam build

# Deploy (first time - guided)
sam deploy --guided

# Subsequent deployments
sam deploy
```

### Step 5: Create SageMaker Endpoint

Create `aws/sagemaker/deploy_endpoint.py`:

```python
import boto3
import sagemaker
from sagemaker.huggingface import HuggingFaceModel

def deploy_generation_endpoint():
    """Deploy SDXL model to SageMaker"""

    role = "arn:aws:iam::YOUR_ACCOUNT_ID:role/photogenius-sagemaker-role"

    # HuggingFace Model
    hub = {
        'HF_MODEL_ID': 'stabilityai/stable-diffusion-xl-base-1.0',
        'HF_TASK': 'text-to-image',
    }

    huggingface_model = HuggingFaceModel(
        transformers_version='4.37.0',
        pytorch_version='2.1.0',
        py_version='py310',
        env=hub,
        role=role,
    )

    # Deploy
    predictor = huggingface_model.deploy(
        initial_instance_count=1,
        instance_type='ml.g5.2xlarge',  # NVIDIA A10G GPU
        endpoint_name='photogenius-generation-dev',
    )

    print(f"Endpoint deployed: {predictor.endpoint_name}")
    return predictor.endpoint_name

if __name__ == "__main__":
    deploy_generation_endpoint()
```

```bash
# Create SageMaker role first
aws iam create-role \
  --role-name photogenius-sagemaker-role \
  --assume-role-policy-document file://aws/iam-sagemaker-role.json

# Deploy endpoint
cd aws/sagemaker
python deploy_endpoint.py
```

### Step 6: Update Environment Variables

```bash
# apps/web/.env.local
CLOUD_PROVIDER=aws
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Lambda URLs (from SAM deploy output)
AWS_LAMBDA_SAFETY_URL=https://xxx.execute-api.us-east-1.amazonaws.com/Prod/safety
AWS_LAMBDA_GENERATION_URL=https://xxx.execute-api.us-east-1.amazonaws.com/Prod/generate
AWS_LAMBDA_REFINEMENT_URL=https://xxx.execute-api.us-east-1.amazonaws.com/Prod/refine
AWS_LAMBDA_TRAINING_URL=https://xxx.execute-api.us-east-1.amazonaws.com/Prod/train

# SageMaker Endpoints
AWS_SAGEMAKER_GENERATION_ENDPOINT=photogenius-generation-dev
```

### Step 7: Test Development Setup

```bash
# Test safety endpoint
curl -X POST https://xxx.execute-api.us-east-1.amazonaws.com/Prod/safety \
  -H "Content-Type: application/json" \
  -d '{"prompt": "professional headshot", "mode": "REALISM"}'

# Start frontend
cd apps/web
pnpm dev
```

---

## 🚀 Production Setup

### Step 1: Create Production Infrastructure

Create `aws/cdk/lib/photogenius-stack.ts`:

```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';

export class PhotoGeniusStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VPC
    const vpc = new ec2.Vpc(this, 'PhotoGeniusVPC', {
      maxAzs: 2,
    });

    // S3 Buckets
    const imagesBucket = new s3.Bucket(this, 'ImagesBucket', {
      bucketName: 'photogenius-images-prod',
      cors: [{
        allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.PUT],
        allowedOrigins: ['*'],
        allowedHeaders: ['*'],
      }],
    });

    // RDS Database
    const database = new rds.DatabaseInstance(this, 'Database', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_15,
      }),
      instanceType: ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MEDIUM
      ),
      vpc,
      databaseName: 'photogenius',
    });

    // Lambda Functions
    const safetyLambda = new lambda.Function(this, 'SafetyLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset('lambda/safety'),
      timeout: cdk.Duration.seconds(30),
    });

    const generationLambda = new lambda.Function(this, 'GenerationLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset('lambda/generation'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
    });

    // API Gateway
    const api = new apigateway.RestApi(this, 'PhotoGeniusApi', {
      restApiName: 'PhotoGenius API',
      deployOptions: {
        stageName: 'prod',
        throttlingRateLimit: 1000,
        throttlingBurstLimit: 2000,
      },
    });

    // Routes
    const safetyResource = api.root.addResource('safety');
    safetyResource.addMethod('POST', new apigateway.LambdaIntegration(safetyLambda));

    const generateResource = api.root.addResource('generate');
    generateResource.addMethod('POST', new apigateway.LambdaIntegration(generationLambda));

    // CloudFront
    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: new cdk.aws_cloudfront_origins.S3Origin(imagesBucket),
      },
    });

    // Outputs
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
    });
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: distribution.distributionDomainName,
    });
  }
}
```

### Step 2: Deploy Production

```bash
cd aws/cdk

# Install dependencies
npm install

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy
cdk deploy --all
```

### Step 3: Setup SageMaker for Production

```python
# aws/sagemaker/deploy_production.py
import boto3
from sagemaker.huggingface import HuggingFaceModel

def deploy_production_endpoint():
    """Deploy production SDXL endpoint with auto-scaling"""

    role = "arn:aws:iam::YOUR_ACCOUNT_ID:role/photogenius-sagemaker-role"

    hub = {
        'HF_MODEL_ID': 'stabilityai/stable-diffusion-xl-base-1.0',
        'HF_TASK': 'text-to-image',
    }

    model = HuggingFaceModel(
        transformers_version='4.37.0',
        pytorch_version='2.1.0',
        py_version='py310',
        env=hub,
        role=role,
    )

    # Production deployment with auto-scaling
    predictor = model.deploy(
        initial_instance_count=2,  # Start with 2 instances
        instance_type='ml.g5.2xlarge',
        endpoint_name='photogenius-generation-prod',
    )

    # Setup auto-scaling
    client = boto3.client('application-autoscaling')

    # Register scalable target
    client.register_scalable_target(
        ServiceNamespace='sagemaker',
        ResourceId=f'endpoint/{predictor.endpoint_name}/variant/AllTraffic',
        ScalableDimension='sagemaker:variant:DesiredInstanceCount',
        MinCapacity=1,
        MaxCapacity=10,
    )

    # Add scaling policy
    client.put_scaling_policy(
        PolicyName='photogenius-generation-scaling',
        ServiceNamespace='sagemaker',
        ResourceId=f'endpoint/{predictor.endpoint_name}/variant/AllTraffic',
        ScalableDimension='sagemaker:variant:DesiredInstanceCount',
        PolicyType='TargetTrackingScaling',
        TargetTrackingScalingPolicyConfiguration={
            'TargetValue': 70.0,  # Scale at 70% GPU utilization
            'PredefinedMetricSpecification': {
                'PredefinedMetricType': 'SageMakerVariantInvocationsPerInstance',
            },
            'ScaleInCooldown': 300,
            'ScaleOutCooldown': 60,
        },
    )

    return predictor.endpoint_name

if __name__ == "__main__":
    deploy_production_endpoint()
```

### Step 4: Production Environment Variables

```bash
# apps/web/.env.local (Production)
NODE_ENV=production
CLOUD_PROVIDER=aws
AWS_REGION=us-east-1

# API Gateway
AWS_LAMBDA_SAFETY_URL=https://xxx.execute-api.us-east-1.amazonaws.com/prod/safety
AWS_LAMBDA_GENERATION_URL=https://xxx.execute-api.us-east-1.amazonaws.com/prod/generate

# SageMaker
AWS_SAGEMAKER_GENERATION_ENDPOINT=photogenius-generation-prod

# Database (RDS)
DATABASE_URL=postgresql://user:pass@xxx.rds.amazonaws.com:5432/photogenius

# CloudFront
CLOUDFRONT_DOMAIN=xxx.cloudfront.net
NEXT_PUBLIC_CDN_URL=https://xxx.cloudfront.net
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

Create `.github/workflows/aws-deploy.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: us-east-1

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v2
        with:
          version: 8
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'pnpm'
      - run: pnpm install
      - run: pnpm lint
      - run: pnpm test

  deploy-lambda:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - uses: aws-actions/setup-sam@v2

      - name: Build SAM
        run: cd aws && sam build

      - name: Deploy SAM
        run: |
          cd aws
          sam deploy \
            --no-confirm-changeset \
            --no-fail-on-empty-changeset \
            --stack-name photogenius-prod

  deploy-frontend:
    needs: deploy-lambda
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v2
        with:
          version: 8

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'pnpm'

      - run: pnpm install
      - run: pnpm build

      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

---

## 📊 Monitoring & Logging

### CloudWatch Setup

```bash
# Create log groups
aws logs create-log-group --log-group-name /aws/lambda/photogenius-safety
aws logs create-log-group --log-group-name /aws/lambda/photogenius-generation
aws logs create-log-group --log-group-name /aws/sagemaker/photogenius

# Set retention
aws logs put-retention-policy \
  --log-group-name /aws/lambda/photogenius-safety \
  --retention-in-days 30
```

### CloudWatch Dashboard

```bash
# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name PhotoGenius \
  --dashboard-body file://aws/cloudwatch-dashboard.json
```

---

## 💰 Cost Optimization

### Development Costs (Estimated)

| Service | Configuration | Cost/Month |
|---------|--------------|------------|
| Lambda | 1M requests | ~$0.20 |
| SageMaker | ml.g5.2xlarge (on-demand) | ~$100 |
| S3 | 10GB storage | ~$0.23 |
| API Gateway | 1M requests | ~$3.50 |
| **Total** | | **~$105/month** |

### Production Costs (Estimated)

| Service | Configuration | Cost/Month |
|---------|--------------|------------|
| Lambda | 10M requests | ~$2 |
| SageMaker | 2x ml.g5.2xlarge | ~$1,500 |
| RDS | db.t3.medium | ~$30 |
| CloudFront | 100GB transfer | ~$10 |
| S3 | 100GB storage | ~$2.30 |
| **Total** | | **~$1,550/month** |

### Cost Saving Tips

```bash
# Use Spot Instances for SageMaker Training
# 70% cheaper than on-demand

# Use Reserved Instances for production
# 30-40% cheaper with 1-year commitment

# Use S3 Intelligent Tiering
aws s3api put-bucket-intelligent-tiering-configuration \
  --bucket photogenius-images-prod \
  --id entire-bucket \
  --intelligent-tiering-configuration '{"Status": "Enabled"}'
```

---

## 🔧 Troubleshooting

### Lambda Timeout
```bash
# Increase timeout
aws lambda update-function-configuration \
  --function-name photogenius-generation-dev \
  --timeout 300
```

### SageMaker Cold Start
```bash
# Keep endpoint warm with scheduled invocations
aws events put-rule \
  --name photogenius-warmup \
  --schedule-expression "rate(5 minutes)"
```

### API Gateway 502 Error
```bash
# Check Lambda logs
aws logs tail /aws/lambda/photogenius-generation --follow
```

---

## 📁 AWS Project Structure

```
PhotoGenius AI/
├── aws/
│   ├── template.yaml         # SAM template
│   ├── samconfig.toml        # SAM config
│   ├── lambda/
│   │   ├── safety/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── generation/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── refinement/
│   │   └── training/
│   ├── sagemaker/
│   │   ├── deploy_endpoint.py
│   │   └── deploy_production.py
│   └── cdk/                   # CDK for production
│       ├── lib/
│       │   └── photogenius-stack.ts
│       └── package.json
└── docs/
    └── AWS_SETUP.md
```

---

## ✅ Checklist

### Development
- [ ] AWS CLI installed & configured
- [ ] S3 buckets created
- [ ] IAM roles created
- [ ] Lambda functions deployed (SAM)
- [ ] SageMaker endpoint deployed
- [ ] Environment variables updated
- [ ] Frontend tested with AWS backend

### Production
- [ ] CDK stack deployed
- [ ] RDS database setup
- [ ] CloudFront distribution created
- [ ] Auto-scaling configured
- [ ] CI/CD pipeline setup
- [ ] Monitoring dashboard created
- [ ] SSL certificate configured
