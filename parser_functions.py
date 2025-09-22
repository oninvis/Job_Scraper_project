#!/usr/bin/env python3
"""
Job Parsing Functions

This module contains utilities for parsing job data from different job sites
(Indeed, Naukri, LinkedIn) and utility functions for URL building and date parsing.
"""

import csv
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from bs4 import BeautifulSoup


# ================================
# User Configuration Functions
# ================================

def user_params(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
    job_number: int = 10,
) -> tuple:
    """
    Package user search parameters into a convenient tuple.

    Args:
        company: Company name to filter by
        location: Location to search in
        profession: Job profession/role to search for
        website_name: Target website (naukri, indeed, linkedin)
        job_number: Maximum number of jobs to scrape

    Returns:
        Tuple of all parameters for easy unpacking
    """
    return company, location, profession, website_name, job_number


# ================================
# Date Parsing Functions
# ================================

def parse_posted_date(relative_phrase: str) -> Optional[datetime]:
    """
    Convert relative date strings like '3 days ago' into actual dates.

    Args:
        relative_phrase: String like "3 days ago", "2 weeks ago", "just now"

    Returns:
        Date object or None if parsing fails
    """
    if not relative_phrase:
        return None

    phrase = relative_phrase.lower().strip()
    today = datetime.today()

    if "just now" in phrase:
        return today.date()

    # Define patterns for different time units
    patterns = [
        (r"(\d+)\s*day", lambda value: timedelta(days=value)),
        (r"(\d+)\s*week", lambda value: timedelta(weeks=value)),
        (r"(\d+)\s*month", lambda value: timedelta(days=30 * value)),
        (r"starts in\s*(\d+)\s*day", lambda value: -timedelta(days=value)),
        (r"starts in\s*(\d+)\s*week", lambda value: -timedelta(weeks=value)),
        (r"starts in\s*(\d+)\s*month", lambda value: -timedelta(days=30 * value)),
    ]

    for pattern, builder in patterns:
        match = re.search(pattern, phrase)
        if match:
            value = int(match.group(1))
            delta = builder(value)
            return (today - delta).date()

    return None


# ================================
# Title Extraction Functions
# ================================

# Site-specific selectors for job titles
SITE_TITLE_SELECTORS = {
    "naukri": [
        "section#job_header h1",
        "h1.styles_jd-header-title__rZwM1",
        "h1[class*='title']",
    ],
    "indeed": [
        "h1[data-testid='jobsearch-JobInfoHeader-title']",
        "h1.jobsearch-JobInfoHeader-title",
        "h1 span[title]",
    ],
    "linkedin": [
        "h1.topcard__title",
        "h1.jobs-unified-top-card__job-title",
        "h2.top-card-layout__title",
    ],
}


def _first_string(value: Any, keys: List[str]) -> str:
    """Find the first non-empty string value from nested dict keys."""
    for key in keys:
        candidate = value.get(key) if isinstance(value, dict) else None
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if isinstance(candidate, dict):
            nested = _first_string(candidate, ("text", "value"))
            if nested:
                return nested
    return ""


def _extract_title_from_json_ld(soup: BeautifulSoup) -> str:
    """Parse JSON-LD structured data blocks for job titles."""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except Exception:
            continue

        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            for key in ("title", "headline", "name"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, dict):
                    nested = _first_string(value, ("text", "value"))
                    if nested:
                        return nested
    return ""


def _extract_title_from_meta(soup: BeautifulSoup) -> str:
    """Extract job title from meta tags and microdata."""
    meta_selectors = [
        "meta[property='og:title']",
        "meta[name='og:title']",
        "meta[name='twitter:title']",
        "meta[itemprop='headline']",
        "meta[itemprop='title']",
        "meta[name='title']",
    ]

    for selector in meta_selectors:
        el = soup.select_one(selector)
        content = el.get("content") or el.get("value") if el else ""
        if content and content.strip():
            return content.strip()

    microdata_selectors = ["[itemprop='headline']", "[itemprop='name']", "[itemprop='title']"]
    for selector in microdata_selectors:
        el = soup.select_one(selector)
        if not el:
            continue
        content = el.get("content") or el.get_text(strip=True)
        if content:
            return content.strip()
    return ""


