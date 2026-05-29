#!/bin/bash
# End-to-end test: create template under 示例工作台, then verify it appears in project structure
set -e

BASE="http://127.0.0.1:47829"
CLIENT_ID="client_53d82aa249"

echo "=== Step 1: Create template module ==="
RESULT=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/v1/clients/$CLIENT_ID/project-modules" \
  -H "Content-Type: application/json" \
  -d '{"name":"烟测模板","goal":"自动测试","templateTasksJson":"{\"tasks\":[{\"id\":\"t1\",\"title\":\"第一步\",\"description\":\"测试\",\"relativeDays\":0,\"durationMinutes\":60,\"priority\":\"normal\"}],\"options\":{\"autoCreateEventLine\":true,\"aiFillEmpty\":false}}"}')
HTTP_CODE=$(echo "$RESULT" | tail -1)
BODY=$(echo "$RESULT" | head -1)
echo "HTTP: $HTTP_CODE"
echo "Body: $BODY"
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: create returned $HTTP_CODE"
  exit 1
fi
MODULE_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Created module: $MODULE_ID"

echo ""
echo "=== Step 2: Verify in project structure ==="
STRUCTURE=$(curl -s "$BASE/api/v1/clients/$CLIENT_ID/project-structure")
FOUND=$(echo "$STRUCTURE" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for m in d.get('modules', []):
    if m['id'] == '$MODULE_ID':
        has_template = bool(m.get('templateTasksJson'))
        print(f'FOUND: {m[\"name\"]}  hasTemplate={has_template}')
        sys.exit(0)
print('NOT_FOUND')
sys.exit(1)
" 2>&1)
echo "$FOUND"

echo ""
echo "=== Step 3: Clean up ==="
sqlite3 "/Users/example_user/Library/Application Support/YiyuThinkTankWorkbench/app.db" "DELETE FROM project_modules WHERE id = '$MODULE_ID'"
echo "Cleaned up $MODULE_ID"

echo ""
echo "=== ALL TESTS PASSED ==="
