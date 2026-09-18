#!/bin/bash
set -e
echo "=== nginx site ==="
head -40 /etc/nginx/sites-available/amap.tingle272.xyz /etc/nginx/sites-available/amap.qrqto.club 2>/dev/null | head -40
echo "=== service ==="
systemctl is-active amap-find.service
echo "=== local http ==="
curl -sS -o /tmp/amap-cfg.json -w "local:%{http_code}\n" http://127.0.0.1:8010/api/config
python3 - <<'PY'
import json
d=json.load(open("/tmp/amap-cfg.json"))
print("key_configured", bool(d.get("amap_key_configured")), "has_js_key", bool(d.get("amap_js_key")))
PY
echo "=== https sni ==="
curl -sk --resolve amap.tingle272.xyz:443:127.0.0.1 -o /tmp/amap-cfg2.json -w "https:%{http_code}\n" https://amap.tingle272.xyz/api/config
python3 - <<'PY'
import json
d=json.load(open("/tmp/amap-cfg2.json"))
print("key_configured", bool(d.get("amap_key_configured")), "has_js_key", bool(d.get("amap_js_key")))
PY
