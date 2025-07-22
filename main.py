# -------------------------------------------------------------------------------------------------------------------------
# Necessary imports and configurations for the job crawler
# -------------------------------------------------------------------------------------------------------------------------
import json
import os
from typing import List, Set, Tuple
from config import Job, CSS_SELECTOR, REQUIRED_KEYS
from dotenv import load_dotenv
import asyncio
import csv
import re
from bs4 import BeautifulSoup

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMExtractionStrategy,
    LLMConfig,
)

load_dotenv()
BASE_URL = "https://www.naukri.com/"

# -----------------------------------------------------------------------------
# Helper for safe .get_text()
# -----------------------------------------------------------------------------
def text_or(el, default=""):
    return el.get_text(strip=True) if el else default


def change_base_url(company: str = None, location: str = None, profession: str = None):
    global BASE_URL
    if company:
        BASE_URL = f"{BASE_URL}{company}-jobs"
    elif location:
        BASE_URL = f"{BASE_URL}jobs-in-{location}"
    elif profession:
        BASE_URL = f"{BASE_URL}{profession}-jobs"
    elif company and location:
        BASE_URL = f"{BASE_URL}{company}-jobs-in-{location}"
    elif company and profession:
        BASE_URL = f"{BASE_URL}{company}-{profession}-jobs"
    elif location and profession:
        BASE_URL = f"{BASE_URL}jobs-in-{location}-{profession}"
    elif company and location and profession:
        BASE_URL = f"{BASE_URL}{profession}-{company}-jobs-in-{location}"
    return BASE_URL


change_base_url(profession="datascience")  # Example usage, change as needed


# -------------------------------------------------------------------------------------------------------------------------
async def crawl_jobs():
    browser_config = BrowserConfig(headless=True, verbose=True)
    page_number = 1
    jobs = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        while True:
            if page_number > 2:  # Limit to 2 pages for testing
                print("Reached the maximum number of pages to crawl.")
                break

            url = f"{BASE_URL}-{page_number}"
            result = await crawler.arun(
                url=url,
                config=CrawlerRunConfig(
                    exclude_external_links=True,
                    word_count_threshold=20,
                    js_code="window.scrollTo(0, document.body.scrollHeight);",
                    session_id="naukri_session",
                    css_selector=CSS_SELECTOR,
                    wait_for=CSS_SELECTOR,
                ),
            )

            if not result.success:
                print(f"Failed to crawl {url}: {result.error}")
                page_number += 1
                continue

            soup = BeautifulSoup(result.html, "html.parser")

            for w in soup.select('.srp-jobtuple-wrapper'):
                # title (skip if missing)
                title_el = w.select_one('.title') or w.select_one('a[subTitle]')
                title = text_or(title_el)
                if not title:
                    continue  # skip cards with no title

                # company
                company_el = w.select_one('a.comp-name') or w.select_one('a[subTitle]')
                company = text_or(company_el)

                # experience
                exp_el = w.select_one('.expwdth') or w.select_one('[class*=srp-experience] .expwdth')
                experience = text_or(exp_el)

                # location
                loc_el = w.select_one('.locWdth') or w.select_one('[class*=srp-location] .locWdth')
                location = text_or(loc_el)

                # description
                desc_el = w.select_one('.job-desc')
                description = text_or(desc_el)

                # posted date
                post_el = w.select_one('.job-post-day')
                posted = text_or(post_el)

                # skills
                skills = [li.get_text(strip=True) for li in w.select('li[class*=tag-li]')]

                jobs.append({
                    "title":       title,
                    "company":     company,
                    "experience":  experience,
                    "location":    location,
                    "description": description,
                    "posted":      posted,
                    "skills":      skills
                })

            page_number += 1

    if jobs:
        # Dynamically infer the exact columns from the first job dict:
        field_names = list(jobs[0].keys())

        with open("jobs.csv", "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(jobs)

        print(f"Extracted {len(jobs)} jobs and saved to jobs.csv")

    print(jobs)


async def main():
    await crawl_jobs()


if __name__ == "__main__":
    asyncio.run(main())
