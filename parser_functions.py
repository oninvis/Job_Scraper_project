from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import csv
import json
from config import CSS_SELECTOR_indeed_dir_page , CSS_SELECTOR_naukri_dir_page, CSS_SELECTOR_indeed, CSS_SELECTOR_naukri

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
    Returns None if it can’t parse.

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


def change_base_url(
    company: str = None,
    location: str = None,
    profession: str = None,
    website_name: str = None,
):
    if website_name == "naukri":
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
            BASE_URL = input_url
        return BASE_URL , input_url
    elif website_name == "indeed":
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
        return BASE_URL , input_url
    else:
        return None




def get_parsed_jobs_naukri(result, jobs):
    soup = BeautifulSoup(result.html, "html.parser")

    # Title
    title_el = soup.select_one("h1.styles_jd-header-title__rZwM1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Company
    comp_el = soup.select_one("div.styles_jd-header-comp-name__MvqAI a")
    company = comp_el.get_text(strip=True) if comp_el else ""

    # Location(s)
    loc_container = soup.select_one("div.styles_jhc__loc___Du2H span.styles_jhc__location__W_pVs")
    if loc_container:
        # there may be multiple <a> tags for each city
        locations = [a.get_text(strip=True) for a in loc_container.select("a")]
        location = ", ".join(locations)
    else:
        location = ""

    # Full description
    desc_el = soup.select_one("div.styles_JDC__dang-inner-html__h0K4t")
    description = desc_el.get_text("\n", strip=True) if desc_el else ""
    final_desc = description[:100]


    # Posted date
    posted = ""
    stats = soup.select("div.styles_jhc__jd-stats__KrId0 span.styles_jhc__stat__PgY67")
    for stat in stats:
        text = stat.get_text(" ", strip=True)
        if text.lower().startswith("posted"):
            # e.g. "Posted: 4 days ago"
            posted = parse_posted_date(text.split(":", 1)[1].strip())
            break

    jobs.append({
        "title": title,
        "company": company,
        "location": location,
        "description": final_desc,
        "posted": posted,
    })
    return jobs



from bs4 import BeautifulSoup

def get_parsed_jobs_indeed(result, jobs):
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

    # Title
    title_el = soup.select_one("h1[data-testid='jobsearch-JobInfoHeader-title']")
    title = title_el.get_text(strip=True) if title_el else ""

    # Company
    comp_el = soup.select_one("div[data-company-name='true'] a")
    company = comp_el.get_text(strip=True) if comp_el else ""

    # Location
    loc_el = soup.select_one("div[data-testid='inlineHeader-companyLocation']")
    location = loc_el.get_text(strip=True) if loc_el else ""

    # Salary
    sal_el = soup.select_one("#salaryInfoAndJobType")
    salary = sal_el.get_text(strip=True) if sal_el else ""

    # Full description
    desc_el = soup.select_one("div#jobDescriptionText")
    description = desc_el.get_text("\n", strip=True) if desc_el else ""

    # Posted date (e.g. "Posted: 4 days ago")
    posted = ""
    post_el = soup.find(string=lambda t: t and t.strip().lower().startswith("posted"))
    if post_el:
        # split off the "Posted:" prefix
        posted = post_el.strip().split(":", 1)[-1].strip()

    jobs.append({
        "title":       title,
        "company":     company,
        "location":    location,
        "salary":      salary,
        "description": description,
        "posted":      posted,
    })
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

