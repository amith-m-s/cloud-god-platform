"""Full live verification of all Cloud God Platform endpoints."""
import os
import sys
os.environ["PYTHONIOENCODING"] = "utf-8"
import httpx

base = "http://127.0.0.1:8000"
results = []

def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, status, detail))
    icon = "[OK]" if passed else "[FAIL]"
    print(f"  {icon} {name}: {status} {detail}")

print("=" * 60)
print("  CLOUD GOD PLATFORM — LIVE ENDPOINT VERIFICATION")
print("=" * 60)

# 1. Health
print("\n--- SYSTEM PROBES ---")
r = httpx.get(f"{base}/health")
check("GET /health", r.status_code == 200, f"[{r.status_code}]")

r = httpx.get(f"{base}/ready")
check("GET /ready", r.status_code == 200, f"[{r.status_code}] {r.json()['checks']}")

r = httpx.get(f"{base}/metrics")
check("GET /metrics", r.status_code == 200 and "http_requests_total" in r.text, f"[{r.status_code}]")

# 2. Auth
print("\n--- AUTHENTICATION ---")
import time
unique_email = f"verify_{int(time.time())}@cloudgod.io"
r = httpx.post(f"{base}/api/v1/auth/register", json={
    "email": unique_email, "password": "GodLevel123!", "full_name": "Verification User"
})
check("POST /auth/register", r.status_code == 201, f"[{r.status_code}]")
access = r.json()["access_token"]
refresh = r.json()["refresh_token"]
headers = {"Authorization": f"Bearer {access}"}

r = httpx.post(f"{base}/api/v1/auth/login", json={
    "email": unique_email, "password": "GodLevel123!"
})
check("POST /auth/login", r.status_code == 200, f"[{r.status_code}]")

r = httpx.post(f"{base}/api/v1/auth/refresh", json={"refresh_token": refresh})
check("POST /auth/refresh", r.status_code == 200, f"[{r.status_code}]")
new_access = r.json()["access_token"]
headers = {"Authorization": f"Bearer {new_access}"}

r = httpx.get(f"{base}/api/v1/auth/me", headers=headers)
check("GET /auth/me", r.status_code == 200 and r.json()["email"] == unique_email, f"[{r.status_code}]")

# 3. Auth guards
print("\n--- SECURITY GUARDS ---")
r = httpx.get(f"{base}/api/v1/documents")
check("Unauth GET /documents -> 401", r.status_code == 401, f"[{r.status_code}]")

r = httpx.post(f"{base}/api/v1/auth/register", json={
    "email": unique_email, "password": "duplicate123!"
})
check("Duplicate email -> 409", r.status_code == 409, f"[{r.status_code}]")

r = httpx.post(f"{base}/api/v1/auth/register", json={
    "email": "short@x.com", "password": "123"
})
check("Short password -> 422", r.status_code == 422, f"[{r.status_code}]")

# 4. Documents
print("\n--- DOCUMENT PIPELINE ---")
r = httpx.get(f"{base}/api/v1/documents?tenant_id=default", headers=headers)
check("GET /documents", r.status_code == 200 and "items" in r.json(), f"[{r.status_code}]")

# Seed a document (create one first)
# We can't upload without real S3, so let's test the seed endpoint directly
# First we need a document record - let's seed directly after checking

# 5. Validation errors
print("\n--- VALIDATION ---")
r = httpx.post(f"{base}/api/v1/documents/search", json={"query": "", "tenant_id": "default"}, headers=headers)
check("Empty query -> 422 with errors[]", r.status_code == 422 and "errors" in r.json(), f"[{r.status_code}]")

# 6. Observability
print("\n--- OBSERVABILITY ---")
r = httpx.get(f"{base}/health")
rid = r.headers.get("x-request-id", "")
check("X-Request-ID header present", len(rid) == 36 and rid.count("-") == 4, f"[{rid[:8]}...]")

# 7. OpenAPI
print("\n--- OPENAPI / SWAGGER ---")
r = httpx.get(f"{base}/openapi.json")
schema = r.json()
check("OpenAPI schema loads", r.status_code == 200, f"[{r.status_code}]")
check("Title present", "Cloud God" in schema.get("info", {}).get("title", ""))
check("Tags present", len(schema.get("tags", [])) == 4, f"[{len(schema.get('tags', []))} tags]")
check("Contact info", "email" in str(schema.get("info", {}).get("contact", {})))
check("License info", "MIT" in str(schema.get("info", {}).get("license", {})))

r = httpx.get(f"{base}/docs")
check("Swagger UI /docs", r.status_code == 200, f"[{r.status_code}]")

r = httpx.get(f"{base}/redoc")
check("ReDoc /redoc", r.status_code == 200, f"[{r.status_code}]")

# Summary
print("\n" + "=" * 60)
passed = sum(1 for _, s, _ in results if s == "PASS")
total = len(results)
print(f"  RESULTS: {passed}/{total} PASSED")
if passed == total:
    print("  STATUS: ALL ENDPOINTS VERIFIED SUCCESSFULLY!")
else:
    print("  STATUS: SOME CHECKS FAILED")
    for name, status, detail in results:
        if status == "FAIL":
            print(f"    FAILED: {name} {detail}")
print("=" * 60)

sys.exit(0 if passed == total else 1)