def _clean_title_text(title: str) -> str:
    """Clean and normalize job title text."""
    if not title:
        return ""

    cleaned = " ".join(title.split())

    # Filter out generic/unhelpful titles
    if cleaned.lower() in {"job", "jobs", "career", "careers", "apply", "application"}:
        return ""

    # Remove site name suffixes
    for site in ("Indeed", "LinkedIn", "Naukri", "Naukri.com"):
        if cleaned.endswith(site):
            cleaned = cleaned[: -len(site)].rstrip(" -|•:—–")
    return cleaned


def extract_title_with_debug(soup: BeautifulSoup, website_name: str, debug: bool = True) -> str:
    """
    Extract job title using multiple fallback strategies.

    Args:
        soup: BeautifulSoup object of the job page
        website_name: Name of the job site
        debug: Whether to print debug information

    Returns:
        Extracted job title or "Title Not Available"
    """
    site_key = (website_name or "").lower()
    selectors = SITE_TITLE_SELECTORS.get(site_key, [])
    debug_notes = []

    # Try site-specific selectors first
    for selector in selectors:
        el = soup.select_one(selector)
        if not el:
            continue
        candidate = el.get("title") or el.get_text(strip=True)
        candidate = _clean_title_text(candidate)
        if candidate:
            if debug:
                debug_notes.append(f"title from selector '{selector}'")
            break
    else:
        # Fallback to JSON-LD
        candidate = _clean_title_text(_extract_title_from_json_ld(soup))
        if candidate and debug:
            debug_notes.append("title from JSON-LD")

    # Fallback to meta tags
    if not candidate:
        candidate = _clean_title_text(_extract_title_from_meta(soup))
        if candidate and debug:
            debug_notes.append("title from meta tags")

    # Final fallback to page title
    if not candidate:
        page_title = soup.find("title")
        if page_title:
            candidate = _clean_title_text(page_title.get_text(strip=True))
            if candidate and debug:
                debug_notes.append("title from <title> tag")

    if not candidate:
        candidate = "Title Not Available"
        if debug:
            debug_notes.append("title lookup failed")

    if debug and debug_notes:
        print("; ".join(debug_notes))

    return candidate


# ================================
# URL Building Functions
# ================================

def change_base_url(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
) -> tuple:
    """
    Build site-specific search URLs based on filter parameters.

    Args:
        company: Company name filter
        location: Location filter
        profession: Job role filter
        website_name: Target job site

    Returns:
        Tuple of (base_url, input_url)
    """
    if website_name.lower() == "naukri":
        input_url = "https://www.naukri.com"
        if company and location and profession:
            base_url = f"{input_url}/{profession}-{company}-jobs-in-{location}"
        elif company and profession:
            base_url = f"{input_url}/{company}-{profession}-jobs"
        elif location and profession:
            base_url = f"{input_url}/jobs-in-{location}-{profession}"
        elif company and location:
            base_url = f"{input_url}/{company}-jobs-in-{location}"
        elif company:
            base_url = f"{input_url}/{company}-jobs"
        elif location:
            base_url = f"{input_url}/jobs-in-{location}"
        elif profession:
            base_url = f"{input_url}/{profession}-jobs"
        else:
            base_url = f'{input_url}/jobs'
        return base_url, input_url

    elif website_name.lower() == "indeed":
        input_url = "https://www.indeed.com"
        query_parts = []

        if profession:
            query_parts.append(profession)
        if company:
            query_parts.append(company)

        query = "+".join(query_parts) if query_parts else ""

        base_url = f"{input_url}/jobs"
        if query:
            base_url += f"?q={query}"
        if location:
            connector = "&" if query else "?"
            base_url += f"{connector}l={location}"

        return base_url, input_url

    elif website_name.lower() == "linkedin":
        input_url = "https://www.linkedin.com"

        keywords = []
        if profession:
            keywords.append(profession)
        if company:
            keywords.append(company)

        keywords_str = "%20".join(keywords) if keywords else ""

        base_url = f"{input_url}/jobs/search"
        params = []

        if keywords_str:
            params.append(f"keywords={keywords_str}")
        if location:
            params.append(f"location={location}")

        if params:
            base_url += "?" + "&".join(params)

        return base_url, input_url
    else:
        return None, None


