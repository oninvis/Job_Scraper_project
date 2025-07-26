# -------------------------------------------------------------------------------------------------------------------------
# Necessary imports and configurations for the job crawler
# -------------------------------------------------------------------------------------------------------------------------
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
    Job,
    CSS_SELECTOR_indeed_dir_page,
    CSS_SELECTOR_naukri_dir_page,
)
import parser_functions as pf

company, location, profession, website_name, job_number = pf.user_params(
    website_name="indeed", profession="it", job_number=5 , company='aws' , location='mumbai'
)
BASE_URL, input_url = pf.change_base_url(company, location, profession, website_name)


# -------------------------------------------------------------------------------------------------------------------------
async def crawl_jobs():
    browser_config = BrowserConfig(headless=False, verbose=True)
    page_number = 1
    jobs = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        jobs_links = []
        while True:
            result = await crawler.arun(
                url=(
                    f"{BASE_URL}-{page_number}"
                    if website_name == "naukri"
                    else f"{BASE_URL}&start={(page_number - 1) * 10}"
                ),
                config=CrawlerRunConfig(
                    exclude_external_links=True,
                    word_count_threshold=20,
                    js_code="window.scrollTo(0, document.body.scrollHeight);",
                    session_id="job_session",
                    css_selector=(
                        CSS_SELECTOR_naukri
                        if website_name == "naukri"
                        else CSS_SELECTOR_indeed
                    ),
                    wait_for=(
                        CSS_SELECTOR_naukri
                        if website_name == "naukri"
                        else CSS_SELECTOR_indeed
                    ),
                ),
            )
            soup = BeautifulSoup(result.html, "html.parser")
            cards = soup.select(
                CSS_SELECTOR_naukri if website_name == "naukri" else CSS_SELECTOR_indeed
            )
            # print(cards)  # Debugging line to check the cards found 
            for card in cards:
                a = card.select_one(
                    "a.title" if website_name == "naukri" else "h2.jobTitle a"
                )
                if not a or not a.get("href"):
                    continue  # skip this card
                link = a["href"]
                full = (
                    link.startswith("https") and link or "https://www.indeed.com" + link
                    if website_name == "indeed"
                    else link.startswith("https")
                    and link
                    or "https://www.naukri.com" + link
                )
                jobs_links.append(full)
                if len(jobs_links) >= job_number:
                    break
            #print(jobs_links)
            for job in range(len(jobs_links)):
                result_dir_page = await crawler.arun(
                    url=jobs_links[job],
                    config=CrawlerRunConfig(
                        exclude_external_links=True,
                        word_count_threshold=20,
                        js_code="window.scrollTo(0, document.body.scrollHeight);",
                        session_id="job_session",
                        css_selector=(
                            CSS_SELECTOR_naukri_dir_page
                            if website_name == "naukri"
                            else CSS_SELECTOR_indeed_dir_page
                        ),
                        wait_for=(
                            CSS_SELECTOR_naukri_dir_page
                            if website_name == "naukri"
                            else CSS_SELECTOR_indeed_dir_page
                        ),
                    ),
                )
                await asyncio.sleep(2)

                if website_name == "indeed":
                    pf.get_parsed_jobs_indeed(result_dir_page, jobs)
                else:
                    pf.get_parsed_jobs_naukri(result_dir_page, jobs)

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
