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

            # Capture API responses
            async def handle_response(response):
                url = response.url
                try:
                    if '/entity/pincode' in url:
                        data = await response.json()
                        logger.info(f"Pincode API response: {data}")
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

                    elif 'ms.products' in url and 'protein' in url.lower():
                        data = await response.json()
                        items = data.get('data', [])
                        if items:
                            result['products'].extend(items)
                            logger.info(f"Found {len(items)} products")
                except Exception as e:
                    logger.error(f"Response handler error: {e}")
                    pass

            page.on('response', handle_response)

            try:
                # Go to protein page
                await page.goto(f'{config.AMUL_BASE_URL}/en/browse/protein', timeout=30000)
                await asyncio.sleep(2)

                # Find and fill pincode input
                pincode_input = await page.wait_for_selector(
                    'input[type="tel"], input[placeholder*="pincode" i], input[name*="pincode" i]',
                    timeout=10000
                )

                if pincode_input:
                    # Clear and enter pincode
                    await pincode_input.fill('')
                    await pincode_input.type(pincode, delay=100)  # Type slowly for dropdown
                    await asyncio.sleep(2)

                    # Wait for dropdown suggestions and click the matching one
                    try:
                        # Look for any dropdown item containing the pincode (more flexible selectors)
                        dropdown_item = await page.wait_for_selector(
                            f'li:has-text("{pincode}"), [role="option"]:has-text("{pincode}"), div[class*="option"]:has-text("{pincode}")',
                            timeout=5000
                        )
                        if dropdown_item:
                            await dropdown_item.click()
                            await asyncio.sleep(3)
                    except Exception as e:
                        logger.info(f"No dropdown found, trying Enter: {e}")
                        # If no dropdown, just press Enter
                        await page.keyboard.press('Enter')
                        await asyncio.sleep(3)

                    # Wait for products to load
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Browser automation error: {e}")
            finally:
                await browser.close()

        return result

    def search_pincode(self, pincode: str) -> Optional[dict]:
        """Search for pincode and get substore info"""
        if pincode in self._pincode_cache:
            return self._pincode_cache[pincode]

        try:
            logger.info(f"Searching for pincode: {pincode}")
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

                logger.info(f"Pincode search successful: {pincode_data}")
                self._pincode_cache[pincode] = pincode_data
                self.pincode = pincode
                self.substore_id = pincode_data['substore_id']
                self.substore_name = pincode_data['substore_name']

                # Also cache products if we got them
                if result['products']:
                    self._products_cache[pincode] = result['products']
                    logger.info(f"Cached {len(result['products'])} products for pincode {pincode}")

                return pincode_data

            logger.warning(f"No pincode info found for {pincode}")
            return None
        except Exception as e:
            logger.error(f"Pincode search error for {pincode}: {e}", exc_info=True)
            return None

    def get_protein_products(self, substore_id: str = None) -> List[dict]:
        """Fetch all protein products with stock info - always gets fresh data"""
        pincode = self.pincode

        # Always fetch fresh stock data (don't use stale cache)
        try:
            if not pincode:
                pincode = '400001'  # Default Mumbai pincode

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
        """Set pincode"""
        self.pincode = pincode
        self.substore_id = substore_id
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
