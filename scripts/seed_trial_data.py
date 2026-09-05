"""RECON-X Pro Trial Data Generator & Judge Showcase Seeder.

Seeds a realistic enterprise dataset into RECON-X with:
- 8 spotlight scenarios (Clean matches, MDR fees, bank clearing delays, refunds, chargebacks, partial settlements, missing ERP entries, billing discrepancies)
- 100 background transactions
- 4-tier matching, AI investigation, deterministic policy guardrails, and audit trails.

Usage:
    python scripts/seed_trial_data.py
"""
import sys
import json
import urllib.request
import urllib.error

API_URL = "http://localhost:8000/api/v1/demo/seed-trial"

def run_seed():
    print("=" * 80)
    print("       RECON-X: PRO TRIAL DATA SEEDER FOR JUDGE PRESENTATION")
    print("=" * 80)
    print(f"Connecting to RECON-X Backend API at {API_URL}...")

    req = urllib.request.Request(API_URL, data=b"", method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Could not connect to RECON-X API: {e}")
        print("Please ensure the backend is running (e.g. docker-compose up or uvicorn app.main:app).")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("       PRO TRIAL DATASET SEEDED SUCCESSFULLY")
    print("=" * 80)
    print(f"Merchant Name        : {data['merchant_name']}")
    print(f"Merchant ID          : {data['merchant_id']}")
    print(f"Reconciliation Run ID: {data['run_id']}")
    print(f"Total Transactions   : {data['total_records']}")
    print(f"Matched Cleanly      : {data['matched_records']}")
    print(f"Exceptions Handled   : {data['exceptions_found']}")
    print(f"  |-- Auto-Resolved  : {data['auto_resolved_count']} (Safe timing & fee tolerances)")
    print(f"  \\-- Human Review   : {data['human_review_count']} (Chargebacks, missing ERP records, high variance)")
    print(f"Processing Time      : {data['processing_time_ms']} ms")
    print("=" * 80)

    print("\nSPOTLIGHT SCENARIOS READY IN UI:")
    print("-" * 80)
    for scenario_name, details in data.get("spotlight_scenarios", {}).items():
        print(f"* {scenario_name:<34} | Status: {details.get('status'):<14} | Action: {details.get('action')}")
        print(f"  Link: http://localhost:3000/exceptions/{details.get('exception_id')}")

    print("\n" + "=" * 80)
    print("PRESENTATION READY:")
    print("1. Open Dashboard  : http://localhost:3000")
    print("2. Exception Queue : http://localhost:3000/exceptions")
    print("3. 8-Scenario Tour : http://localhost:3000/demo")
    print("4. Benchmark Score : http://localhost:3000/evaluation")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_seed()
