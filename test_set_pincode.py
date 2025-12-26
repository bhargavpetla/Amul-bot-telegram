#!/usr/bin/env python3
"""Test set_pincode after bot restart (empty cache scenario)"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from scraper import AmulAPI
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_set_pincode_with_empty_cache():
    """Simulate what happens when bot restarts and needs to load products"""
    print("\n" + "="*60)
    print("TESTING: set_pincode with empty cache (bot restart scenario)")
    print("="*60)

    # Simulate: User previously set pincode 400063, it's saved in DB
    # Now bot restarts, cache is empty, and we need to load products

    api = AmulAPI()  # New instance, empty cache

    # This is what handlers.py does when showing products
    user_pincode = "400063"
    user_substore_id = "66506000c8f2d6e221b9193a"

    print(f"\n1. Calling set_pincode({user_pincode}, {user_substore_id})")
    api.set_pincode(user_pincode, user_substore_id)

    print(f"\n2. Instance state after set_pincode:")
    print(f"   pincode: {api.pincode}")
    print(f"   canonical_pincode: {api.canonical_pincode}")
    print(f"   substore_id: {api.substore_id}")

    print(f"\n3. Attempting to fetch products...")
    try:
        products = api.get_protein_products()
        if products:
            print(f"   [SUCCESS] Loaded {len(products)} products")
            print(f"\n   Sample products:")
            for i, p in enumerate(products[:3], 1):
                print(f"   {i}. {p['name']} - Rs.{p['price']} - {'In Stock' if p['in_stock'] else 'Out of Stock'}")
            return True
        else:
            print("   [FAILED] No products returned")
            return False
    except Exception as e:
        print(f"   [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_set_pincode_with_empty_cache()

    print("\n" + "="*60)
    if success:
        print("TEST PASSED - Products loaded successfully after bot restart")
    else:
        print("TEST FAILED - Products did not load")
    print("="*60)
