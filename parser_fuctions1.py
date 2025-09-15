from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import csv
import json
from config import (
    CSS_SELECTOR_indeed_dir_page,
    CSS_SELECTOR_naukri_dir_page,
    CSS_SELECTOR_indeed,
    CSS_SELECTOR_naukri,
)


def user_params(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
    job_number: int = 10,
):
    return company, location, profession, website_name, job_number


def text_or(el, default=""):
    return el.get_text(strip=True) if el else default


def parse_posted_date(rel: str):
    """
    Convert strings like '1 day ago', '3 weeks ago', 'Just now',
    or 'Starts in 1-3 months' into a datetime.date.
    Returns None if it can't parse.

    """
    rel = rel.lower().strip()
    today = datetime.today()

    if not rel:
        return None
    if "just now" in rel:
        return today.date()

    # X days ago
    m = re.match(r"(\d+)\s*day", rel)
    if m:
        return (today - timedelta(days=int(m.group(1)))).date()

    # X weeks ago
    m = re.match(r"(\d+)\s*week", rel)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).date()

    # X months ago (approximate as 30 days each)
    m = re.match(r"(\d+)\s*month", rel)
    if m:
        return (today - timedelta(days=30 * int(m.group(1)))).date()

    # Starts in X days / weeks / months
    m = re.match(r"starts in\s*(\d+)\s*day", rel)
    if m:
        return (today + timedelta(days=int(m.group(1)))).date()
    m = re.match(r"starts in\s*(\d+)\s*week", rel)
    if m:
        return (today + timedelta(weeks=int(m.group(1)))).date()
    m = re.match(r"starts in\s*(\d+)\s*month", rel)
    if m:
        return (today + timedelta(days=30 * int(m.group(1)))).date()

    return None


def _extract_title_from_json_ld(soup, debug=False):
    """Try to extract title-like fields from JSON-LD blocks.
    Looks for JobPosting, Article, NewsArticle, WebPage, and generic objects.
    Returns a cleaned string or "".
    """
    def _get_first(d, keys):
        for k in keys:
            if isinstance(d, dict) and k in d and isinstance(d[k], str) and d[k].strip():
                return d[k].strip()
        return ""

    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    for sc in scripts:
        try:
            data = json.loads(sc.string or sc.get_text() or "")
        except Exception:
            continue

        # Normalize into iterable of dicts
        candidates = data if isinstance(data, list) else [data]
        for obj in candidates:
            if not isinstance(obj, dict):
                continue

            atype = obj.get("@type")
            # Prefer JobPosting -> title/headline/name
            if atype == "JobPosting":
                t = _get_first(obj, ["title", "headline", "name"]) or _get_first(obj.get("title", {}), ["text"])  # some sites nest
                if t:
                    if debug:
                        print(f"\nFound title in JSON-LD JobPosting: {t[:100]}")
                    return t

            # Common content types also carry headline/title
            if atype in {"Article", "NewsArticle", "BlogPosting", "WebPage"}:
                t = _get_first(obj, ["headline", "title", "name"]) or _get_first(obj.get("headline", {}), ["text"]) 
                if t:
                    if debug:
                        print(f"\nFound title in JSON-LD {atype}: {t[:100]}")
                    return t

            # Generic attempt
            t = _get_first(obj, ["title", "headline", "name"]) or _get_first(obj.get("title", {}), ["text"]) 
            if t:
                if debug:
                    print(f"\nFound title in JSON-LD object: {t[:100]}")
                return t

    return ""


def _extract_title_from_meta(soup, debug=False):
    """Try a comprehensive set of meta tags for title.
    Checks OpenGraph, Twitter, itemprop, and a few common vendor tags.
    Returns string or "".
    """
    meta_selectors = [
        "meta[property='og:title']",
        "meta[name='og:title']",
        "meta[name='twitter:title']",
        "meta[name='sailthru.title']",
        "meta[itemprop='headline']",
        "meta[itemprop='title']",
        "meta[name='title']",
        "meta[name='hdl']",
    ]
    for sel in meta_selectors:
        el = soup.select_one(sel)
        if el and (el.get("content") or el.get("value")):
            t = (el.get("content") or el.get("value") or "").strip()
            if t:
                if debug:
                    print(f"\nFound title in meta tag ({sel}): {t[:100]}")
                return t

    # Microdata attributes sometimes appear on non-meta tags
    micro_sel = ["[itemprop='headline']", "[itemprop='name']", "[itemprop='title']"]
    for sel in micro_sel:
        el = soup.select_one(sel)
        if el:
            t = (el.get("content") or el.get_text(strip=True) or "").strip()
            if t:
                if debug:
                    print(f"\nFound title via itemprop ({sel}): {t[:100]}")
                return t
    return ""


def _clean_title_text(title: str) -> str:
    if not title:
        return ""
    # Normalize whitespace
    t = " ".join(title.split())
    # Strip common site suffixes and job generic words if they are the whole string
    if t.lower() in {"job", "jobs", "career", "careers", "apply", "application"}:
        return ""
    # Remove leading/trailing separators and common site names
    for site in ["Indeed", "LinkedIn", "Naukri", "Naukri.com"]:
        if t.endswith(site):
            t = t[: -len(site)].strip(" -|•:\u2013\u2014")
    return t


