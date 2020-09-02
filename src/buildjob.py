# @[copyright_header]@
"""
Representation of a build job
"""

import os
import shutil
from glob import glob
from tempfile import mkdtemp, TemporaryDirectory
from typing import Iterator

import yaml
from mmpack_build.source_tarball import SourceTarball

from buildrequest import BuildRequest
from common import log_info, sha256sum


class BuildJob:
    # pylint: disable=too-many-instance-attributes
    """
    Class representing a build to be performed
    """
    def __init__(self, request: BuildRequest, name: str, version: str, srctar: str):
        self.pkgdir = mkdtemp(prefix='mmpack')
        self.prj_name = name
        self.version = version
        self.srctar = shutil.move(srctar, self.pkgdir)
        self.request = request
        self.do_upload = request.do_upload
        self.build_id = os.path.basename(self.pkgdir)
        self.deps_repos = request.deps_repos
        self.upload_repo = request.upload_repo
        self.archs = request.archs
        self.srchash = sha256sum(self.srctar)

    def __del__(self):
        if self.pkgdir:
            shutil.rmtree(self.pkgdir, ignore_errors=True)

    def __repr__(self):
        desc = '{}-{} {} (build {})'.format(self.prj_name,
                                            self.version,
                                            self.srchash,
                                            self.build_id)
        return desc

    def notify_result(self, success: bool, message: str = None):
        """
        Method called when the build has been finished (success or failure).

        Args:
            success: True if build was successful
            message: optional message to sent along the result
        """
        self.request.notify_result(success, message)

    def merge_manifests(self) -> str:
        """
        find all mmpack manifest of a folder, and create an aggregated
        version of them in the same folder

        Return: the path to the aggregated manifest.
        """
        common_keys = ('name', 'source', 'version')

        merged = {}
        for manifest_file in glob(self.pkgdir + '/*.mmpack-manifest'):
            elt_data = yaml.load(open(manifest_file, 'rb'),
                                 Loader=yaml.BaseLoader)
            if not merged:
                merged = elt_data

            # Check consistency between source, name and source version
            merged_common = {k: v for k, v in merged.items() if k in common_keys}
            elt_common = {k: v for k, v in elt_data.items() if k in common_keys}
            if merged_common != elt_common:
                raise RuntimeError('merging inconsistent manifest')

            # merged list of binary packages for each architecture
            merged['binpkgs'].update(elt_data['binpkgs'])

        filename = '{}/{}_{}.mmpack-manifest'.format(self.pkgdir,
                                                     merged['name'],
                                                     merged['version'])
        yaml.dump(merged,
                  open(filename, 'w+', newline='\n'),
                  default_style='',
                  allow_unicode=True,
                  indent=4)
        return filename


def generate_buildjobs(req: BuildRequest) -> Iterator[BuildJob]:
    """
    Generate the mmpack source packages from a build request
    """
    log_info(f'making source packages for {req}...')

    with TemporaryDirectory(prefix='mmpack-src') as tmpdir:
        srctarball = SourceTarball(method='git',
                                   outdir=tmpdir,
                                   path_url=req.url,
                                   tag=req.fetch_refspec,
                                   **req.srctar_make_opts)
        num_prj = 0
        for prj in srctarball.iter_mmpack_srcs():
            job = BuildJob(req, prj.name, prj.version, prj.tarball)
            num_prj += 1
            log_info(f'{job.prj_name} {job.version} {job.srchash}')
            yield job

        log_info('... Done' if num_prj else 'No mmpack packaging')
