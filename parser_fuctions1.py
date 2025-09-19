from datetime import datetime, timedelta
import csv
import json
import re

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# User input helpers
# ---------------------------------------------------------------------------


def user_params(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
    job_number: int = 10,
):
    """Return a tuple that keeps the caller signature tidy."""
    return company, location, profession, website_name, job_number


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def parse_posted_date(relative_phrase: str):
    """Convert a relative date string (e.g. '3 days ago') into a date."""
    if not relative_phrase:
        return None

    phrase = relative_phrase.lower().strip()
    today = datetime.today()

    if "just now" in phrase:
        return today.date()

    patterns = (
        (r"^(\d+)\s*day", lambda value: timedelta(days=value)),
        (r"^(\d+)\s*week", lambda value: timedelta(weeks=value)),
        (r"^(\d+)\s*month", lambda value: timedelta(days=30 * value)),
        (r"^starts in\s*(\d+)\s*day", lambda value: -timedelta(days=value)),
        (r"^starts in\s*(\d+)\s*week", lambda value: -timedelta(weeks=value)),
        (r"^starts in\s*(\d+)\s*month", lambda value: -timedelta(days=30 * value)),
    )

    for pattern, builder in patterns:
        match = re.search(pattern, phrase)
        if match:
            value = int(match.group(1))
            delta = builder(value)
            return (today - delta).date()

    return None


# ---------------------------------------------------------------------------
# Title extraction helpers
# ---------------------------------------------------------------------------


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


def _first_string(value, keys):
    """Return the first non-empty string belonging to keys inside value."""
    for key in keys:
        candidate = value.get(key) if isinstance(value, dict) else None
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if isinstance(candidate, dict):
            nested = _first_string(candidate, ("text", "value"))
            if nested:
                return nested
    return ""


def _extract_title_from_json_ld(soup):
    """Parse JSON-LD blocks and pull out a plausible title."""
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


def _extract_title_from_meta(soup):
    """Read common meta/itemprop attributes that carry the job title."""
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
    """Normalise whitespace and trim common site suffixes."""
    if not title:
        return ""

    cleaned = " ".join(title.split())
    if cleaned.lower() in {"job", "jobs", "career", "careers", "apply", "application"}:
        return ""

    for site in ("Indeed", "LinkedIn", "Naukri", "Naukri.com"):
        if cleaned.endswith(site):
            cleaned = cleaned[: -len(site)].rstrip(" -|•:—–")
    return cleaned


def extract_title_with_debug(soup, website_name, debug=True):
    """Extract the best guess for a job title, optionally logging misses."""
    site_key = (website_name or "").lower()
    selectors = SITE_TITLE_SELECTORS.get(site_key, [])
    debug_notes = []

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
        candidate = _clean_title_text(_extract_title_from_json_ld(soup))
        if candidate and debug:
            debug_notes.append("title from JSON-LD")

    if not candidate:
        candidate = _clean_title_text(_extract_title_from_meta(soup))
        if candidate and debug:
            debug_notes.append("title from meta tags")

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


def change_base_url(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
):
    """Build a site-specific search URL from the optional filters provided."""
    if website_name.lower() == "naukri":
        input_url = "https://www.naukri.com"
        if company and location and profession:
            BASE_URL = f"{input_url}/{profession}-{company}-jobs-in-{location}"
        elif company and profession:
            BASE_URL = f"{input_url}/{company}-{profession}-jobs"
        elif location and profession:
            BASE_URL = f"{input_url}/jobs-in-{location}-{profession}"
        elif company and location:
            BASE_URL = f"{input_url}/{company}-jobs-in-{location}"
        elif company:
            BASE_URL = f"{input_url}/{company}-jobs"
        elif location:
            BASE_URL = f"{input_url}/jobs-in-{location}"
        elif profession:
            BASE_URL = f"{input_url}/{profession}-jobs"
        else:
            BASE_URL = f'{input_url}/jobs'
        return BASE_URL, input_url
    elif website_name.lower() == "indeed":
        input_url = "https://www.indeed.com"
        if company and location and profession:
            BASE_URL = f"{input_url}/jobs?q={profession}+{company}&l={location}"
        elif company and profession:
            BASE_URL = f"{input_url}/jobs?q={company}+{profession}"
        elif location and profession:
            BASE_URL = f"{input_url}/jobs?q={profession}&l={location}"
        elif company and location:
            BASE_URL = f"{input_url}/jobs?q={company}&l={location}"
        elif company:
            BASE_URL = f"{input_url}/jobs?q={company}"
        elif location:
            BASE_URL = f"{input_url}/jobs?l={location}"
        elif profession:
            BASE_URL = f"{input_url}/jobs?q={profession}"
        else:
            BASE_URL = input_url
        return BASE_URL, input_url
    elif website_name.lower() == "linkedin":
        input_url = "https://www.linkedin.com"
        # LinkedIn job search endpoint
        #   /jobs/search?keywords=<…>&location=<…>

        if company and location and profession:
            BASE_URL = (
                f"{input_url}/jobs/search?"
                f"keywords={profession}%20{company}&location={location}"
            )
        elif company and profession:
            BASE_URL = f"{input_url}/jobs/search?" f"keywords={profession}%20{company}"
        elif location and profession:
            BASE_URL = (
                f"{input_url}/jobs/search?" f"keywords={profession}&location={location}"
            )
        elif company and location:
            BASE_URL = (
                f"{input_url}/jobs/search?" f"keywords={company}&location={location}"
            )
        elif company:
            BASE_URL = f"{input_url}/jobs/search?" f"keywords={company}"
        elif location:
            BASE_URL = f"{input_url}/jobs/search?" f"location={location}"
        elif profession:
            BASE_URL = f"{input_url}/jobs/search?" f"keywords={profession}"
        else:
            BASE_URL = input_url

        return BASE_URL, input_url
    else:
        return None


