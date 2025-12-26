# Bug Fixes - Subscription & Alert Issues

## Issues Found & Fixed

### 1. **Critical Bug: Subscriptions Not Being Saved** ❌
**Location:** [bot/handlers.py](bot/handlers.py#L228)  
**Problem:**  
- When toggling a product subscription, the user is added to the subscription database
- BUT the user's `is_active` flag was never set to 1
- Stock monitor only checks users with `is_active = 1`
- Result: Even though subscription was saved, NO alerts were sent because user was inactive

**Fix Applied:**
```python
if sku in subscribed_skus:
    db.remove_subscription(user_id, sku)
else:
    db.add_subscription(user_id, sku)
    # NEW: Ensure user is marked as active to receive notifications
    db.set_user_active(user_id, True)  # ✅ This was missing!
```

---

### 2. **Product Data Not Fully Cached** ❌
**Location:** [bot/handlers.py](bot/handlers.py#L145-L148)  
**Problem:**  
- When saving products to DB, not all fields were being saved
- Missing price, image_url, and category could cause issues
- Stock monitor couldn't find product information later

**Fix Applied:**
```python
# BEFORE: Only saved id, sku, name, price, image_url
db.upsert_product(p["id"], p["sku"], p["name"], p["price"], p["image_url"])

# AFTER: Now saves all fields with safe defaults
db.upsert_product(
    p["id"], 
    p["sku"], 
    p["name"], 
    p.get("price", 0),        # ✅ Safe default
    p.get("image_url", ""),   # ✅ Safe default
    p.get("category", "")     # ✅ Category field
)
```

---

### 3. **Stock Monitor Missing Error Handling** ❌
**Location:** [scheduler/stock_monitor.py](scheduler/stock_monitor.py#L55)  
**Problem:**  
- If a product wasn't found in the latest stock data, it was silently skipped
- No logging made debugging impossible
- Empty subscriptions list wasn't checked, could cause unnecessary API calls

**Fix Applied:**
```python
# BEFORE: Silently skipped if product not found
for sub in subscriptions:
    sku = sub["product_sku"]
    product = stock_by_sku.get(sku)
    if not product:
        continue  # ❌ Silent failure

# AFTER: Check for empty subscriptions + add logging
if not subscriptions:
    continue  # Skip user if no subscriptions

for sub in subscriptions:
    sku = sub["product_sku"]
    product = stock_by_sku.get(sku)
    if not product:
        print(f"Product {sku} not found in latest stock for substore {substore_id}")  # ✅ Debug info
        continue
```

---

## How the Subscription Flow Should Now Work

```
1. User runs /products
   └─ Products fetched from Amul API
   └─ Products saved to database (all fields)
   
2. User clicks product button
   └─ Subscription added to database
   └─ User is_active = 1  ✅ (NOW FIXED)
   
3. Background scheduler runs every 5 minutes
   └─ Gets all active users (is_active = 1)  ✅ (User now found)
   └─ Gets user subscriptions from database
   └─ Fetches latest stock from Amul API
   └─ Compares with cache
   └─ SENDS ALERTS when stock changes  ✅ (NOW WORKING)
```

---

## Verification Checklist

After these fixes, verify:
- [ ] Subscribe to a product → Check database that `is_active = 1`
- [ ] Product should already be in stock → Wait for next stock check (5 min)
- [ ] Alert notification should arrive
- [ ] Check logs show: "Notification sent to {user_id} for {product_sku}"

---

## Database Check Command

If alerts still not working, run this SQL to debug:

```sql
-- Check if user is marked as active
SELECT user_id, is_active FROM users WHERE user_id = YOUR_USER_ID;

-- Should return: is_active = 1

-- Check subscriptions
SELECT * FROM subscriptions WHERE user_id = YOUR_USER_ID AND is_active = 1;

-- Should list your subscribed products
```