# ================================
# Site-Specific Parsers
# ================================

def get_parsed_jobs_naukri(result: Any, jobs: List[Dict], debug: bool = False) -> List[Dict]:
    """
    Parse job details from a Naukri job page.

    Args:
        result: Crawl result object with HTML content
        jobs: List to append parsed job data to
        debug: Enable debug output

    Returns:
        Updated jobs list
    """
    soup = BeautifulSoup(result.html, "html.parser")

    # Extract title using enhanced method
    title = extract_title_with_debug(soup, "naukri", debug=debug)

    # If enhanced extraction failed, try manual fallback
    if title == "Title Not Available" and debug:
        print("\n--- Attempting manual title extraction ---")
        for tag in ['h1', 'h2', 'h3']:
            elements = soup.find_all(tag, limit=5)
            for el in elements:
                text = el.get_text(strip=True)
                if text and 10 < len(text) < 100:
                    job_keywords = ['developer', 'engineer', 'manager', 'analyst', 'designer',
                                  'administrator', 'specialist', 'consultant', 'architect',
                                  'lead', 'senior', 'junior', 'intern', 'associate']
                    if any(keyword in text.lower() for keyword in job_keywords):
                        print(f"Found potential title: {text[:80]}")
                        if title == "Title Not Available":
                            title = text
                            break
            if title != "Title Not Available":
                break

    # Extract company with fallbacks
    company = ""
    company_selectors = [
        "div.styles_jd-header-comp-name__MvqAI a",
        "a[class*='comp-name']",
        "div[class*='company'] a"
    ]
    for selector in company_selectors:
        comp_el = soup.select_one(selector)
        if comp_el:
            company = comp_el.get_text(strip=True)
            break

    # Extract location with fallbacks
    location = ""
    loc_selectors = [
        "div.styles_jhc__loc___Du2H span.styles_jhc__location__W_pVs",
        "span[class*='location']"
    ]
    for selector in loc_selectors:
        loc_container = soup.select_one(selector)
        if loc_container:
            locations = [a.get_text(strip=True) for a in loc_container.select("a")]
            if not locations:
                locations = [loc_container.get_text(strip=True)]
            location = ", ".join(filter(None, locations))
            break

    # Extract description with fallbacks
    description = ""
    desc_selectors = [
        "div.styles_JDC__dang-inner-html__h0K4t",
        "div[class*='description']",
        "div[class*='job-desc']"
    ]
    for selector in desc_selectors:
        desc_el = soup.select_one(selector)
        if desc_el:
            description = desc_el.get_text("\n", strip=True)[:100]
            break

    # Extract posted date
    posted = ""
    posted_selectors = [
        "div.styles_jhc__jd-stats__KrId0 span.styles_jhc__stat__PgY67",
        "span[class*='posted']"
    ]
    for selector in posted_selectors:
        stats = soup.select(selector)
        for stat in stats:
            text = stat.get_text(" ", strip=True)
            if "ago" in text.lower() or "posted" in text.lower():
                if ":" in text:
                    posted = parse_posted_date(text.split(":", 1)[1].strip())
                else:
                    posted = parse_posted_date(text)
                break
        if posted:
            break

    jobs.append({
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "posted": posted,
    })
    return jobs


