# @[copyright_header]@
"""
Representation of a request to build a commit
"""


class BuildRequest:
    # pylint: disable=too-many-instance-attributes
    """
    Class representing a build request, ie a change in a repository which will
    in turn spawn in later stages build jobs. If the repository is a
    multiproject, there might several build jobs for one build request.
    """
    def __init__(self, project: str, url: str, refspec: str, **kwargs):
        self.project = project
        self.fetch_refspec = refspec
        self.url = url
        self.ref = refspec
        self.do_upload = True
        self.upload_repo = ''
        self.archs = []
        self.srctar_make_opts = kwargs

    def notify_result(self, success: bool, message: str = None):
        """
        Method called when the build has been finished (success or failure). It
        can be used as a hook to notify the event source about the result of
        the build.

        Args:
            success: True if build was successful
            message: optional message to sent along the result
        """

    def __repr__(self):
        return '{} commit {}'.format(self.project, self.ref)
