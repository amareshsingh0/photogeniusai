#!/usr/bin/env bash
# Delete ALL PhotoGenius SageMaker endpoints in the region (one command).
# Only deletes endpoints whose names start with "photogenius-".
# Usage: ./delete-all-sagemaker.sh [us-east-1]
set -e
REGION="${1:-us-east-1}"
echo "Listing SageMaker endpoints in $REGION (photogenius-* only)..."
JSON=$(aws sagemaker list-endpoints --region "$REGION" --output json 2>/dev/null || echo '{"Endpoints":[]}')
NAMES=$(echo "$JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for e in d.get('Endpoints',[]):
    if e.get('EndpointName','').startswith('photogenius-'):
        print(e['EndpointName'])
" 2>/dev/null || true)
if [ -z "$NAMES" ]; then
  echo "No PhotoGenius endpoints found. Nothing to delete."
  exit 0
fi
echo "Found: $NAMES"
read -p "Delete all? (y/N) " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then echo "Aborted."; exit 0; fi
for name in $NAMES; do
  echo "Deleting $name ..."
  aws sagemaker delete-endpoint --endpoint-name "$name" --region "$REGION" && echo "  OK" || echo "  Failed"
done
echo "Done. Endpoints transitioning to Deleting."
