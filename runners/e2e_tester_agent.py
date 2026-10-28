import asyncio
from playwright.async_api import async_playwright

async def run_e2e_tests(url: str):
    """
    Runs automated browser tests on the generated project.
    Returns (success: bool, errors: list[str])
    """
    errors = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Catch console errors
            page.on("pageerror", lambda err: errors.append(f"JS Error: {err}"))
            page.on("console", lambda msg: errors.append(f"Console {msg.type}: {msg.text}") if msg.type in ['error'] else None)
            
            # Catch network API failures
            def handle_response(response):
                if "/api/" in response.url and not response.ok:
                    errors.append(f"API Failed: [{response.request.method}] {response.url} returned {response.status}")
            page.on("response", handle_response)
            
            print(f"E2E Tester navigating to {url}")
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=10000)
                if response and not response.ok:
                    errors.append(f"HTTP Error {response.status} when loading {url}")
            except Exception as e:
                errors.append(f"Failed to load {url}: {str(e)}")
                await browser.close()
                return False, errors
                
            # (Removed empty state checking to prevent false positives on valid empty lists)
            # Find links and try to click a few to ensure they work
            links = await page.locator("a").all()
            hrefs = []
            for link in links:
                try:
                    href = await link.get_attribute("href")
                    if href and not href.startswith("http") and not href.startswith("#") and not href.startswith("javascript"):
                        hrefs.append(href)
                except Exception:
                    pass
                    
            # Dedup
            hrefs = list(set(hrefs))
            
            print(f"E2E Tester found links: {hrefs}")
            
            for href in hrefs[:3]: # test up to 3 links to avoid infinite loops
                test_url = f"{url.rstrip('/')}/{href.lstrip('/')}"
                try:
                    print(f"E2E Tester checking {test_url}")
                    resp = await page.goto(test_url, wait_until="load", timeout=5000)
                    if resp and not resp.ok:
                        errors.append(f"Link {href} returned HTTP {resp.status}")
                        
                    # (Removed empty state checking to prevent false positives on linked pages)
                except Exception as e:
                    errors.append(f"Failed to navigate to link {href}: {str(e)}")
                    
            await browser.close()
            
    except Exception as e:
        errors.append(f"Playwright execution failed: {str(e)}")
        
    if errors:
        return False, errors
    return True, []
