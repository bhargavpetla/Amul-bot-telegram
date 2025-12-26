#!/usr/bin/env python3
"""Quick test script to verify pincode 400063 works"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from scraper import AmulAPI
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_pincode(pincode):
    print(f"\n{'='*60}")
    print(f"Testing pincode: {pincode}")
    print('='*60)

    api = AmulAPI()
    result = api.search_pincode(pincode)

    if result:
        print("\n[SUCCESS] Pincode found:")
        print(f"   Pincode: {result['pincode']}")
        print(f"   City: {result['city']}")
        print(f"   State: {result['state']}")
        print(f"   Substore ID: {result['substore_id']}")
        print(f"   Substore Name: {result['substore_name']}")
        print(f"   Canonical Pincode: {result.get('canonical_pincode', 'N/A')}")

        # Test product fetching
        print("\n   Testing product fetch...")
        try:
            products = api.get_protein_products()
            if products:
                print(f"   [OK] Loaded {len(products)} products")
                return True
            else:
                print("   [WARN] No products found")
                return True  # Still pass if pincode was recognized
        except Exception as e:
            print(f"   [ERROR] Product fetch failed: {e}")
            return False
    else:
        print("\n[FAILED] Pincode not found")
        return False

if __name__ == "__main__":
    # Test the problematic pincode - focus on 400063
    test_cases = [
        "400063",  # Mumbai - the one user reported (should use 400001 for products)
    ]

    results = {}
    for pincode in test_cases:
        results[pincode] = test_pincode(pincode)

    print(f"\n{'='*60}")
    print("SUMMARY:")
    print('='*60)
    for pincode, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} - {pincode}")