def extract_title_with_debug(soup, website_name, debug=True):
    """
    Extract job title with extensive debugging to identify the issue.
    """
    title = ""
    
    if debug:
        print(f"\n{'='*50}")
        print(f"DEBUG: Extracting title for {website_name}")
        print(f"{'='*50}")
        
        # First, let's see all h1, h2, and h3 tags
        print("\n--- All H1 tags found ---")
        h1_tags = soup.find_all("h1")
        for i, h1 in enumerate(h1_tags[:5]):  # Show first 5
            print(f"H1 #{i}: {h1.get_text(strip=True)[:100]}")
            print(f"   Classes: {h1.get('class')}")
            print(f"   ID: {h1.get('id')}")
            print(f"   Data attributes: {[k for k in h1.attrs.keys() if k.startswith('data-')]}")
        
        print("\n--- All H2 tags found ---")
        h2_tags = soup.find_all("h2")
        for i, h2 in enumerate(h2_tags[:5]):  # Show first 5
            print(f"H2 #{i}: {h2.get_text(strip=True)[:100]}")
            print(f"   Classes: {h2.get('class')}")
        
        # Let's also check the page title
        page_title = soup.find("title")
        if page_title:
            print(f"\n--- Page <title> tag ---")
            print(f"Title: {page_title.get_text(strip=True)}")
        
        # Check meta tags
        print("\n--- Meta tags with potential title info ---")
        meta_tags = soup.find_all("meta", attrs={"property": True})
        for meta in meta_tags[:10]:
            if "title" in str(meta.get("property", "")).lower():
                print(f"Meta: {meta.get('property')} = {meta.get('content', '')[:100]}")
    
    # Now try to extract based on website
    if website_name.lower() == "naukri":
        # Try all possible Naukri selectors
        selectors = [
            "h1.styles_jd-header-title__rZwM1",
            "h1[class*='title']",
            "h1[class*='Title']",
            "h1[class*='header']",
            "div[class*='title'] h1",
            "div[class*='Title'] h1",
            ".jd-header-title",
            "h1",  # Generic h1
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for el in elements:
                    text = el.get_text(strip=True)
                    if text and 5 < len(text) < 200:
                        if debug:
                            print(f"\nFound title with selector '{selector}': {text[:100]}")
                        title = text
                        break
            if title:
                break
                
    elif website_name.lower() == "indeed":
        # Try all possible Indeed selectors
        selectors = [
            "h1[data-testid='jobsearch-JobInfoHeader-title']",
            "h1.jobsearch-JobInfoHeader-title",
            "h1 span[title]",  # Sometimes title is in a span with title attribute
            "h1 span",
            "div[class*='jobsearch'] h1",
            "div[class*='JobInfoHeader'] h1",
            "[class*='title']",
            "h1",  # Generic h1
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for el in elements:
                    # Check if there's a title attribute
                    if el.get('title'):
                        text = el.get('title')
                    else:
                        text = el.get_text(strip=True)
                    
                    if text and 5 < len(text) < 200 and not text.startswith("Company"):
                        if debug:
                            print(f"\nFound title with selector '{selector}': {text[:100]}")
                        title = text
                        break
            if title:
                break
                
    elif website_name.lower() == "linkedin":
        # Try all possible LinkedIn selectors
        selectors = [
            "h1.topcard__title",
            "h1.jobs-unified-top-card__job-title",
            "h2.top-card-layout__title",
            "h1[class*='title']",
            "h1[class*='Title']",
            "div.top-card h1",
            "h1",  # Generic h1
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for el in elements:
                    text = el.get_text(strip=True)
                    if text and 5 < len(text) < 200:
                        if debug:
                            print(f"\nFound title with selector '{selector}': {text[:100]}")
                        title = text
                        break
            if title:
                break
    
    # Try generic JSON-LD and meta fallbacks before page <title>
    if not title:
        json_ld_title = _extract_title_from_json_ld(soup, debug=debug)
        if json_ld_title:
            title = json_ld_title

    if not title:
        meta_title = _extract_title_from_meta(soup, debug=debug)
        if meta_title:
            title = meta_title

    # Final fallback - look for any reasonable text that could be a title
    if not title:
        # Try to extract from page title
        page_title_el = soup.find("title")
        if page_title_el:
            full_title = page_title_el.get_text(strip=True)
            if debug:
                print(f"\nTrying to extract from page title: {full_title}")
            
            # Clean up the title
            # Remove company names and locations that typically come after separators
            if " - " in full_title:
                parts = full_title.split(" - ")
                title = parts[0].strip()
            elif " | " in full_title:
                parts = full_title.split(" | ")
                title = parts[0].strip()
            else:
                # Remove common suffixes
                for suffix in ["Jobs", "Job", "Careers", "Career", "Hiring", "Opening"]:
                    if full_title.endswith(suffix):
                        full_title = full_title[:-len(suffix)].strip()
                title = full_title
            
            # Remove website names
            for site in ["Indeed", "LinkedIn", "Naukri", "Naukri.com"]:
                if title.endswith(site):
                    title = title[:-len(site)].strip(" -|")
    
    # Try meta/twitter/itemprop as absolute last resort (covers sites without <title> semantics)
    if not title:
        meta_title = _extract_title_from_meta(soup, debug=debug)
        if meta_title:
            title = meta_title
    
    # Clean up the title
    if title:
        # Remove extra whitespace and generic single-word titles
        title = _clean_title_text(title)
        if not title:
            title = "Title Not Available"
    else:
        title = "Title Not Available"
        if debug:
            print("\n!!! Could not find title - please check the HTML structure !!!")
            # Print a sample of the HTML to understand structure
            print("\nFirst 2000 characters of HTML body:")
            body = soup.find("body")
            if body:
                body_text = str(body)[:2000]
                print(body_text)
    
    if debug:
        print(f"\n{'='*50}")
        print(f"FINAL TITLE: {title}")
        print(f"{'='*50}\n")
    
    return title


def change_base_url(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
):
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


def get_parsed_jobs_naukri(result, jobs, debug=False):
    soup = BeautifulSoup(result.html, "html.parser")

    # Title - using enhanced extraction with debug
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

    # Title - using enhanced extraction with debug
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

    # Title - using enhanced extraction with debug
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
