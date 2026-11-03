import argparse
import io
import subprocess
import threading

import pytest
from flexmock import flexmock

from borgmatic_browse import archive as module

REPO_LIST_JSON = '''
    {"archives": [
        {"archive": "dup", "name": "dup", "id": "abc123", "time": "2026-10-31T17:40:59.123456"},
        {"archive": "dup", "name": "dup", "id": "def456", "time": "2026-10-31T18:50:00.000000"}
    ]}
'''


@pytest.mark.parametrize(
    'borg_version,expected_selectors',
    (
        ('1.4.5', ('dup', 'dup')),
        # Names only form series of identically named archives starting from this version.
        ('2.0.0b10', ('dup', 'dup')),
        ('2.0.0b11', ('abc123', 'def456')),
    ),
)
def test_get_repository_archives_selects_by_id_only_if_names_might_not_be_unique(
    borg_version, expected_selectors
):
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return(
        borg_version
    )
    flexmock(module.borgmatic.borg.repo_list).should_receive('list_repository').and_return(
        REPO_LIST_JSON
    )

    archives = module.get_repository_archives(config, config['repositories'][0])

    assert tuple(archive.selector for archive in archives) == expected_selectors


def test_get_repository_archives_returns_archive_names_and_formatted_times():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.repo_list).should_receive('list_repository').and_return(
        REPO_LIST_JSON
    )

    assert module.get_repository_archives(config, config['repositories'][0]) == (
        module.Archive('abc123', 'dup', '2026-10-31 17:40'),
        module.Archive('def456', 'dup', '2026-10-31 18:50'),
    )


def test_get_archive_paths_returns_each_as_archive_path_with_metadata():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {'path': 'foo.txt', 'type': '-', 'linktarget': '', 'size': 3},
        {'path': 'bar.txt', 'type': 'l', 'linktarget': 'foo.txt', 'size': 0},
        {'path': 'etc', 'type': 'd', 'linktarget': '', 'size': 0},
    )

    assert tuple(module.get_archive_paths(config, config['repositories'][0], 'archive')) == (
        module.Archive_path('-', 'foo.txt', '', 3),
        module.Archive_path('l', 'bar.txt', 'foo.txt', 0),
        module.Archive_path('d', 'etc', '', 0),
    )


def test_get_archive_paths_reads_borg_1_symlink_target_from_linktarget():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('1.4.5')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {
            'type': 'l',
            'path': 'tree/link',
            'linktarget': 'hello.py',
            'size': 8,
            'mtime': '2026-10-31T17:50:09.044035',
        },
    )

    assert tuple(module.get_archive_paths(config, config['repositories'][0], 'archive')) == (
        module.Archive_path('l', 'tree/link', 'hello.py', 8, '2026-10-31T17:50:09.044035'),
    )


def test_get_archive_paths_reads_borg_2_symlink_target_from_target():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('2.0.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {
            'type': 'l',
            'path': 's/lnk',
            'target': 'a.txt',
            'size': 5,
            'mtime': '2026-11-01T13:13:39.316219+11:00',
        },
    )

    assert tuple(module.get_archive_paths(config, config['repositories'][0], 'archive')) == (
        module.Archive_path('l', 's/lnk', 'a.txt', 5, '2026-11-01T13:13:39.316219+11:00'),
    )


def test_get_archive_paths_prefers_linktarget_over_target_when_both_present():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('2.0.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {'type': 'l', 'path': 's/lnk', 'linktarget': 'first.txt', 'target': 'second.txt'},
    )

    (archive_path,) = module.get_archive_paths(config, config['repositories'][0], 'archive')

    assert archive_path.link_target == 'first.txt'


def test_get_archive_paths_keeps_empty_borg_1_linktarget_for_non_symlinks():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('1.4.5')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {'type': '-', 'path': 'foo.txt', 'linktarget': ''},
    )

    (archive_path,) = module.get_archive_paths(config, config['repositories'][0], 'archive')

    assert archive_path.link_target == ''


def test_get_archive_paths_gives_falsy_link_target_for_borg_2_non_symlinks():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('2.0.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {'type': '-', 'path': 'foo.txt', 'target': ''},
    )

    (archive_path,) = module.get_archive_paths(config, config['repositories'][0], 'archive')

    assert not archive_path.link_target


def test_get_archive_paths_gives_none_link_target_without_either_key():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {'type': '-', 'path': 'foo.txt'},
    )

    (archive_path,) = module.get_archive_paths(config, config['repositories'][0], 'archive')

    assert archive_path.link_target is None


