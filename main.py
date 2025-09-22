#!/usr/bin/env python3
"""
Job Scraper Application

A web scraper that extracts job listings from popular job sites:
- Indeed
- Naukri
- LinkedIn

The scraper supports filtering by company, location, and profession,
and exports results to CSV format.
"""

import asyncio
from typing import List, Dict, Any

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
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

# Configuration - modify these parameters as needed
company, location, profession, website_name, job_number = pf.user_params(
    website_name="indeed",  # Options: naukri, indeed, linkedin
    profession='it',
    job_number=20,
    # Uncomment to filter by specific company/location:
    # company="accenture",
    # location="mumbai",
)

# Generate base URL for the selected job site and filters
BASE_URL, input_url = pf.change_base_url(company, location, profession, website_name)


def get_site_config(website_name: str, page_number: int) -> Dict[str, Any]:
    """
    Get site-specific configuration for crawling.

    Returns:
        Dict containing page_url, css_selector, css_selector_dir_page,
        wait_selector_dir_page, and url_prefix
    """
    if website_name == "naukri":
        return {
            "page_url": f"{BASE_URL}-{page_number}",
            "css_selector": CSS_SELECTOR_naukri,
            "css_selector_dir_page": CSS_SELECTOR_naukri_dir_page,
            "wait_selector_dir_page": "section#job_header h1",
            "url_prefix": "https://www.naukri.com",
            "link_selector": "a.title"
        }
    elif website_name == "linkedin":
        return {
            "page_url": f"{BASE_URL}&start={(page_number - 1) * 25}",
            "css_selector": CSS_SELECTOR_linkedin,
            "css_selector_dir_page": CSS_SELECTOR_linkedin_dir_page,
            "wait_selector_dir_page": "h1[class*='topcard__title']",
            "url_prefix": input_url,
            "link_selector": "a.base-card__full-link"
        }
    else:  # indeed
        return {
            "page_url": f"{BASE_URL}&start={(page_number - 1) * 10}",
            "css_selector": CSS_SELECTOR_indeed,
            "css_selector_dir_page": CSS_SELECTOR_indeed_dir_page,
            "wait_selector_dir_page": "h1[data-testid='jobsearch-JobInfoHeader-title']",
            "url_prefix": "https://www.indeed.com",
            "link_selector": "h2.jobTitle a"
        }


def extract_job_links(soup: BeautifulSoup, config: Dict[str, Any]) -> List[str]:
    """
    Extract job listing URLs from a search results page.

    Args:
        soup: BeautifulSoup object of the page HTML
        config: Site configuration dictionary

    Returns:
        List of job URLs
    """
    job_links = []
    cards = soup.select(config["css_selector"])

    for card in cards:
        link_element = card.select_one(config["link_selector"])

        if not link_element or not link_element.get("href"):
            continue

        link = link_element["href"]
        full_url = link if link.startswith("https") else config["url_prefix"] + link
        job_links.append(full_url)

    return job_links


async def scrape_job_details(crawler: AsyncWebCrawler, job_links: List[str],
                           config: Dict[str, Any], jobs: List[Dict]) -> None:
    """
    Scrape detailed information from individual job pages.

    Args:
        crawler: AsyncWebCrawler instance
        job_links: List of job URLs to scrape
        config: Site configuration
        jobs: List to append parsed job data to
    """
    for job_link in job_links:
        try:
            result = await crawler.arun(
                url=job_link,
                config=CrawlerRunConfig(
                    exclude_external_links=True,
                    word_count_threshold=20,
                    js_code="window.scrollTo(0, document.body.scrollHeight);",
                    session_id="job_session",
                    css_selector=config["css_selector_dir_page"],
                    wait_for=config["wait_selector_dir_page"],
                ),
            )

            # Parse job details based on website
            if website_name == "indeed":
                pf.get_parsed_jobs_indeed(result, jobs)
            elif website_name == "naukri":
                pf.get_parsed_jobs_naukri(result, jobs)
            else:  # linkedin
                pf.get_parsed_jobs_linkedin(result, jobs)

            # Rate limiting
            await asyncio.sleep(3)

        except Exception as e:
            print(f"Error scraping job {job_link}: {e}")
            continue


async def crawl_jobs() -> None:
    """
    Main crawling function that orchestrates the job scraping process.

    Crawls job listings page by page until the desired number of jobs
    is collected, then exports results to CSV.
    """
    browser_config = BrowserConfig(headless=False, verbose=True)
    page_number = 1
    jobs: List[Dict] = []

    print(f"Starting job scraping from {website_name.upper()}...")
    print(f"Target: {job_number} jobs")

    async with AsyncWebCrawler(config=browser_config) as crawler:
        all_job_links: List[str] = []

        while len(jobs) < job_number:
            print(f"\nScraping page {page_number}...")

            # Get site-specific configuration
            config = get_site_config(website_name, page_number)

            try:
                # Scrape job listing page
                result = await crawler.arun(
                    url=config["page_url"],
                    config=CrawlerRunConfig(
                        exclude_external_links=True,
                        word_count_threshold=20,
                        js_code="window.scrollTo(0, document.body.scrollHeight);",
                        session_id="job_session",
                        css_selector=config["css_selector"],
                        wait_for=config["css_selector"],
                    ),
                )

                # Extract job links from the page
                soup = BeautifulSoup(result.html, "html.parser")
                page_job_links = extract_job_links(soup, config)

                if not page_job_links:
                    print(f"No job links found on page {page_number}. Stopping.")
                    break

                print(f"Found {len(page_job_links)} job links on page {page_number}")

                # Limit to target number
                remaining_needed = job_number - len(jobs)
                page_job_links = page_job_links[:remaining_needed]
                all_job_links.extend(page_job_links)

                # Scrape detailed job information
                await scrape_job_details(crawler, page_job_links, config, jobs)

                print(f"Scraped {len(jobs)} jobs so far")

                # Stop if we have enough jobs
                if len(jobs) >= job_number:
                    break

                page_number += 1
                await asyncio.sleep(5)  # Rate limiting between pages

            except Exception as e:
                print(f"Error on page {page_number}: {e}")
                break

    # Export results
    print(f"\nScraping completed! Found {len(jobs)} jobs.")
    if jobs:
        pf.convert_to_csv(jobs, "jobs.csv")
    else:
        print("No jobs were found to export.")


async def main() -> None:
    """
    Application entry point.
    """
    try:
        await crawl_jobs()
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
