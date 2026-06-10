from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Capture console messages
        page.on("console", lambda msg: print(f"Console {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Page Error: {err}"))
        
        print("Navigating to app...")
        try:
            # The dev server is likely running on 5173
            page.goto('http://localhost:5173/', wait_until='networkidle')
            print("Loaded homepage")
            
            # Take a screenshot
            page.screenshot(path='/Users/wyl/Desktop/Aurora-Design/frontend/screenshot1.png')
            print("Taking screenshot to screenshot1.png")
            
            # Find the knowledge graph tab or page
            # Usually the user is testing it manually, so we just wait for 2 seconds to see if there are errors.
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"Error navigating: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