def test_get_archive_paths_defaults_missing_size_to_zero():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {'path': 'foo.txt', 'type': '-', 'linktarget': ''},
    )

    assert tuple(module.get_archive_paths(config, config['repositories'][0], 'archive')) == (
        module.Archive_path('-', 'foo.txt', '', 0),
    )


def test_archive_path_defaults_mtime_to_none():
    assert module.Archive_path('-', 'foo.txt', '', 3).mtime is None
    assert module.Archive_path('-', 'foo.txt', '').mtime is None
    assert module.Archive_path('-', 'foo.txt', '').size == 0


def test_archive_path_with_mtime_keeps_raw_string():
    archive_path = module.Archive_path('-', 'foo.txt', '', 3, '2026-11-01T09:52:52.447550+11:00')

    assert archive_path.size == 3
    assert archive_path.mtime == '2026-11-01T09:52:52.447550+11:00'


def test_get_archive_paths_returns_raw_mtime_for_each_path():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').and_yield(
        {
            'path': 's/a.txt',
            'type': '-',
            'size': 3,
            'mtime': '2026-11-01T09:52:52.447550+11:00',
        },
        {'path': 'tree', 'type': 'd', 'size': 0, 'mtime': '2026-10-31T17:50:09.044035'},
        {'path': 'nomtime', 'type': '-', 'size': 1},
    )

    assert tuple(module.get_archive_paths(config, config['repositories'][0], 'archive')) == (
        module.Archive_path('-', 's/a.txt', None, 3, '2026-11-01T09:52:52.447550+11:00'),
        module.Archive_path('d', 'tree', None, 0, '2026-10-31T17:50:09.044035'),
        module.Archive_path('-', 'nomtime', None, 1, None),
    )


def test_get_archive_paths_asks_borg_for_size_and_mtime():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    captured = {}

    def fake_capture_archive_listing(*args, **kwargs):
        captured.update(kwargs)
        return iter(())

    flexmock(module.borgmatic.borg.list).should_receive('capture_archive_listing').replace_with(
        fake_capture_archive_listing
    )

    tuple(module.get_archive_paths(config, config['repositories'][0], 'archive'))

    assert captured['path_format'] == '{size}{mtime}'


def test_get_archive_file_content_with_binary_file_bails():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        extract_process := flexmock()
    )
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_return(
        (b'foo\n', b'bar\n')
    )
    extract_process.should_receive('terminate').never()
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(True)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        is None
    )


def test_get_archive_file_content_decodes_content():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        extract_process := flexmock()
    )
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_return(
        (b'foo\n', b'bar\n')
    )
    extract_process.should_receive('terminate').never()
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(False)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        == 'foo\nbar\n'
    )


def test_get_archive_file_content_with_large_file_truncates_content():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module, MAXIMUM_TOTAL_READ_SIZE=3)
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        extract_process := flexmock()
    )
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_return(
        (b'foo\n', b'bar\n')
    )
    extract_process.should_receive('terminate').once()
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(False)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        == f'foo\nbar\n\n{module.TRUNCATION_MESSAGE}'
    )


def test_get_archive_file_content_with_unicode_decode_error_does_not_raise():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        extract_process := flexmock()
    )
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_return(
        (b'foo\n', b'\xc3\n')
    )
    extract_process.should_receive('terminate').never()
    flexmock(module.binaryornot.helpers).should_receive('is_binary_string').and_return(False)

    assert (
        module.get_archive_file_content(config, config['repositories'][0], 'archive', 'etc/foo.txt')
        is None
    )


# Issue #11: piping a file to a command.


def test_stop_processes_terminates_running_extract_process_and_signals_command_process_group():
    extract_process = flexmock()
    extract_process.should_receive('poll').and_return(None)
    extract_process.should_receive('terminate').once()
    command_process = flexmock(pid=1234)
    flexmock(module.os).should_receive('killpg').with_args(1234, module.signal.SIGTERM).once()

    module.stop_processes(extract_process, command_process)


def test_stop_processes_leaves_finished_extract_process_alone():
    extract_process = flexmock()
    extract_process.should_receive('poll').and_return(0)
    extract_process.should_receive('terminate').never()
    command_process = flexmock(pid=1234)
    flexmock(module.os).should_receive('killpg').with_args(1234, module.signal.SIGTERM).once()

    module.stop_processes(extract_process, command_process)


