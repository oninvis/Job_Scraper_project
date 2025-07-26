from pydantic import BaseModel
class Job(BaseModel):
    title: str
    company: str
    experience: str
    location: str
    job_desc: str
    skills: list[str]
    posted_date: str = ''  # Added posted_date field with default empty string

#BASE_URL = 'https://www.naukri.com/it-jobs' # change the base url as per your requirement
CSS_SELECTOR_naukri = '.srp-jobtuple-wrapper'#'[class^=srp-jobtuple-wrapper]' # change the css selector according to the website structure
CSS_SELECTOR_indeed = '.mainContentTable'#'[class^=mainContentTable]' # change the css selector according to the website structure
CSS_SELECTOR_indeed_dir_page = 'div.jobsearch-JobComponent'#'[class^=jobsearch-JobComponent]' # change the css selector according to the website structure
CSS_SELECTOR_naukri_dir_page = 'div[class*=jd-container]'#'[class^=styles_jd-container_nFVw8]'
#each job “card” on the LinkedIn results page 
CSS_SELECTOR_linkedin = "div.base-card.job-search-card"
CSS_SELECTOR_linkedin_dir_page = "div.details"

# the <a> inside that card which links to the job detail page */


REQUIRED_KEYS = [
    'title',
    'company',
    'experience',
    'job-description',
    'skills'
]


