import json
import logging
import asyncio
from typing import Optional, List
from playwright.async_api import async_playwright
import config

logger = logging.getLogger(__name__)


# Substore ID mapping from open-source project
SUBSTORE_IDS = {
    'goa': '66506005147d6c73c1110115',
    'telangana': '66506004aa64743ceefbed25',
    'pune-br': '66506004a7cddee1b8adb014',
    'solapur-br': '66506004145c16635e6cc914',
    'nashik-br': '66506002c8f2d6e221b9193a88',
    'aurangabad-br': '66506002aa64743ceefbecf1',
    'chhattisgarh': '66506002998183e1b1935f41',
    'mumbai-br': '66506000c8f2d6e221b9193a',
    'dadra-and-nagar-haveli': '6650600062e3d963520d0bc3',
    'west-bengal': '6650600024e61363e088c526',
    'odisha': '66505ffeaf6a3c7411d2f62c',
    'sikkim': '66505ffe91ab653d60a3df2d',
    'tripura': '66505ffe78117873bb53b6ad',
    'mizoram': '66505ffd998183e1b1935e21',
    'meghalaya': '66505ffd672747740fb389c7',
    'nagaland': '66505ffd24e61363e088c4a5',
    'manipur': '66505ffbf40e263cf5588098',
    'jharkhand': '66505ffb998183e1b1935dee',
    'assam': '66505ffb6510ee3d5903fef8',
    'bihar': '66505ff9af6a3c7411d2f55f',
    'arunachal-pradesh': '66505ff978117873bb53b643',
    'uttar-pradesh-e': '66505ff924e61363e088c414',
    'up-ncr': '66505ff8c8f2d6e221b9180c',
    'uttrakhand': '66505ff8a7cddee1b8adae9d',
    'rajasthan': '66505ff824e61363e088c3dd',
    'jandk': '66505ff6f40e263cf5587fb5',
    'madhya-pradesh': '66505ff6d9346de216752cd7',
    'ladakh': '66505ff6145c16635e6cc7c1',
    'haryana': '66505ff5af6a3c7411d2f4b2',
    'tamil-nadu-1': '66505ff578117873bb53b56a',
    'delhi': '66505ff5145c16635e6cc74d',
    'punjab': '66505ff3998183e1b1935d0e',
    'andhra-pradesh': '66505ff378117873bb53b542',
    'pondicherry': '66505ff312a50963f24870e8',
    'kerala': '66505ff2998183e1b1935ccd',
    'himachal-pradesh': '66505ff26510ee3d5903fda9',
    'chandigarh': '66505ff1672747740fb388ec',
    'karnataka': '66505ff0998183e1b1935c75',
    'gujarat': '66505ff06510ee3d5903fd42',
    'daman-and-diu': '66505ff024e61363e088c306',
}


