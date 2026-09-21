"""Quick script to test all endpoints against the live server."""
import httpx
import json
import sys

BASE = "http://127.0.0.1:8000"
RUN_ID = "c74eb2fd-d114-4279-ac80-961b89f6482f"

def test_get_findings():
    r = httpx.get(f"{BASE}/discover/{RUN_ID}/findings", timeout=10)
    d = r.json()
    print(f"\n=== GET /discover/{{id}}/findings ===")
    print(f"Status: {r.status_code}, count: {len(d)}")
    for f in d:
        ev_ids = f.get("supporting_evidence_ids", [])
        ev_summ = f.get("supporting_evidence", [])
        print(f"  [{f['change_status']}] {f['finding_type']}: {f['title'][:80]}")
        print(f"    importance={f['importance_score']}, confidence={f['confidence_score']}, evidence_ids={ev_ids}")
        if ev_summ:
            print(f"    supporting_evidence count: {len(ev_summ)}")

def test_get_evidence():
    r = httpx.get(f"{BASE}/discover/{RUN_ID}/evidence", timeout=10)
    d = r.json()
    print(f"\n=== GET /discover/{{id}}/evidence ===")
    print(f"Status: {r.status_code}, count: {len(d)}")
    for e in d[:5]:
        print(f"  [{e['change_status']}] {e['relevance']} (score={e['relevance_score']:.3f})")
        print(f"    src={e['source_name']}, quality={e['source_quality']}, title={str(e.get('title',''))[:60]}")
    if len(d) > 5:
        print(f"  ... and {len(d)-5} more")

def test_get_status():
    r = httpx.get(f"{BASE}/discover/status", timeout=10)
    d = r.json()
    print(f"\n=== GET /discover/status ===")
    print(f"Status: {r.status_code}, items: {len(d)}")
    for s in d:
        print(f"  {s['brand']} / {s['market']} / {s['research_type']}: {s['status']} (findings={s['findings_count']})")

def test_404():
    r = httpx.get(f"{BASE}/discover/00000000-0000-0000-0000-000000000000", timeout=10)
    print(f"\n=== GET /discover/{{missing_id}} ===")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.json()}")

if __name__ == "__main__":
    test_get_findings()
    test_get_evidence()
    test_get_status()
    test_404()
    print("\n=== All endpoint tests passed ===")
