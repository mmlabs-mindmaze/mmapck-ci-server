# @[copyright_header]@
"""
Source for handling scanning change in repository
"""

from buildrequest import BuildRequest
from jobscheduler import JobScheduler


class EventSource:
    """
    Class encapsulating a source of project changes triggering build jobs
    """
    def __init__(self, scheduler: JobScheduler):
        self.scheduler = scheduler

    def add_build_request(self, req: BuildRequest):
        """
        Queue a build request to the scheduler
        """
        self.scheduler.add_build_request(req)

    def run(self):
        """
        event loop to run to generate events
        """
