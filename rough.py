import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from main import extraction_strategy
from config import BASE_URL, CSS_SELECTOR

async def main():
    browser_config = BrowserConfig(headless=False,verbose=True)  # Default browser configuration
    run_config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        #cache_mode='bypass',  # Bypass cache for fresh content
        css_selector=CSS_SELECTOR,  # CSS selector to target job listings
        verbose=True,  # Enable verbose logging
        wait_for=CSS_SELECTOR,  # Wait for the content to load
        scan_full_page=True,  # Scan the full page for content
          # Delay between scrolls
        
    )   # Default crawl run configuration

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://www.naukri.com/it-jobs",
            config=run_config
        )
        print(result.markdown)  # Print clean markdown content

if __name__ == "__main__":
    asyncio.run(main())
