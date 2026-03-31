# 🚀 Ubuntu Deployment Guide

Fast and reliable deployment on Ubuntu/Linux.

## Prerequisites

1. **AWS CLI configured**:
   ```bash
   aws configure
   # Enter your AWS credentials
   ```

2. **Python 3 installed**:
   ```bash
   python3 --version  # Should be 3.8+
   ```

## Quick Start

### Step 1: Make scripts executable

```bash
cd aws/sagemaker
chmod +x deploy_ubuntu.sh monitor_deployment.sh
```

### Step 2: Run deployment

```bash
./deploy_ubuntu.sh
```

**This will:**
- ✅ Download sdxl-turbo and sdxl-base-1.0 from S3 (~8-12 min)
- ✅ Create model.tar.gz (~3-5 min)
- ✅ Upload to S3 (~3-5 min)
- ✅ Deploy to SageMaker (~10-15 min)

**Total time: 25-35 minutes** (much faster than Windows!)

### Step 3: Monitor deployment

In a new terminal:

```bash
cd aws/sagemaker
./monitor_deployment.sh
```

Or manually check:

```bash
aws sagemaker describe-endpoint \
  --endpoint-name photogenius-generation-dev \
  --query 'EndpointStatus'
```

### Step 4: Test endpoint

Once status is `InService`:

```bash
cd aws/sagemaker
python3 test_endpoint.py
```

## What Gets Deployed

### Models Included:
- ✅ **sdxl-turbo** (~7GB) - For FAST tier
- ✅ **sdxl-base-1.0** (~14GB) - For STANDARD & PREMIUM tiers

### Quality Tiers:
1. **FAST**: Turbo, 4 steps, ~5 seconds
2. **STANDARD**: Base, 30 steps, ~25 seconds
3. **PREMIUM**: Base, 50 steps, ~40 seconds (Midjourney-quality)

## Troubleshooting

### Error: "AWS CLI not installed"
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### Error: "Credentials not configured"
```bash
aws configure
# Enter:
#   AWS Access Key ID
#   AWS Secret Access Key
#   Default region: us-east-1
#   Default output format: json
```

### Error: "Role not found"
The SageMaker execution role should already exist. If not:
```bash
aws iam get-role --role-name SageMakerExecutionRole
```

### Deployment failed
Check CloudWatch logs:
```bash
aws logs tail /aws/sagemaker/Endpoints/photogenius-generation-dev --follow
```

## Performance Comparison

| Platform | Download | Compress | Upload | Total |
|----------|----------|----------|--------|-------|
| Windows  | 15-20 min | 8-10 min | 8-10 min | 35-45 min |
| **Ubuntu** | **8-12 min** | **3-5 min** | **3-5 min** | **25-35 min** |

Ubuntu is **30-40% faster!** 🚀

## After Deployment

### Test all tiers:
```bash
python3 test_endpoint.py
```

### View generated images:
```bash
ls -lh test_outputs/
# test_fast.png - FAST tier
# test_standard.png - STANDARD tier
# test_premium.png - PREMIUM tier (best quality)
```

### Cleanup local files:
```bash
rm model.tar.gz  # Delete local tar file (~20GB)
rm -rf temp_model_package_*  # Remove temp directories
```

## Cost

- **Instance**: ml.g5.2xlarge = $1.21/hour
- **Storage**: ~20GB model.tar.gz in S3 = $0.46/month
- **Data transfer**: Download from S3 = Free (same region)

**Monthly cost**: ~$870/month (if running 24/7)

## Next Steps

1. ✅ Deploy endpoint (current step)
2. ✅ Test all three quality tiers
3. ✅ Verify Midjourney-quality results
4. 🔄 Update Lambda functions with new endpoint
5. 🔄 Test end-to-end from frontend

## Support

If you encounter issues, check:
- AWS credentials: `aws sts get-caller-identity`
- S3 bucket access: `aws s3 ls s3://photogenius-models-dev/`
- SageMaker permissions: `aws sagemaker list-endpoints`
