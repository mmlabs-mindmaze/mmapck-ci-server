project('mmpack-ci-server', 'c',
        version: '0.0.1',
        license: 'GPL3',
        meson_version: '>= 0.49',
)

mmpack_ci_server_files = files(
    'src/builder.py',
    'src/buildjob.py',
    'src/common.py',
    'src/eventsrc_gerrit.py',
    'src/eventsrc.py',
    'src/gerrit.py',
    'src/jobscheduler.py',
    'src/repository.py',
)

mmpack_ci_server_files += configure_file(
    output: 'main.py',
    input: files('src/main.py.in'),
    configuration: configuration_data({
	'sysconfdir': get_option('prefix') / get_option('sysconfdir'),
	'localstatedir': get_option('prefix') / get_option('localstatedir'),
    }),
)

install_data(mmpack_ci_server_files,
    install_dir : get_option('datadir') / 'mmpack-ci-server',
)


#
# dev targets
#
pylint = find_program(['pylint3', 'pylint'], required : false)
if pylint.found()
    run_target('pylint',
        command : [
            pylint,
            '--jobs=0',
            '--disable=locally-disabled',
	    '--ignore=gerrit.py',
            '--rcfile', files('pylint-config'),
	    mmpack_ci_server_files
        ],
    )
endif # pylint

pycodestyle = find_program('pycodestyle', required : false)
if pycodestyle.found()
    run_target('pycodestyle',
        command : [
            pycodestyle,
            '--show-source',
            'src',
        ],
    )
endif # pycodestyle
