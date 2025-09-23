#!/usr/bin/env python3
"""
Configuration Settings for Job Scraper

This module contains CSS selectors and configuration constants used
for scraping different job sites.
"""

from typing import List
from pydantic import BaseModel


# ================================
# Data Models
# ================================

class Job(BaseModel):
    """
    Pydantic model for job data structure.

    Note: This model is currently unused in the main scraper
    but can be used for data validation if needed.
    """
    title: str
    company: str
    experience: str
    location: str
    job_desc: str
    skills: List[str]
    posted_date: str = ''


# ================================
# CSS Selectors for Job Listing Pages
# ================================

# Naukri.com - Job listing cards on search results page
CSS_SELECTOR_naukri = '.srp-jobtuple-wrapper'

# Indeed.com - Job listing cards on search results page
CSS_SELECTOR_indeed = '.mainContentTable'

# LinkedIn.com - Job listing cards on search results page
CSS_SELECTOR_linkedin = "div.base-card.job-search-card"


# ================================
# CSS Selectors for Individual Job Pages
# ================================

# Naukri.com - Container for job details on individual job pages
CSS_SELECTOR_naukri_dir_page = 'div[class*=jd-container]'

# Indeed.com - Container for job details on individual job pages
CSS_SELECTOR_indeed_dir_page = 'div.jobsearch-JobComponent'

# LinkedIn.com - Container for job details on individual job pages
CSS_SELECTOR_linkedin_dir_page = "div.details"


# ================================
# Legacy Configuration
# ================================

# Fields that were previously required for job data
# Kept for backwards compatibility
REQUIRED_KEYS = [
    'title',
    'company',
    'experience',
    'job-description',
    'skills'
]


# ================================
# Site Configuration
# ================================

# Supported job sites
SUPPORTED_SITES = ['naukri', 'indeed', 'linkedin']

# Default job search limits per site
DEFAULT_JOB_LIMITS = {
    'naukri': 10,
    'indeed': 10,
    'linkedin': 25  # LinkedIn shows 25 jobs per page
}


