import asyncio
import csv
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMConfig,
    LLMExtractionStrategy,
)
from bs4 import BeautifulSoup

from config import (
    CSS_SELECTOR_indeed,
    CSS_SELECTOR_naukri,
    CSS_SELECTOR_indeed_dir_page,
    CSS_SELECTOR_naukri_dir_page,
    CSS_SELECTOR_linkedin,
    CSS_SELECTOR_linkedin_dir_page,
)
import parser_functions as pf

company, location, profession, website_name, job_number = pf.user_params(
    website_name="linkedin",
    #profession=,
    job_number=5,
    company="accenture",
    location="mumbai",
)
BASE_URL, input_url = pf.change_base_url(company, location, profession, website_name)


async def crawl_jobs():
    browser_config = BrowserConfig(headless=False, verbose=True)
    page_number = 1
    jobs = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        jobs_links = []
        while True:

            if website_name == "naukri":
                page_url = f"{BASE_URL}-{page_number}"
                css_selector = CSS_SELECTOR_naukri
                css_selector_dir_page = CSS_SELECTOR_naukri_dir_page
            elif website_name == "linkedin":

                page_url = f"{BASE_URL}&start={(page_number - 1) * 25}"
                css_selector = CSS_SELECTOR_linkedin
                css_selector_dir_page = CSS_SELECTOR_linkedin_dir_page
            else:
                page_url = f"{BASE_URL}&start={(page_number - 1) * 10}"
                css_selector = CSS_SELECTOR_indeed
                css_selector_dir_page = CSS_SELECTOR_indeed_dir_page

            result = await crawler.arun(
                url=page_url,
                config=CrawlerRunConfig(
                    exclude_external_links=True,
                    word_count_threshold=20,
                    js_code="window.scrollTo(0, document.body.scrollHeight);",
                    session_id="job_session",
                    css_selector=css_selector,
                    wait_for=css_selector,
                ),
            )

            soup = BeautifulSoup(result.html, "html.parser")
            cards = soup.select(css_selector)

            for card in cards:
                if website_name == "naukri":
                    a = card.select_one("a.title")
                elif website_name == "linkedin":
                    a = card.select_one("a.base-card__full-link")
                else:  
                    a = card.select_one("h2.jobTitle a")

                if not a or not a.get("href"):
                    continue

                link = a["href"]
                if website_name == "indeed":
                    prefix = "https://www.indeed.com"
                elif website_name == "naukri":
                    prefix = "https://www.naukri.com"
                else:  
                    prefix = input_url

                full = link if link.startswith("https") else prefix + link
                jobs_links.append(full)

                if len(jobs_links) >= job_number:
                    break

            for job_link in jobs_links:
                result_dir_page = await crawler.arun(
                    url=job_link,
                    config=CrawlerRunConfig(
                        exclude_external_links=True,
                        word_count_threshold=20,
                        js_code="window.scrollTo(0, document.body.scrollHeight);",
                        session_id="job_session",
                        css_selector=css_selector_dir_page,
                        wait_for=css_selector_dir_page,
                    ),
                )
                await asyncio.sleep(2)

                if website_name == "indeed":
                    pf.get_parsed_jobs_indeed(result_dir_page, jobs)
                elif website_name == "naukri":
                    pf.get_parsed_jobs_naukri(result_dir_page, jobs)
                else:
                    pf.get_parsed_jobs_linkedin(result_dir_page, jobs)

            if len(jobs) >= job_number:
                break

            page_number += 1
            await asyncio.sleep(5)

    print(jobs)
    pf.convert_to_csv(jobs, "jobs.csv")


async def main():
    await crawl_jobs()


if __name__ == "__main__":
    asyncio.run(main())
