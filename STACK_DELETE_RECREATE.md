# 🔄 Full Stack Delete & Recreate

**Time**: 14:12 UTC  
**Strategy**: Nuclear option - delete EVERYTHING and start fresh

---

## Why This Approach:

CloudFormation stuck in `UPDATE_ROLLBACK_FAILED` loop:

- Manually deleted Lambda → Stack expected it
- Rollback tried to recreate → Failed
- Update tried again → Lambda missing → Failed again
- **LOOP!** ⚠️

---

## What We're Doing:

### Step 1: DELETE Entire Stack ⏳

```powershell
aws cloudformation delete-stack --stack-name photogenius
```

This will delete:

- ✅ All Lambda functions (8 total)
- ✅ API Gateway
- ✅ DynamoDB tables
- ✅ IAM roles
- ✅ ALL CloudFormation resources

**SageMaker SAFE** - deployed separately! ✅

---

### Step 2: Wait for Deletion (3-5 mins)

Stack deletion takes time because CloudFormation must:

1. Delete all Lambda functions
2. Delete API Gateway
3. Delete DynamoDB tables (may have data)
4. Delete IAM roles
5. Remove all dependencies in order

---

### Step 3: Fresh Deploy

After deletion completes:

```powershell
sam deploy --guided
```

This will:

- ✅ Create FRESH stack from scratch
- ✅ Deploy NEW Lambda code (v2.0)
- ✅ Set correct environment variables
- ✅ Connect to existing SageMaker
- ✅ NO cached code issues!

---

## ETA: 8-12 minutes total

- Deletion: 3-5 mins
- Fresh deployment: 5-7 mins

---

**Monitoring deletion now...**