# ---------------------------------------------------------------------------
# Custom job parsers (user-authored)
# ---------------------------------------------------------------------------


def get_parsed_jobs_naukri(result, jobs, debug=False):
    soup = BeautifulSoup(result.html, "html.parser")

    # Title - using enhanced extraction with debug
    # Keep shared title extraction so the helper logic stays centralised.
    title = extract_title_with_debug(soup, "naukri", debug=debug)
    
    # If title extraction failed, try to get any context about the page
    if title == "Title Not Available" and debug:
        print("\n--- Attempting to extract ANY job-related text ---")
        # Try to find any text that might give us a clue
        for tag in ['h1', 'h2', 'h3', 'span', 'div']:
            elements = soup.find_all(tag, limit=10)
            for el in elements:
                text = el.get_text(strip=True)
                if text and 10 < len(text) < 100:
                    # Look for job-related keywords
                    job_keywords = ['developer', 'engineer', 'manager', 'analyst', 'designer', 
                                  'administrator', 'specialist', 'consultant', 'architect',
                                  'lead', 'senior', 'junior', 'intern', 'associate']
                    if any(keyword in text.lower() for keyword in job_keywords):
                        print(f"Potential job text in <{tag}>: {text[:80]}")
                        if title == "Title Not Available":
                            title = text  # Use this as fallback
                            break
            if title != "Title Not Available":
                break

    # Company
    comp_el = soup.select_one("div.styles_jd-header-comp-name__MvqAI a")
    if not comp_el:
        # Try alternate selectors
        comp_el = soup.select_one("a[class*='comp-name']")
    if not comp_el:
        comp_el = soup.select_one("div[class*='company'] a")
    company = comp_el.get_text(strip=True) if comp_el else ""

    # Location(s)
    loc_container = soup.select_one(
        "div.styles_jhc__loc___Du2H span.styles_jhc__location__W_pVs"
    )
    if not loc_container:
        # Try alternate selectors
        loc_container = soup.select_one("span[class*='location']")
    
    if loc_container:
        # there may be multiple <a> tags for each city
        locations = [a.get_text(strip=True) for a in loc_container.select("a")]
        if not locations:
            # If no anchor tags, get the text directly
            locations = [loc_container.get_text(strip=True)]
        location = ", ".join(locations)
    else:
        location = ""

    # Full description
    desc_el = soup.select_one("div.styles_JDC__dang-inner-html__h0K4t")
    if not desc_el:
        # Try alternate selectors
        desc_el = soup.select_one("div[class*='description']")
    if not desc_el:
        desc_el = soup.select_one("div[class*='job-desc']")
    description = desc_el.get_text("\n", strip=True) if desc_el else ""
    final_desc = description[:100]

    # Posted date
    posted = ""
    stats = soup.select("div.styles_jhc__jd-stats__KrId0 span.styles_jhc__stat__PgY67")
    if not stats:
        # Try alternate selectors
        stats = soup.select("span[class*='posted']")
    
    for stat in stats:
        text = stat.get_text(" ", strip=True)
        if "ago" in text.lower() or "posted" in text.lower():
            # e.g. "Posted: 4 days ago" or just "4 days ago"
            if ":" in text:
                posted = parse_posted_date(text.split(":", 1)[1].strip())
            else:
                posted = parse_posted_date(text)
            break

    jobs.append(
        {
            "title": title,
            "company": company,
            "location": location,
            "description": final_desc,
            "posted": posted,
        }
    )
    return jobs


