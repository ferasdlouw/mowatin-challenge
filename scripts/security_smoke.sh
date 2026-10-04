#!/usr/bin/env bash
# Post-deploy security smoke test for the Muwattin API (Phase SEC). bash + curl only.
#
#   scripts/security_smoke.sh https://muwattin-api.onrender.com [https://mowatin.pages.dev]
#
# LLM cost: at most LLM_CALL_BUDGET calls (one flood request, D-034). The rate-limit check
# uses GET /v1/glossary, which calls no LLM. Run it once per deploy, not in a loop: it uses
# up the caller's per-minute limit for about a minute.
set -u

API="${1:?usage: security_smoke.sh API_URL [ALLOWED_ORIGIN]}"
API="${API%/}"
ORIGIN="${2:-https://mowatin.pages.dev}"
fails=0

check() { # name, condition result (0 = pass)
  if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; fails=$((fails + 1)); fi
}
code() { curl -s -o /dev/null -w "%{http_code}" "$@"; }

# 1. Health
[ "$(code "$API/health")" = "200" ]; check "health 200" $?

# 2. Docs hidden in production
for p in docs redoc openapi.json; do
  [ "$(code "$API/$p")" = "404" ]; check "/$p hidden (404)" $?
done

# 3. Security headers
headers="$(curl -s -D - -o /dev/null "$API/health" | tr -d '\r' | tr 'A-Z' 'a-z')"
for h in "x-content-type-options: nosniff" "strict-transport-security: max-age=31536000" \
         "x-frame-options: deny" "content-security-policy: default-src 'none'; frame-ancestors 'none'" \
         "referrer-policy: no-referrer" "cross-origin-resource-policy: same-site"; do
  grep -qF "$h" <<<"$headers"; check "header $h" $?
done

# 4. CORS: allowed origin echoed, foreign origin refused
allowed="$(curl -s -D - -o /dev/null -X OPTIONS "$API/v1/translate" -H "Origin: $ORIGIN" \
  -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type" | tr -d '\r')"
grep -qi "^access-control-allow-origin: $ORIGIN$" <<<"$allowed"; check "CORS allows $ORIGIN" $?
refused="$(curl -s -D - -o /dev/null -X OPTIONS "$API/v1/translate" -H "Origin: https://evil.example.com" \
  -H "Access-Control-Request-Method: POST" | tr -d '\r')"
! grep -qi "^access-control-allow-origin:" <<<"$refused"; check "CORS refuses a foreign origin" $?

# 5. Input validation (no LLM call)
[ "$(code -X POST "$API/v1/translate" -H "Content-Type: application/json" \
  -d '{"text":"x","debug":true}')" = "400" ]; check "extra field -> 400" $?
long="$(printf 'a%.0s' $(seq 4001))"
[ "$(code -X POST "$API/v1/translate" -H "Content-Type: application/json" \
  --data-binary @- <<<"{\"text\":\"$long\"}")" = "413" ]; check "4001 chars -> 413" $?

# 6. Flood input: 2000 segments come back quickly, capped, with the rest in review
flood="$(printf 'a.%.0s' $(seq 2000))"
started=$(date +%s)
body="$(curl -s -m 150 -X POST "$API/v1/translate" -H "Content-Type: application/json" \
  --data-binary @- <<<"{\"text\":\"$flood\",\"mode\":\"localize\"}")"
elapsed=$(( $(date +%s) - started ))
segments=$(grep -o '"id":[0-9]*' <<<"$body" | wc -l)
[ "$segments" -ge 1 ] && [ "$segments" -le 50 ]; check "flood capped ($segments segments, ${elapsed}s)" $?
[ "$elapsed" -le 120 ]; check "flood answered within 120 s" $?
grep -q '"review_queue":\[[0-9]' <<<"$body"; check "flood remainder is in review" $?

# 7. Rate limit: /v1/* answers 429 with Retry-After within 31 calls
got429=1
for _ in $(seq 31); do
  resp="$(curl -s -D - -o /dev/null "$API/v1/glossary?q=x" | tr -d '\r')"
  if grep -q "^HTTP/[0-9.]* 429" <<<"$resp"; then
    grep -qi "^retry-after: [0-9]" <<<"$resp" && got429=0
    break
  fi
done
check "rate limit -> 429 with Retry-After" $got429

echo
if [ "$fails" -eq 0 ]; then echo "security smoke: all checks passed"; else echo "security smoke: $fails check(s) failed"; fi
exit "$fails"
