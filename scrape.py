import urllib.parse
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def search_depop(query: str):
    # URL-encode the user's query (e.g., "vintage leather jacket" -> "vintage+leather+jacket")
    encoded_query = urllib.parse.quote_plus(query)
    search_url = f"https://www.depop.com/search/?q={encoded_query}"
    
    print(f"Launching Chromium and navigating to: {search_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
           #Set a standard User-Agent to appear more like a regular user
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # wait_until="domcontentloaded" ensures the initial HTML is loaded before moving on
        page.goto(search_url, wait_until="domcontentloaded")

        # wait for the product grid to dynamically render via JavaScript
        try:
            page.wait_for_selector('ol[class*="styles_productGrid__"]', timeout=10000)
            print("Product grid successfully loaded!")
        except Exception as e:
            print("Could not find the product grid within the timeout period.")
            browser.close()
            return None

        #grab fully rendered html content
        html_content = page.content()
        browser.close()
        return html_content

def extract_product_links(html_content: str):
    print("Parsing HTML")
    soup = BeautifulSoup(html_content, 'html.parser')

    # finds any <ol> whose class attribute contains "styles_productGrid__"
    product_grid = soup.find('ol', class_=lambda c: c and 'styles_productGrid__' in c)

    if not product_grid:
        print("Error: Could not locate the product grid in the HTML.")
        return []

    # Find all anchor (<a>) tags inside the grid
    # depop wraps product cards in link tags that lead to the item page
    product_cards = product_grid.find_all('a', href=True)

    product_links = []
    base_url = "https://www.depop.com"

    # Extract and normalize the URLs
    for card in product_cards:
        href = card['href']
        
        # only want actual product listing links 
        # structure is https://www.depop.com/products/[username]-[item-name]-[id]/
        if "/products/" in href:
            # If the link is relative (e.g., "/products/item-123/"), join it with the base domain
            full_url = urllib.parse.urljoin(base_url, href)
            
            # avoid duplicate links if a card contains multiple clickable elements pointing to the same item
            if full_url not in product_links:
                product_links.append(full_url)

    print(f"Successfully extracted {len(product_links)} unique product links!")
    return product_links

if __name__ == "__main__":
    user_query = input("Enter your Depop search query: ")
    html_data = search_depop(user_query)
    
    # Run Step 2
    if html_data:
        links = extract_product_links(html_data)
        
        # Print the first 5 links as a preview
        print("\n--- Preview of Scraped Links ---")
        for i, link in enumerate(links[:5], 1):
            print(f"{i}. {link}")