def get_parsed_jobs_indeed(result: Any, jobs: List[Dict], debug: bool = False) -> List[Dict]:
    """
    Parse job details from an Indeed job page.

    Args:
        result: Crawl result object with HTML content
        jobs: List to append parsed job data to
        debug: Enable debug output

    Returns:
        Updated jobs list
    """
    soup = BeautifulSoup(result.html, "html.parser")

    # Extract title using enhanced method
    title = extract_title_with_debug(soup, "indeed", debug=debug)

    # Extract company with fallbacks
    company = ""
    company_selectors = [
        "div[data-company-name='true'] a",
        "div[data-company-name='true']",
        "a[data-testid*='company']",
        "div[class*='company'] a"
    ]
    for selector in company_selectors:
        comp_el = soup.select_one(selector)
        if comp_el:
            company = comp_el.get_text(strip=True)
            break

    # Extract location with fallbacks
    location = ""
    location_selectors = [
        "div[data-testid='inlineHeader-companyLocation']",
        "div[data-testid*='location']",
        "div[class*='location']"
    ]
    for selector in location_selectors:
        loc_el = soup.select_one(selector)
        if loc_el:
            location = loc_el.get_text(strip=True)
            break

    # Extract salary with fallbacks
    salary = ""
    salary_selectors = [
        "#salaryInfoAndJobType",
        "span[class*='salary']",
        "div[class*='salary']"
    ]
    for selector in salary_selectors:
        sal_el = soup.select_one(selector)
        if sal_el:
            salary = sal_el.get_text(strip=True)
            break

    # Extract description with fallbacks
    description = ""
    desc_selectors = [
        "div#jobDescriptionText",
        "div[class*='jobDescription']",
        "div[class*='description']"
    ]
    for selector in desc_selectors:
        desc_el = soup.select_one(selector)
        if desc_el:
            description = desc_el.get_text("\n", strip=True)[:100]
            break

    # Extract posted date
    posted = ""
    post_el = soup.find(string=lambda t: t and t.strip().lower().startswith("posted"))
    if not post_el:
        post_el = soup.find(string=lambda t: t and "ago" in t.lower())
    if post_el:
        text = post_el.strip()
        posted = text.split(":", 1)[-1].strip() if ":" in text else text

    jobs.append({
        "title": title,
        "company": company,
        "location": location,
        "salary": salary,
        "description": description,
        "posted": posted,
    })
    return jobs


def get_parsed_jobs_linkedin(result: Any, jobs: List[Dict], debug: bool = False) -> List[Dict]:
    """
    Parse job details from a LinkedIn job page.

    Args:
        result: Crawl result object with HTML content
        jobs: List to append parsed job data to
        debug: Enable debug output

    Returns:
        Updated jobs list
    """
    soup = BeautifulSoup(result.html, "html.parser")

    # Extract title using enhanced method
    title = extract_title_with_debug(soup, "linkedin", debug=debug)

    # Extract company with fallbacks
    company = ""
    company_selectors = [
        "a.topcard__org-name-link",
        "span.topcard__flavor",
        "a[class*='company']",
        "div[class*='company']"
    ]
    for selector in company_selectors:
        comp_el = soup.select_one(selector)
        if comp_el:
            company = comp_el.get_text(strip=True)
            break

    # Extract location with fallbacks
    location = ""
    location_selectors = [
        "span.topcard__flavor--bullet",
        "span[class*='location']"
    ]
    for selector in location_selectors:
        loc_el = soup.select_one(selector)
        if loc_el:
            location = loc_el.get_text(strip=True)
            break

    # Extract posted date with fallbacks
    posted = ""
    posted_selectors = [
        "span.posted-time-ago__text",
        "span[class*='posted']"
    ]
    for selector in posted_selectors:
        posted_el = soup.select_one(selector)
        if posted_el:
            posted = posted_el.get_text(strip=True)
            break

    if not posted:
        # Look for any span containing "ago"
        for span in soup.find_all("span"):
            if "ago" in span.get_text(strip=True).lower():
                posted = span.get_text(strip=True)
                break

    # Extract description with fallbacks
    description = ""
    desc_selectors = [
        "div.show-more-less-html__markup",
        "div.description__text",
        "div[class*='description']"
    ]
    for selector in desc_selectors:
        desc_el = soup.select_one(selector)
        if desc_el:
            description = desc_el.get_text("\n", strip=True)[:100]
            break

    jobs.append({
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "posted": posted,
    })
    return jobs


# ================================
# Export Functions
# ================================

def convert_to_csv(jobs: List[Dict], filename: str = "jobs.csv") -> None:
    """
    Export job data to CSV file.

    Args:
        jobs: List of job dictionaries
        filename: Output CSV filename
    """
    if not jobs:
        print("No jobs to save.")
        return

    # Dynamically determine columns from first job
    field_names = list(jobs[0].keys())

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"Extracted {len(jobs)} jobs and saved to {filename}")