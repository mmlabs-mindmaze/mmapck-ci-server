# @[copyright_header]@
"""
Source build event using Gerrit
"""

from typing import Dict

from buildrequest import BuildRequest
from common import log_error, subdict
from eventsrc import EventSource
from jobscheduler import JobScheduler
from gerrit import Gerrit


class GerritBuildRequest(BuildRequest):
    # pylint: disable=too-few-public-methods
    """
    Class encapsulating a build job generated through gerrit stream-events
    command
    """
    def __init__(self, clone_url: str, clone_opts: Dict[str, str],
                 gerrit: Gerrit, gerrit_event: dict):
        project = gerrit_event['change']['project']
        branch = gerrit_event['change']['branch']
        change = gerrit_event['patchSet']['revision']
        oldref = gerrit_event['patchSet']['parents'][0]

        super().__init__(project=project,
                         url='{}/{}'.format(clone_url, project),
                         refspec=change,
                         oldref=oldref,
                         **clone_opts)
        self.gerrit_instance = gerrit
        self.gerrit_change = change
        self.branch = branch

    def notify_result(self, success: bool, message: str = None):
        self.gerrit_instance.review(self.project, self.gerrit_change, message)


def _trigger_build(event):
    """
    test whether an event is a merge event, or a manual trigger
    """
    do_build = False
    do_upload = False
    build_all = False
    try:
        evttype = event['type']
        if evttype == 'change-merged':
            do_build = True
            do_upload = True
        elif evttype == 'comment-added':
            comment = event['comment']
            if 'MMPACK_UPLOAD_BUILD' in comment:
                do_build = True
                do_upload = True

            if 'MMPACK_BUILD' in comment:
                do_build = True

            if 'BUILD_ALL_SUBPROJECTS' in comment:
                build_all = True

    except KeyError:
        pass

    return (do_build, do_upload, build_all)


class GerritEventSource(EventSource):
    """
    Class representing an event source spawning event from gerrit streamed
    events
    """
    def __init__(self, scheduler: JobScheduler, config=Dict[str, str]):
        """
        Initialize a Gerrit based event source

        Args:
            @scheduler: scheduler to which job must be added
            @config: dictionary configuring the connection to gerrit. Allowed
                keys are 'hostname', 'username', 'port', 'keyfile' and
                'clone_url'
        """
        # Create connection to gerrit command line
        cfg = subdict(config, ['hostname', 'username', 'port', 'keyfile'])
        gerrit = Gerrit(**cfg)

        # determine settings for git clone when a project must be build
        clone_opts = {}
        clone_url = config.get('clone_url')
        if not clone_url:
            clone_url = 'ssh://{}@{}:{:d}'.format(gerrit.username,
                                                  gerrit.hostname,
                                                  int(gerrit.port))
            if gerrit.keyfile:
                clone_opts['git_ssh_cmd'] = 'ssh -i ' + gerrit.keyfile

        super().__init__(scheduler)
        self.gerrit_instance = gerrit
        self.clone_url = clone_url
        self.clone_opts = clone_opts

    def _handle_gerrit_event(self, event: dict):
        do_build, do_upload, build_all = _trigger_build(event)
        if not do_build:
            return

        req = GerritBuildRequest(clone_url=self.clone_url,
                                 clone_opts=self.clone_opts,
                                 gerrit=self.gerrit_instance,
                                 gerrit_event=event)
        req.do_upload = do_upload
        if build_all:
                req.srctar_make_opts['only_modified'] = False
        self.add_build_request(req)

    def run(self):
        self.gerrit_instance.startWatching()

        while True:
            try:
                event = self.gerrit_instance.getEvent()
            except Exception as err:  # pylint: disable=broad-except
                # an error occurred, but NOT one involving package
                # generation just let slide, it may be caused by a hiccup
                # in the infrastructure.
                log_error('ignoring exception {}'.format(str(err)))
                continue

            self._handle_gerrit_event(event)
