import json
import os
from typing import List, Set, Tuple
from config import Job, BASE_URL, CSS_SELECTOR, REQUIRED_KEYS
from dotenv import load_dotenv
import asyncio
import csv

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMExtractionStrategy,
    LLMConfig,
)

load_dotenv()
extraction_strategy = LLMExtractionStrategy(
    LLMConfig(provider="openai/gpt-4o-mini", api_token=os.getenv("OPENAI_API_KEY")),
    schema=Job.model_json_schema(),
    extraction_type="schema",
    instruction=(
        'Extract all the job objects "title", "company", "experience", "location", "job_desc", and "skills" from the given content. '
    ),
    verbose=True,
    input_format="markdown",
)


async def crawl_jobs():
    browser_config = BrowserConfig(headless=False, verbose=True)
    page_number = 0
    jobs = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        while page_number < 10:
            url = f"{BASE_URL}-{page_number}"
            result = await crawler.arun(
                url=url,
                run_config=CrawlerRunConfig(
                    extraction_strategy=extraction_strategy,
                    # cache_mode='bypass',  # Bypass cache for fresh content
                    css_selector=CSS_SELECTOR,  # CSS selector to target job listings
                    verbose=True,  # Enable verbose logging
                    wait_for=CSS_SELECTOR,  # Wait for the content to load
                    scan_full_page=True,  # Scan the full page for content
                    scroll_delay=1,
                )
            )
            if not result.success:
                print(f"Failed to crawl {url}: {result.error}")
                break
            if not result.extracted_content:
                print(f"No content extracted from {url}. Stopping the crawl.")
                break
            extracted_job = json.load(result.extracted_content)
            if not extracted_job:
                print(f"No jobs found on page {page_number}. Stopping the crawl.")
                break
            jobs.append(extracted_job)
            page_number += 1

            await asyncio.sleep(2)
        if jobs:
            field_names = Job.model_fields.keys()
            with open("jobs.csv", "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=field_names)
                writer.writeheader()
                for job in jobs:
                    writer.writerow(job)
        extraction_strategy.show_usage()


async def main():
    await crawl_jobs()

if __name__ == '__main__':
    asyncio.run(main())