@pytest.mark.parametrize('error', (ProcessLookupError(), PermissionError()))
def test_stop_processes_ignores_error_signalling_command_process_group(error):
    extract_process = flexmock()
    extract_process.should_receive('poll').and_return(None)
    extract_process.should_receive('terminate').once()
    command_process = flexmock(pid=1234)
    flexmock(module.os).should_receive('killpg').and_raise(error)

    module.stop_processes(extract_process, command_process)


def make_pipe_processes(output=b'', returncode=0):
    '''
    Given the command's output and exit code, mock out the extract process and the command process
    that pipe_archive_file() starts, and return them as a pair.
    '''
    extract_process = flexmock(stdout=flexmock(), stderr=flexmock())
    extract_process.stdout.should_receive('close')
    command_process = flexmock(pid=1234, stdout=io.BytesIO(output), returncode=returncode)
    command_process.should_receive('wait').and_return(returncode)
    flexmock(module.borgmatic.logger).should_receive('Log_prefix').and_return(flexmock())
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').and_return(
        extract_process
    )
    flexmock(module.subprocess).should_receive('Popen').and_return(command_process)
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_return(())

    return extract_process, command_process


def test_pipe_archive_file_extracts_file_to_stdout_with_same_arguments_as_file_content():
    config = {'repositories': [{'path': 'test.borg'}], 'local_path': 'borg2', 'remote_path': 'rb'}
    extract_process, _command_process = make_pipe_processes()
    flexmock(module.borgmatic.borg.version).should_receive('local_borg_version').and_return('3.0')
    flexmock(module.borgmatic.borg.extract).should_receive('extract_archive').with_args(
        dry_run=False,
        repository='test.borg',
        archive='archive',
        paths=('etc/foo.txt',),
        config=config,
        local_borg_version='3.0',
        global_arguments=argparse.Namespace(),
        local_path='borg2',
        remote_path='rb',
        destination_path=None,
        strip_components=None,
        extract_to_stdout=True,
    ).and_return(extract_process).once()

    module.pipe_archive_file(config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat')


def test_pipe_archive_file_runs_command_in_shell_in_new_session_reading_from_extract_stdout():
    config = {'repositories': [{'path': 'test.borg'}]}
    extract_process, command_process = make_pipe_processes()
    flexmock(module.subprocess).should_receive('Popen').with_args(
        ('/bin/sh', '-c', 'jq . | head'),
        stdin=extract_process.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    ).and_return(command_process).once()

    module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'jq . | head'
    )


def test_pipe_archive_file_closes_parent_copy_of_extract_stdout():
    config = {'repositories': [{'path': 'test.borg'}]}
    extract_process, _command_process = make_pipe_processes()
    extract_process.stdout.should_receive('close').once()

    module.pipe_archive_file(config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat')


def test_pipe_archive_file_returns_output_exit_code_and_not_truncated():
    config = {'repositories': [{'path': 'test.borg'}]}
    make_pipe_processes(output=b'hello\nworld\n', returncode=3)

    result = module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat'
    )

    assert result == module.Command_result(b'hello\nworld\n', 3, False)


def test_pipe_archive_file_with_negative_exit_code_returns_it():
    config = {'repositories': [{'path': 'test.borg'}]}
    make_pipe_processes(output=b'', returncode=-15)

    result = module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'sleep 99'
    )

    assert result.exit_code == -15


def test_pipe_archive_file_with_no_output_returns_empty_bytes():
    config = {'repositories': [{'path': 'test.borg'}]}
    make_pipe_processes(output=b'')

    result = module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'true'
    )

    assert result == module.Command_result(b'', 0, False)


