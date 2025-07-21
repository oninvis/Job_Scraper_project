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
    browser_config = BrowserConfig(headless=False, verbose=True)
    page_number = 1
    jobs = []
    # -------------------------------------------------------------------------------------------------------------------------
    # LLM extraction strategy configuration
    # -------------------------------------------------------------------------------------------------------------------------

    """llm_strategy = LLMExtractionStrategy(
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
    )"""
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
                    # extraction_strategy=llm_strategy,
                    js_code="window.scrollTo(0, document.body.scrollHeight);",
                    session_id="naukri_session",
                    css_selector=CSS_SELECTOR,
                    wait_for=CSS_SELECTOR,
                ),
            )

            if not result.success:
                print(f"Failed to crawl {url}: {result.error}")
                continue

            html_extractable = (
                result.fit_html
            )  # result in extratable friendly html format
            soup = BeautifulSoup(html_extractable, "html.parser")
            for wrapper in soup.find_all("div", class_="srp-jobtuple-wrapper"):
                # Title (skip entirely if missing)
                title_tag = wrapper.find("a", class_="title")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                # Company
                # comp_tag = wrapper.find('a', class_='comp-name mw-25')
                comp_tag = wrapper.find("a", class_=re.compile(r"comp"))
                company = comp_tag.get_text(strip=True) if comp_tag else ""
                print(title_tag)
                print(comp_tag)

                # Experience
                exp_tag = wrapper.find("span", class_=re.compile(r"\bsrp-experience\b"))
                experience = exp_tag.get_text(strip=True) if exp_tag else ""
                print(exp_tag)

                # Location
                loc_tag = wrapper.find(
                    "span", class_=re.compile(r"\bsrp-location\b")
                )  # ni-job-tuple-icon ni-job-tuple-icon-srp-location loc
                location = loc_tag.get_text(strip=True) if loc_tag else ""
                print(loc_tag)

                # Description
                desc_tag = wrapper.find("span", class_=re.compile(r"\bjob-desc\b"))
                description = desc_tag.get_text(strip=True) if desc_tag else ""

                # Skills (might be an empty list)
                skills = [
                    li.get_text(strip=True)
                    for li in wrapper.find_all("li", class_=re.compile(r"\btag-li\b"))
                ]

                jobs.append(
                    {
                        "title": title,
                        "company": company,
                        "experience": experience,
                        "location": location,
                        "job_desc": description,
                        "skills": skills,
                    }
                )

            page_number = page_number + 1
            await asyncio.sleep(1000)
        if jobs:
            field_names = Job.model_fields.keys()
            with open("jobs.csv", "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=field_names)
                writer.writeheader()
                writer.writerows(jobs)
            print(f"Extracted {len(jobs)} jobs and saved to jobs.csv")

        print(jobs)


# -------------------------------------------------------------------------------------------------------------------------


async def main():
    await crawl_jobs()


if __name__ == "__main__":
    asyncio.run(main())
