# @[copyright_header]@
"""
Source for handling scanning change in repository
"""

from buildjob import BuildJob
from jobscheduler import JobScheduler


class EventSource:
    """
    Class encapsulating a source of project changes triggering build jobs
    """
    def __init__(self, scheduler: JobScheduler):
        self.scheduler = scheduler

    def add_job(self, job: BuildJob):
        """
        Queue a job to the scheduler
        """
        self.scheduler.add_job(job)

    def run(self):
        """
        event loop to run to generate events
        """
