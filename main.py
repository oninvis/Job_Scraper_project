# -------------------------------------------------------------------------------------------------------------------------
# Necessary imports and configurations for the job crawler
# -------------------------------------------------------------------------------------------------------------------------
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


# -------------------------------------------------------------------------------------------------------------------------
async def crawl_jobs():
    browser_config = BrowserConfig(headless=False, verbose=True)
    page_number = 1
    jobs = []
    # -------------------------------------------------------------------------------------------------------------------------
    # LLM extraction strategy configuration
    # -------------------------------------------------------------------------------------------------------------------------
    llm_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="openai/gpt-4o-mini", api_token=os.getenv("OPENAI_API_KEY")
        ),
        schema=Job.model_json_schema(),
        extraction_type="schema",
        instruction=(
            'Extract all the job objects "title", "company", "experience", "location", "job-description", and "skills" from the given content if found and if objects "title", "company", "experience", "location", "job-description" are not found then return " " and if skills are not found then return empty list.  '
        ),
        verbose=True,
        input_format="html",
    )
    # -------------------------------------------------------------------------------------------------------------------------
    # Crawler configuration and execution
    # -------------------------------------------------------------------------------------------------------------------------
    async with AsyncWebCrawler(config=browser_config) as crawler:
        while True:
            if page_number > 4:  # Limit to 10 pages
                print("Reached the maximum number of pages to crawl.")
                break
            url = f"{BASE_URL}-{page_number}"
            result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(
                    exclude_external_links=True,
                    word_count_threshold=20,
                    extraction_strategy=llm_strategy,
                    js_code="window.scrollTo(0, document.body.scrollHeight);",
                    session_id="naukri_session",
                    css_selector=CSS_SELECTOR,
                    wait_for=CSS_SELECTOR,
                ),
            )

            if not result.success:
                print(f"Failed to crawl {url}: {result.error}")
                continue

            print(result.extracted_content)

            if not result.extracted_content:
                print(f"No content extracted from {url}. Stopping the crawl.")
                page_number += 1
                continue

            extracted_job = json.loads(result.extracted_content)
            
            if not extracted_job:
                print(f"No jobs found on page {page_number}. Stopping the crawl.")
                page_number += 1
                continue
            jobs.append(extracted_job)
            page_number += 1

            await asyncio.sleep(2)
        """if jobs:
            field_names = Job.model_fields.keys()
            with open("jobs.csv", "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=field_names)
                writer.writeheader()
                for job in jobs:
                    writer.writerow(job)"""

        llm_strategy.show_usage()
        print(jobs)


# -------------------------------------------------------------------------------------------------------------------------


async def main():
    await crawl_jobs()


if __name__ == "__main__":
    asyncio.run(main())
