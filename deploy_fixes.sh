#!/bin/bash
# Deploy all fixes to production server

set -e

echo "🚀 Deploying fixes to PhotoGenius API..."

# Server details
SERVER="ubuntu@13.200.252.174"
REMOTE_DIR="/home/ubuntu/photogenius-api"

# Files to deploy
FILES=(
    "apps/api/app/services/smart/design_director.py"
    "apps/api/app/services/smart/design_agent_chain.py"
    "apps/api/app/api/v1/endpoints/generate_stream.py"
)

echo "📦 Uploading fixed files..."
for file in "${FILES[@]}"; do
    echo "  → $file"
    scp -i ~/.ssh/photogenius.pem "$file" "$SERVER:$REMOTE_DIR/$file"
done

echo "🔄 Restarting PM2 process..."
ssh -i ~/.ssh/photogenius.pem "$SERVER" << 'ENDSSH'
cd /home/ubuntu/photogenius-api
pm2 restart photogenius-api
pm2 logs photogenius-api --lines 20 --nostream
ENDSSH

echo "✅ Deployment complete!"
echo ""
echo "🧪 Test with:"
echo "curl -X POST http://13.200.252.174:8003/api/v1/generate/stream \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"prompt\": \"gym poster with text TRANSFORM and Join Now\", \"quality\": \"premium\"}'"