def get_parsed_jobs_indeed(result, jobs, debug=False):
    """
    Parses an Indeed job-detail page (result.html) and appends a dict with:
      - title
      - company
      - location
      - salary
      - description
      - posted
    into the given jobs list.
    """
    soup = BeautifulSoup(result.html, "html.parser")

    # Title - using enhanced extraction with debug to stay consistent across sites
    title = extract_title_with_debug(soup, "indeed", debug=debug)

    # Company
    comp_el = soup.select_one("div[data-company-name='true'] a")
    if not comp_el:
        comp_el = soup.select_one("div[data-company-name='true']")
    if not comp_el:
        comp_el = soup.select_one("a[data-testid*='company']")
    if not comp_el:
        comp_el = soup.select_one("div[class*='company'] a")
    company = comp_el.get_text(strip=True) if comp_el else ""

    # Location
    loc_el = soup.select_one("div[data-testid='inlineHeader-companyLocation']")
    if not loc_el:
        loc_el = soup.select_one("div[data-testid*='location']")
    if not loc_el:
        loc_el = soup.select_one("div[class*='location']")
    location = loc_el.get_text(strip=True) if loc_el else ""

    # Salary
    sal_el = soup.select_one("#salaryInfoAndJobType")
    if not sal_el:
        sal_el = soup.select_one("span[class*='salary']")
    if not sal_el:
        sal_el = soup.select_one("div[class*='salary']")
    salary = sal_el.get_text(strip=True) if sal_el else ""

    # Full description
    desc_el = soup.select_one("div#jobDescriptionText")
    if not desc_el:
        desc_el = soup.select_one("div[class*='jobDescription']")
    if not desc_el:
        desc_el = soup.select_one("div[class*='description']")
    description = desc_el.get_text("\n", strip=True) if desc_el else ""
    description = description[:100]  # limit to first 100 chars

    # Posted date (e.g. "Posted: 4 days ago")
    posted = ""
    post_el = soup.find(string=lambda t: t and t.strip().lower().startswith("posted"))
    if not post_el:
        # Look for elements containing "ago"
        post_el = soup.find(string=lambda t: t and "ago" in t.lower())
    if post_el:
        # split off the "Posted:" prefix if present
        text = post_el.strip()
        if ":" in text:
            posted = text.split(":", 1)[-1].strip()
        else:
            posted = text

    jobs.append(
        {
            "title": title,
            "company": company,
            "location": location,
            "salary": salary,
            "description": description,
            "posted": posted,
        }
    )
    return jobs

def get_parsed_jobs_linkedin(result, jobs, debug=False):
    """
    Parse a LinkedIn job-detail page (result.html) and append a dict to jobs.
    """
    soup = BeautifulSoup(result.html, "html.parser")

    # Title - using enhanced extraction with debug to stay consistent across sites
    title = extract_title_with_debug(soup, "linkedin", debug=debug)

    # Company
    comp_el = soup.select_one("a.topcard__org-name-link")
    if not comp_el:
        # fallback if LinkedIn uses a span instead
        comp_el = soup.select_one("span.topcard__flavor")
    if not comp_el:
        comp_el = soup.select_one("a[class*='company']")
    if not comp_el:
        comp_el = soup.select_one("div[class*='company']")
    company = comp_el.get_text(strip=True) if comp_el else ""

    # Location
    loc_el = soup.select_one("span.topcard__flavor--bullet")
    if not loc_el:
        loc_el = soup.select_one("span[class*='location']")
    location = loc_el.get_text(strip=True) if loc_el else ""

    # Posted date
    posted_el = soup.select_one("span.posted-time-ago__text")
    if not posted_el:
        posted_el = soup.select_one("span[class*='posted']")
    if not posted_el:
        # Look for text containing "ago"
        for span in soup.find_all("span"):
            if "ago" in span.get_text(strip=True).lower():
                posted_el = span
                break
    posted = posted_el.get_text(strip=True) if posted_el else ""

    # Full description
    desc_el = soup.select_one("div.show-more-less-html__markup")
    if not desc_el:
        # another common wrapper
        desc_el = soup.select_one("div.description__text")
    if not desc_el:
        desc_el = soup.select_one("div[class*='description']")
    description = desc_el.get_text("\n", strip=True) if desc_el else ""
    description = description[:100]  # limit to first 100 chars

    jobs.append(
        {
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "posted": posted,
        }
    )
    return jobs


def convert_to_csv(jobs, filename="jobs.csv"):
    if not jobs:
        print("No jobs to save.")
        return

    # Dynamically infer the exact columns from the first job dict
    field_names = list(jobs[0].keys())

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=field_names)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"Extracted {len(jobs)} jobs and saved to {filename}")
