# @[copyright_header]@
"""
Source providing the adding and executing of build jobs
"""

import re
from queue import Queue
from threading import Thread, Lock
from typing import Dict, List

from repository import Repository

from builder import Builder
from buildjob import BuildJob
from common import log_info, log_error


class FilterRule:
    """
    Class used to represent the action to take when a matching job is added
    """
    def __init__(self, upload: List[str], patterns: Dict[str, str] = None):
        if not patterns:
            patterns = {}

        self.regex_map = {k: re.compile(p) for k, p in patterns.items()}
        self.repo_names = upload

    def match(self, job: BuildJob) -> bool:
        """
        Test whether a job fulfills the criteria of the FilterRule
        """
        for key, regex in self.regex_map.items():
            attrvalue = getattr(job, key, None)
            if not (attrvalue and regex.fullmatch(attrvalue)):
                return False

        return True

    @staticmethod
    def load_rules(config: dict):
        """
        Factory of all filter rules described in the config file. The created
        rules are returned in a dictionary.
        """
        repo_names = list(config['repositories'].keys())

        rules = {}
        for key, cfg in config.get('rules', {}).items():
            rules[key] = FilterRule(**cfg)

        if not rules:
            rules = {'default': FilterRule(upload=repo_names)}

        return rules


class _BuildScheduledJob:
    # pylint: disable=too-few-public-methods
    def __init__(self, job: BuildJob, done_queue: Queue, num_build: int):
        self.job = job
        self.done_queue = done_queue
        self.num_active_build = num_build
        self.lock = Lock()
        self.feedback_msgs = []
        self.success = True

    def build_done(self, success: bool, msg: str):
        """
        method at the end of each build of a job
        """
        with self.lock:
            self.feedback_msgs.append(msg)
            if not success:
                self.success = False

            # Add to repo update queue if all build done
            self.num_active_build -= 1
            if self.num_active_build == 0:
                self.done_queue.put(self)


class _BuilderQueue(Thread):
    """
    class representing the job to be executed on a builder
    """
    def __init__(self, builder: Builder):
        super().__init__()
        self.builder = builder
        self.queue = Queue()

    def _process_job(self, scheduled_job: _BuildScheduledJob):
        builder = self.builder
        success = True
        try:
            builder.build(scheduled_job.job)
            msg = 'build on {} succeed'.format(builder)
            log_info(msg)
        except Exception as exception:  # pylint: disable=broad-except
            msg = 'build on {} failed: {}'.format(builder, str(exception))
            log_error(msg)
            success = False
        scheduled_job.build_done(success, msg)

    def run(self):
        queue = self.queue

        log_info('Builder queue for {} started'.format(self.builder))
        while True:
            scheduled_job = queue.get()
            if not scheduled_job:
                break

            self._process_job(scheduled_job)
            queue.task_done()

        log_info('Builder queue for {} stopped'.format(self.builder))

    def stop(self):
        """
        Stop asynchronous processing of incoming build jobs
        """
        self.queue.put(None)
        self.join()

    def add_scheduled_job(self, scheduled_job: _BuildScheduledJob):
        """
        Put a job to the scheduled job queue
        """
        self.queue.put(scheduled_job)


class JobScheduler(Thread):
    """
    Class to execute job asynchronously
    """
    def __init__(self, config: dict):
        super().__init__()
        self.queue = Queue()
        self.repos = {k: Repository(k, v['path'], v['architecture'])
                      for k, v in config['repositories'].items()}
        self.builder_queues = {k: _BuilderQueue(Builder(name=k, cfg=v))
                               for k, v in config['builders'].items()}
        self.rules = FilterRule.load_rules(config)

    def _schedule_job_for_build(self, job: BuildJob):
        builder_queues = self.builder_queues.values()
        num_build = len(builder_queues)

        scheduled_job = _BuildScheduledJob(job, self.queue, num_build)
        for builder_queue in builder_queues:
            builder_queue.add_scheduled_job(scheduled_job)

    def _process_build_done(self, job: BuildJob, success: bool, feedback: str):
        if not success:
            job.notify_result(False, feedback)
            return

        if not job.do_upload:
            job.notify_result(True, 'Packages upload skipped')
            return

        modified_repos = []
        try:
            # Update repositories
            manifest = job.merge_manifests()
            for reponame in job.repo_name_set:
                repo = self.repos[reponame]
                modified_repos.append(repo)
                repo.add(manifest)

        except Exception as exception:  # pylint: disable=broad-except
            # Rollback changes in repositories modified so far
            for repo in modified_repos:
                repo.rollback()
            job.notify_result(False, str(exception))
            return

        # Commit changes in modified repositories
        for repo in modified_repos:
            repo.commit()
            log_info('Arch {} uploaded on {}'.format(repo.arch, repo.name))

        job.notify_result(True)

    def run(self):
        queue = self.queue

        log_info('Job queue started')
        while True:
            scheduled_job = queue.get()
            if not scheduled_job:
                queue.task_done()
                break

            job = scheduled_job.job
            success = scheduled_job.success
            feedback = '\n'.join(scheduled_job.feedback_msgs)
            self._process_build_done(job, success, feedback)

            queue.task_done()
        log_info('Job queue stopped')

    def start(self):
        """
        Start asynchronous processing of incoming build jobs
        """
        for builder_queue in self.builder_queues.values():
            builder_queue.start()

        super().start()

    def stop(self):
        """
        Stop asynchronous processing of incoming build jobs
        """
        for builder_queue in self.builder_queues.values():
            builder_queue.stop()

        self.queue.put(None)
        self.join()

    def add_job(self, job: BuildJob):
        """
        Add a job in the queue of processing
        """
        for rule in self.rules.values():
            if rule.match(job):
                job.repo_name_set = rule.repo_names
                break

        if not job.repo_name_set:
            return

        # Generate mmpack source
        log_info('making source package for {}'.format(job))
        done = job.make_srcpkg()
        if not done:
            log_info('No mmpack packaging, build cancelled')
            return
        log_info('Done')

        self._schedule_job_for_build(job)
