# @[copyright_header]@
"""
Source providing the adding and executing of build jobs
"""

from subprocess import Popen, PIPE
from common import log_error


class Repository:
    """
    Class encapsulating the access to the repository. It is a thin layer around
    a long live process created with a call to "mmpack-modifyrepo batch".
    """
    def __init__(self, name, path: str, arch: str):
        cmd_argv = ['mmpack-modifyrepo',
                    '--path=' + path,
                    '--arch=' + arch,
                    'batch']

        proc = Popen(cmd_argv, shell=False,
                     stdin=PIPE, stdout=PIPE, universal_newlines=True)
        self.proc = proc
        self.name = name
        self.arch = arch

    def _send_cmd(self, cmd: str):
        # Write newline terminated command to stdin of child
        print(cmd, file=self.proc.stdin, flush=True)

        # Parse result from stdout of child
        resline = self.proc.stdout.readline()
        res = resline.strip('\n').split(maxsplit=1)
        msg = res[1:]
        if res[0] != 'OK':
            errmsg = 'Failed to {} in {}: {}'.format(cmd, self.name, msg)
            log_error(errmsg)
            raise RuntimeError(errmsg)

    def add(self, manifest_file: str):
        """
        Stage adding manifest to repository

        Args:
            manifest_file: path to mmpack manifest

        Raises:
            RuntimeError: Add manifest failed
        """
        self._send_cmd('ADD ' + manifest_file)

    def commit(self):
        """
        Commit stagged changes to repository
        """
        self._send_cmd('COMMIT')

    def rollback(self):
        """
        rollback stagged changes to repository
        """
        self._send_cmd('ROLLBACK')