def test_pipe_archive_file_drains_borg_stderr_through_log_outputs():
    config = {'repositories': [{'path': 'test.borg'}], 'borg_exit_codes': [{'code': 1}]}
    extract_process, _command_process = make_pipe_processes()
    consumed = []

    def log_outputs(**kwargs):
        assert kwargs == {
            'processes': (extract_process,),
            'exclude_stdouts': (extract_process.stdout,),
            'output_log_level': None,
            'borg_local_path': 'borg',
            'borg_exit_codes': [{'code': 1}],
        }
        consumed.append('started')
        yield b'ignored'
        consumed.append('finished')

    flexmock(module.borgmatic.execute).should_receive('log_outputs').replace_with(log_outputs)

    module.pipe_archive_file(config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat')

    assert consumed == ['started', 'finished']


def test_pipe_archive_file_calls_on_start_with_both_processes():
    config = {'repositories': [{'path': 'test.borg'}]}
    extract_process, command_process = make_pipe_processes()
    started = []

    module.pipe_archive_file(
        config,
        config['repositories'][0],
        'archive',
        'etc/foo.txt',
        'cat',
        on_start=lambda *processes: started.append(processes),
    )

    assert started == [(extract_process, command_process)]


def test_pipe_archive_file_with_command_that_cannot_start_terminates_extract_and_raises():
    config = {'repositories': [{'path': 'test.borg'}]}
    extract_process, _command_process = make_pipe_processes()
    flexmock(module.subprocess).should_receive('Popen').and_raise(OSError('no shell'))
    extract_process.should_receive('terminate').once()
    flexmock(module.borgmatic.execute).should_receive('log_outputs').never()

    with pytest.raises(OSError, match='no shell'):
        module.pipe_archive_file(config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat')


def test_pipe_archive_file_with_output_over_maximum_keeps_first_bytes_and_stops_processes():
    config = {'repositories': [{'path': 'test.borg'}]}
    extract_process, command_process = make_pipe_processes(output=b'0123456789')
    flexmock(module, MAXIMUM_COMMAND_OUTPUT_SIZE=5)
    flexmock(module).should_receive('stop_processes').with_args(
        extract_process, command_process
    ).once()

    result = module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'yes'
    )

    assert result.output == b'01234'
    assert result.truncated is True


def test_pipe_archive_file_with_output_exactly_maximum_is_not_truncated():
    config = {'repositories': [{'path': 'test.borg'}]}
    make_pipe_processes(output=b'01234')
    flexmock(module, MAXIMUM_COMMAND_OUTPUT_SIZE=5)
    flexmock(module).should_receive('stop_processes').never()

    result = module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat'
    )

    assert result == module.Command_result(b'01234', 0, False)


def test_pipe_archive_file_ignores_borg_failure_after_truncating_output():
    config = {'repositories': [{'path': 'test.borg'}]}
    make_pipe_processes(output=b'0123456789')
    flexmock(module, MAXIMUM_COMMAND_OUTPUT_SIZE=5)
    flexmock(module).should_receive('stop_processes')
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_raise(
        subprocess.CalledProcessError(-15, 'borg extract', output='terminated')
    )

    result = module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'yes'
    )

    assert result.truncated is True


def test_pipe_archive_file_ignores_borg_broken_pipe_when_command_stops_reading_early():
    config = {'repositories': [{'path': 'test.borg'}]}
    make_pipe_processes(output=b'first line\n')
    flexmock(module).should_receive('stop_processes').never()
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_raise(
        subprocess.CalledProcessError(
            2, 'borg extract', output=f'Traceback...\n{module.BROKEN_PIPE_TEXT}: [Errno 32]'
        )
    )

    result = module.pipe_archive_file(
        config, config['repositories'][0], 'archive', 'etc/foo.txt', 'head -n1'
    )

    assert result == module.Command_result(b'first line\n', 0, False)


def test_pipe_archive_file_with_other_borg_failure_stops_processes_and_raises():
    config = {'repositories': [{'path': 'test.borg'}]}
    extract_process, command_process = make_pipe_processes()
    flexmock(module).should_receive('stop_processes').with_args(
        extract_process, command_process
    ).once()
    flexmock(module.borgmatic.execute).should_receive('log_outputs').and_raise(
        subprocess.CalledProcessError(2, 'borg extract', output='Repository does not exist.')
    )

    with pytest.raises(subprocess.CalledProcessError):
        module.pipe_archive_file(config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat')


def test_pipe_archive_file_reads_command_output_in_background_thread():
    config = {'repositories': [{'path': 'test.borg'}]}
    _extract_process, command_process = make_pipe_processes()
    reader_threads = []

    class Recording_stdout(io.BytesIO):
        def read(self, size=-1):
            reader_threads.append(threading.current_thread())
            return super().read(size)

    command_process.stdout = Recording_stdout(b'hello')

    module.pipe_archive_file(config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat')

    assert reader_threads
    assert all(thread is not threading.main_thread() for thread in reader_threads)


def test_pipe_archive_file_waits_for_command_to_exit():
    config = {'repositories': [{'path': 'test.borg'}]}
    _extract_process, command_process = make_pipe_processes()
    command_process.should_receive('wait').once().and_return(0)

    module.pipe_archive_file(config, config['repositories'][0], 'archive', 'etc/foo.txt', 'cat')