class AmulAPI:
    """Amul Shop API Client using Playwright browser automation"""

    def __init__(self):
        self.substore_id = None
        self.substore_name = None
        self.pincode = None
        self.canonical_pincode = None  # Pincode to use for fetching products
        self._products_cache = {}
        self._pincode_cache = {}

    def _get_substore_id(self, alias: str) -> Optional[str]:
        """Get actual MongoDB _id from substore alias"""
        return SUBSTORE_IDS.get(alias)

    def _run_async(self, coro):
        """Run async code in sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, use nest_asyncio or create new loop
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(coro)
        except RuntimeError:
            pass

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    async def _enter_pincode_and_fetch(self, pincode: str) -> dict:
        """Enter pincode in browser and fetch products"""
        result = {
            'pincode_info': None,
            'products': []
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()

            # Track all network requests for debugging
            all_requests = []
            all_responses = []

            async def handle_request(request):
                url = request.url
                if 'pincode' in url.lower() or 'entity' in url.lower():
                    all_requests.append(url)
                    logger.info(f"Request: {url}")

            async def handle_response(response):
                url = response.url
                all_responses.append(url)

                try:
                    # Log all API calls for debugging
                    if '/entity/pincode' in url or 'pincode' in url.lower():
                        logger.info(f"Pincode-related response URL: {url}")
                        try:
                            data = await response.json()
                            logger.info(f"Pincode API response data: {data}")
                            records = data.get('records', [])
                            # Try exact match first
                            for rec in records:
                                if str(rec.get('pincode')) == str(pincode):
                                    result['pincode_info'] = rec
                                    logger.info(f"Found exact pincode match: {rec}")
                                    break
                            # If no exact match, use first record (partial match)
                            if not result['pincode_info'] and records:
                                result['pincode_info'] = records[0]
                                logger.info(f"Using first pincode record: {records[0]}")
                        except:
                            text = await response.text()
                            logger.info(f"Pincode response (not JSON): {text[:500]}")

                    elif 'ms.products' in url and 'protein' in url.lower():
                        data = await response.json()
                        items = data.get('data', [])
                        if items:
                            result['products'].extend(items)
                            logger.info(f"Found {len(items)} products")
                except Exception as e:
                    logger.error(f"Response handler error for {url}: {e}")
                    pass

            page.on('request', handle_request)
            page.on('response', handle_response)

            try:
                # Go to protein page
                logger.info(f"Navigating to {config.AMUL_BASE_URL}/en/browse/protein")
                await page.goto(f'{config.AMUL_BASE_URL}/en/browse/protein', timeout=30000)
                await asyncio.sleep(3)

                # Find and fill pincode input - try multiple selectors
                pincode_input = None
                selectors = [
                    'input[type="tel"]',
                    'input[placeholder*="pincode" i]',
                    'input[name*="pincode" i]',
                    'input[id*="pincode" i]',
                    'input[class*="pincode" i]'
                ]

                for selector in selectors:
                    try:
                        pincode_input = await page.wait_for_selector(selector, timeout=3000)
                        if pincode_input:
                            logger.info(f"Found pincode input with selector: {selector}")
                            break
                    except:
                        continue

                if pincode_input:
                    # Clear and enter pincode
                    logger.info(f"Entering pincode: {pincode}")
                    await pincode_input.click()
                    await pincode_input.fill('')
                    await asyncio.sleep(0.5)
                    await pincode_input.type(pincode, delay=100)  # Type slowly for dropdown
                    logger.info(f"Typed pincode, waiting for dropdown...")
                    await asyncio.sleep(3)

                    # Wait for dropdown suggestions and click the matching one
                    dropdown_found = False
                    try:
                        # Look for any dropdown item containing the pincode (more flexible selectors)
                        dropdown_selectors = [
                            f'li:has-text("{pincode}")',
                            f'[role="option"]:has-text("{pincode}")',
                            f'div[class*="option"]:has-text("{pincode}")',
                            f'div[class*="dropdown"] >> text={pincode}',
                            f'.dropdown-item:has-text("{pincode}")'
                        ]

                        for ds in dropdown_selectors:
                            try:
                                dropdown_item = await page.wait_for_selector(ds, timeout=2000)
                                if dropdown_item:
                                    logger.info(f"Found dropdown with selector: {ds}")
                                    await dropdown_item.click()
                                    dropdown_found = True
                                    await asyncio.sleep(3)
                                    break
                            except:
                                continue

                    except Exception as e:
                        logger.info(f"Dropdown search error: {e}")

                    if not dropdown_found:
                        logger.info("No dropdown found, pressing Enter")
                        await page.keyboard.press('Enter')
                        await asyncio.sleep(3)

                    # Wait for products to load
                    logger.info("Waiting for products to load...")
                    await asyncio.sleep(5)

                    # Log final state
                    logger.info(f"Captured {len(all_requests)} requests, {len(all_responses)} responses")
                    logger.info(f"Pincode info found: {result['pincode_info'] is not None}")
                    logger.info(f"Products found: {len(result['products'])}")
                else:
                    logger.error("Could not find pincode input field!")

            except Exception as e:
                logger.error(f"Browser automation error: {e}")
            finally:
                await browser.close()

        return result

    def search_pincode(self, pincode: str) -> Optional[dict]:
        """Search for pincode and get substore info"""
        if pincode in self._pincode_cache:
            logger.info(f"Using cached pincode data for {pincode}")
            return self._pincode_cache[pincode]

        try:
            logger.info(f"Searching for pincode: {pincode}")

            # STRATEGY: Try fallback FIRST for known regions (fast & reliable)
            # Only use slow Playwright scraper if fallback doesn't match
            fallback_data = self._get_fallback_substore(pincode)
            if fallback_data:
                logger.info(f"✓ Pincode {pincode} matched fallback region: {fallback_data['city']}, {fallback_data['state']}")
                self._pincode_cache[pincode] = fallback_data
                self.pincode = pincode
                self.substore_id = fallback_data['substore_id']
                self.substore_name = fallback_data['substore_name']
                # Use canonical pincode for product fetching (e.g., 400001 instead of 400063)
                self.canonical_pincode = fallback_data.get('canonical_pincode', pincode)
                logger.info(f"Using canonical pincode {self.canonical_pincode} for product fetching")
                return fallback_data

            # If fallback didn't match, try Playwright scraper (slower)
            logger.info(f"No fallback match, trying browser automation for {pincode}...")
            result = self._run_async(self._enter_pincode_and_fetch(pincode))

            if result['pincode_info']:
                info = result['pincode_info']
                substore_alias = info.get('substore', '')

                pincode_data = {
                    "pincode": str(info.get("pincode", pincode)),
                    "substore_id": self._get_substore_id(substore_alias) or substore_alias,
                    "substore_name": substore_alias,
                    "city": info.get("city", ""),
                    "state": info.get("state", "")
                }

                logger.info(f"✓ Playwright found pincode: {pincode_data}")
                self._pincode_cache[pincode] = pincode_data
                self.pincode = pincode
                self.substore_id = pincode_data['substore_id']
                self.substore_name = pincode_data['substore_name']
                self.canonical_pincode = pincode  # Use actual pincode from API

                # Also cache products if we got them
                if result['products']:
                    self._products_cache[pincode] = result['products']
                    logger.info(f"Cached {len(result['products'])} products for pincode {pincode}")

                return pincode_data

            logger.warning(f"✗ Pincode {pincode} not found via API or fallback")
            return None

        except Exception as e:
            logger.error(f"Pincode search error for {pincode}: {e}", exc_info=True)
            return None

    def _get_fallback_substore(self, pincode: str) -> Optional[dict]:
        """Get fallback substore based on pincode range - covers major Indian cities"""
        try:
            pin_num = int(pincode)

            # Maharashtra
            if 400001 <= pin_num <= 400104:  # Mumbai
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('mumbai-br'),
                    "substore_name": "mumbai-br",
                    "city": "Mumbai",
                    "state": "Maharashtra",
                    "canonical_pincode": "400001"  # Use this for fetching products
                }
            elif 411001 <= pin_num <= 411060:  # Pune
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('pune-br'),
                    "substore_name": "pune-br",
                    "city": "Pune",
                    "state": "Maharashtra",
                    "canonical_pincode": "411001"
                }
            elif 413001 <= pin_num <= 413736:  # Solapur
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('solapur-br'),
                    "substore_name": "solapur-br",
                    "city": "Solapur",
                    "state": "Maharashtra",
                    "canonical_pincode": "413001"
                }
            elif 422001 <= pin_num <= 422605:  # Nashik
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('nashik-br'),
                    "substore_name": "nashik-br",
                    "city": "Nashik",
                    "state": "Maharashtra",
                    "canonical_pincode": "422001"
                }
            elif 431001 <= pin_num <= 431542:  # Aurangabad
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('aurangabad-br'),
                    "substore_name": "aurangabad-br",
                    "city": "Aurangabad",
                    "state": "Maharashtra",
                    "canonical_pincode": "431001"
                }

            # Delhi NCR
            elif 110001 <= pin_num <= 110096:  # Delhi
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('delhi'),
                    "substore_name": "delhi",
                    "city": "Delhi",
                    "state": "Delhi",
                    "canonical_pincode": "110001"
                }
            elif 201001 <= pin_num <= 203207 or 244001 <= pin_num <= 247778:  # UP NCR (Noida, Ghaziabad, etc.)
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('up-ncr'),
                    "substore_name": "up-ncr",
                    "city": "NCR",
                    "state": "Uttar Pradesh",
                    "canonical_pincode": "201001"
                }
            elif 121001 <= pin_num <= 122505:  # Haryana (Gurgaon, Faridabad)
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('haryana'),
                    "substore_name": "haryana",
                    "city": "Gurgaon/Faridabad",
                    "state": "Haryana",
                    "canonical_pincode": "122001"
                }

            # Karnataka
            elif 560001 <= pin_num <= 560110:  # Bangalore
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('karnataka'),
                    "substore_name": "karnataka",
                    "city": "Bangalore",
                    "state": "Karnataka",
                    "canonical_pincode": "560001"
                }

            # Tamil Nadu
            elif 600001 <= pin_num <= 600126:  # Chennai
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('tamil-nadu-1'),
                    "substore_name": "tamil-nadu-1",
                    "city": "Chennai",
                    "state": "Tamil Nadu",
                    "canonical_pincode": "600001"
                }

            # Telangana
            elif 500001 <= pin_num <= 500097:  # Hyderabad
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('telangana'),
                    "substore_name": "telangana",
                    "city": "Hyderabad",
                    "state": "Telangana",
                    "canonical_pincode": "500001"
                }

            # Gujarat
            elif 380001 <= pin_num <= 382481:  # Ahmedabad
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('gujarat'),
                    "substore_name": "gujarat",
                    "city": "Ahmedabad",
                    "state": "Gujarat",
                    "canonical_pincode": "380001"
                }

            # West Bengal
            elif 700001 <= pin_num <= 700156:  # Kolkata
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('west-bengal'),
                    "substore_name": "west-bengal",
                    "city": "Kolkata",
                    "state": "West Bengal",
                    "canonical_pincode": "700001"
                }

            # Rajasthan
            elif 302001 <= pin_num <= 303807:  # Jaipur
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('rajasthan'),
                    "substore_name": "rajasthan",
                    "city": "Jaipur",
                    "state": "Rajasthan",
                    "canonical_pincode": "302001"
                }

            # Kerala
            elif 682001 <= pin_num <= 695615:  # Kerala (Kochi, Trivandrum)
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('kerala'),
                    "substore_name": "kerala",
                    "city": "Kerala",
                    "state": "Kerala",
                    "canonical_pincode": "695001"
                }

            # Goa
            elif 403001 <= pin_num <= 403806:  # Goa
                return {
                    "pincode": pincode,
                    "substore_id": self._get_substore_id('goa'),
                    "substore_name": "goa",
                    "city": "Goa",
                    "state": "Goa",
                    "canonical_pincode": "403001"
                }

        except Exception as e:
            logger.debug(f"Fallback check failed for {pincode}: {e}")

        return None

    def get_protein_products(self, substore_id: str = None) -> List[dict]:
        """Fetch all protein products with stock info - always gets fresh data"""
        # Use canonical pincode if available (e.g., 400001 instead of 400063)
        # This ensures Amul website recognizes the pincode
        pincode = self.canonical_pincode or self.pincode

        # Always fetch fresh stock data (don't use stale cache)
        try:
            if not pincode:
                pincode = '400001'  # Default Mumbai pincode

            logger.info(f"Fetching products using pincode: {pincode}")
            result = self._run_async(self._enter_pincode_and_fetch(pincode))
            raw_products = result.get('products', [])

            if not raw_products:
                logger.warning(f"No products returned for pincode {pincode}")
                return []

            # Update cache with fresh data
            self._products_cache[pincode] = raw_products
        except Exception as e:
            logger.error(f"Get products error: {e}")
            # Don't use stale cache - return empty list to force retry
            return []

        # Process products
        products = []
        seen_skus = set()

        for item in raw_products:
            sku = item.get('sku')
            if sku and sku not in seen_skus:
                seen_skus.add(sku)
                # CRITICAL: Use 'available' field for pincode-specific stock, not 'inventory_quantity'
                # 'available' = stock available at the user's pincode/location
                # 'inventory_quantity' = total warehouse stock (not location-specific)
                available_qty = item.get("available", 0)

                product = {
                    "id": item.get("_id"),
                    "name": item.get("name"),
                    "sku": sku,
                    "alias": item.get("alias"),
                    "price": item.get("price", 0),
                    "compare_price": item.get("compare_price", 0),
                    "quantity": available_qty,  # Use pincode-specific availability
                    "allow_out_of_stock": item.get("inventory_allow_out_of_stock", False),
                    "in_stock": available_qty > 0,  # Based on pincode-specific stock
                    "image_url": self._get_image_url(item.get("images", [])),
                    "product_url": f"{config.AMUL_BASE_URL}/en/product/{item.get('alias', '')}"
                }
                products.append(product)

        return products

    def _get_image_url(self, images: list) -> str:
        """Extract first image URL from images array"""
        if images and len(images) > 0:
            img = images[0]
            if isinstance(img, dict):
                return img.get("image", "") or img.get("url", "")
            return str(img)
        return ""

    def init_session(self) -> bool:
        """Initialize - returns True (browser handles sessions)"""
        return True

    def set_pincode(self, pincode: str, substore_id: str) -> bool:
        """Set pincode and determine canonical pincode for product fetching"""
        self.pincode = pincode
        self.substore_id = substore_id

        # Try to get canonical pincode from cache first
        if pincode in self._pincode_cache:
            cached_data = self._pincode_cache[pincode]
            self.canonical_pincode = cached_data.get('canonical_pincode', pincode)
            self.substore_name = cached_data.get('substore_name', '')
            logger.info(f"Set pincode {pincode} (from cache), using canonical {self.canonical_pincode}")
        else:
            # Cache miss - check fallback mapping to determine canonical pincode
            fallback_data = self._get_fallback_substore(pincode)
            if fallback_data:
                self.canonical_pincode = fallback_data.get('canonical_pincode', pincode)
                self.substore_name = fallback_data.get('substore_name', '')
                logger.info(f"Set pincode {pincode} (from fallback), using canonical {self.canonical_pincode}")
            else:
                # Not in fallback mapping, use pincode as-is
                self.canonical_pincode = pincode
                logger.info(f"Set pincode {pincode}, no fallback found, using as-is")

        return True

    def get_product_stock(self, sku: str, substore_id: str = None) -> Optional[dict]:
        """Get stock info for a specific product"""
        products = self.get_protein_products(substore_id)
        for product in products:
            if product.get("sku") == sku:
                return {
                    "sku": product["sku"],
                    "name": product["name"],
                    "quantity": product["quantity"],
                    "in_stock": product["in_stock"],
                    "price": product["price"]
                }
        return None

    def get_in_stock_products(self, substore_id: str = None) -> List[dict]:
        """Get only products that are in stock"""
        products = self.get_protein_products(substore_id)
        return [p for p in products if p.get("in_stock", False)]

    def check_stock_for_skus(self, skus: list, substore_id: str = None) -> dict:
        """Check stock for multiple SKUs"""
        products = self.get_protein_products(substore_id)
        result = {}
        for product in products:
            if product.get("sku") in skus:
                result[product["sku"]] = {
                    "name": product["name"],
                    "quantity": product["quantity"],
                    "in_stock": product["in_stock"],
                    "price": product["price"],
                    "product_url": product["product_url"]
                }
        return result

    def clear_cache(self):
        """Clear cached data"""
        self._products_cache.clear()
        self._pincode_cache.clear()
