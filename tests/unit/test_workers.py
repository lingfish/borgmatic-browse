import subprocess

import pytest
from flexmock import flexmock

from borgmatic_browse import workers as module


def test_add_repository_archives_publishes_for_each_archive():
    foo = module.borgmatic_browse.archive.Archive('1', 'foo', '2026-10-31 17:40')
    bar = module.borgmatic_browse.archive.Archive('2', 'bar', '2026-10-31 18:50')
    flexmock(module.borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (foo, bar)
    )
    archive_loaded = flexmock()
    archive_loaded.should_receive('publish').with_args(bar).once()  # Reversed order.
    archive_loaded.should_receive('publish').with_args(foo).once()
    archive_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.add_repository_archives.__wrapped__(
        browse_app=flexmock(),
        archive_loaded=archive_loaded,
        config=flexmock(),
        repository=flexmock(),
    )


def test_directory_defaults_to_zero_size():
    assert module.Directory().size == 0


def test_directory_with_size_and_contents_sets_both():
    directory = module.Directory({'foo': module.Directory()}, size=3)

    assert directory.size == 3
    assert directory == {'foo': {}}


def test_directory_sizes_are_independent_per_instance():
    directory = module.Directory()
    other_directory = module.Directory()

    directory.size += 3

    assert directory.size == 3
    assert other_directory.size == 0


def test_directory_defaults_to_no_mtime():
    assert module.Directory().mtime is None


def test_directory_with_mtime_sets_it():
    assert module.Directory(size=3, mtime='2026-10-31T17:50:09').mtime == '2026-10-31T17:50:09'


def test_directory_mtimes_are_independent_per_instance():
    directory = module.Directory()
    other_directory = module.Directory()

    directory.mtime = '2026-10-31T17:50:09'

    assert other_directory.mtime is None


def test_record_path_sets_file_path_in_filesystem_hierarchy():
    archive_path = flexmock(path_type='-', file_path='foo/bar/baz.txt', size=3)
    quux_path = flexmock(size=5)
    hierarchy = {
        'foo': module.Directory(
            {'bar': module.Directory({'quux.txt': quux_path}), 'empty': module.Directory()}
        )
    }

    module.record_path(
        archive_path=archive_path, hierarchy=hierarchy, path_components=('foo', 'bar', 'baz.txt')
    )

    assert hierarchy == {
        'foo': {'bar': {'quux.txt': quux_path, 'baz.txt': archive_path}, 'empty': {}}
    }
    assert hierarchy['foo'].size == 3
    assert hierarchy['foo']['bar'].size == 3


def test_record_path_sets_directory_path_in_filesystem_hierarchy():
    archive_path = flexmock(path_type='d', file_path='foo/bar/baz', size=0, mtime=None)
    quux_path = flexmock(size=5)
    hierarchy = {
        'foo': module.Directory(
            {'bar': module.Directory({'quux.txt': quux_path}), 'empty': module.Directory()}
        )
    }

    module.record_path(
        archive_path=archive_path, hierarchy=hierarchy, path_components=('foo', 'bar', 'baz')
    )

    assert hierarchy == {'foo': {'bar': {'quux.txt': quux_path, 'baz': {}}, 'empty': {}}}
    assert hierarchy['foo']['bar']['baz'].size == 0


def test_record_path_sets_mtime_on_new_directory_but_not_its_parents():
    archive_path = module.borgmatic_browse.archive.Archive_path(
        'd', 'foo/bar', '', 0, '2026-10-31T17:50:09'
    )
    hierarchy = {}

    module.record_path(archive_path, hierarchy, ('foo', 'bar'))

    assert hierarchy['foo']['bar'].mtime == '2026-10-31T17:50:09'
    assert hierarchy['foo'].mtime is None


def test_record_path_sets_mtime_on_existing_directory_keeping_children_and_size():
    baz_path = module.borgmatic_browse.archive.Archive_path('-', 'foo/bar/baz.txt', '', 3)
    hierarchy = {}
    module.record_path(baz_path, hierarchy, ('foo', 'bar', 'baz.txt'))
    assert hierarchy['foo']['bar'].mtime is None

    module.record_path(
        module.borgmatic_browse.archive.Archive_path('d', 'foo/bar', '', 0, '2026-10-31T17:50:09'),
        hierarchy,
        ('foo', 'bar'),
    )

    assert hierarchy['foo']['bar'] == {'baz.txt': baz_path}
    assert hierarchy['foo']['bar'].size == 3
    assert hierarchy['foo']['bar'].mtime == '2026-10-31T17:50:09'
    assert hierarchy['foo'].size == 3
    assert hierarchy['foo'].mtime is None


def test_record_path_with_directory_without_mtime_leaves_mtime_none():
    hierarchy = {}

    module.record_path(
        module.borgmatic_browse.archive.Archive_path('d', 'foo', '', 0), hierarchy, ('foo',)
    )

    assert hierarchy['foo'].mtime is None


def test_record_path_with_child_does_not_alter_parent_mtime():
    hierarchy = {}
    module.record_path(
        module.borgmatic_browse.archive.Archive_path('d', 'foo', '', 0, '2026-10-31T17:50:09'),
        hierarchy,
        ('foo',),
    )

    module.record_path(
        module.borgmatic_browse.archive.Archive_path(
            '-', 'foo/baz.txt', '', 3, '2026-11-01T09:52:52'
        ),
        hierarchy,
        ('foo', 'baz.txt'),
    )
    module.record_path(
        module.borgmatic_browse.archive.Archive_path('d', 'foo/sub', '', 0, '2026-11-02T09:52:52'),
        hierarchy,
        ('foo', 'sub'),
    )

    assert hierarchy['foo'].mtime == '2026-10-31T17:50:09'


def test_get_paths_lists_directory_contents():
    baz_path = module.borgmatic_browse.archive.Archive_path('-', 'foo/bar/baz.txt', '', 3)
    hierarchy = {
        'foo': module.Directory(
            {'bar': module.Directory({'baz.txt': baz_path, 'other': module.Directory()})}
        ),
        'nope': module.Directory(),
    }

    assert tuple(module.get_paths(hierarchy, ('foo', 'bar'))) == (
        baz_path,
        module.borgmatic_browse.archive.Archive_path('d', 'foo/bar/other', '', 0),
    )


def test_get_paths_with_full_path_components_lists_directory_contents():
    baz_path = module.borgmatic_browse.archive.Archive_path('-', 'etc/foo/bar/baz.txt', '', 3)
    hierarchy = {
        'foo': module.Directory(
            {'bar': module.Directory({'baz.txt': baz_path, 'other': module.Directory()})}
        ),
        'nope': module.Directory(),
    }

    assert tuple(module.get_paths(hierarchy, ('foo', 'bar'), ('etc', 'foo', 'bar'))) == (
        baz_path,
        module.borgmatic_browse.archive.Archive_path('d', 'etc/foo/bar/other', '', 0),
    )


def test_get_paths_lists_empty_directory_contents():
    baz_path = module.borgmatic_browse.archive.Archive_path('-', 'etc/foo/bar/baz.txt', '', 3)
    hierarchy = {
        'foo': module.Directory(
            {'bar': module.Directory({'baz.txt': baz_path, 'other': module.Directory()})}
        ),
        'nope': module.Directory(),
    }

    assert (
        tuple(module.get_paths(hierarchy, ('foo', 'bar', 'other'), ('etc', 'foo', 'bar', 'other')))
        == ()
    )


def test_get_paths_directory_archive_paths_carry_mtime():
    hierarchy = {
        'foo': module.Directory(
            {
                'dated': module.Directory(size=4, mtime='2026-10-31T17:50:09'),
                'undated': module.Directory(),
            }
        )
    }

    assert tuple(module.get_paths(hierarchy, ('foo',))) == (
        module.borgmatic_browse.archive.Archive_path(
            'd', 'foo/dated', '', 4, '2026-10-31T17:50:09'
        ),
        module.borgmatic_browse.archive.Archive_path('d', 'foo/undated', '', 0, None),
    )


def test_get_paths_leaves_file_archive_paths_untouched():
    baz_path = module.borgmatic_browse.archive.Archive_path(
        '-', 'foo/baz.txt', '', 3, '2026-10-31T17:50:09'
    )
    hierarchy = {'foo': module.Directory({'baz.txt': baz_path})}

    assert tuple(module.get_paths(hierarchy, ('foo',))) == (baz_path,)


def test_get_paths_with_unknown_file_raises():
    hierarchy = {'foo': module.Directory({'other': module.Directory()})}

    with pytest.raises(ValueError):
        tuple(module.get_paths(hierarchy, ('foo', 'bar.txt')))


def test_get_paths_with_unknown_directory_raises():
    hierarchy = {'foo': module.Directory({'other': module.Directory()})}

    with pytest.raises(ValueError):
        tuple(module.get_paths(hierarchy, ('foo', 'bar', 'baz')))


def test_get_path_size_returns_cumulative_directory_size():
    hierarchy = {
        'foo': module.Directory(
            {
                'bar': module.Directory(
                    {
                        'baz.txt': module.borgmatic_browse.archive.Archive_path(
                            '-', 'foo/bar/baz.txt', '', 3
                        )
                    },
                    size=3,
                )
            },
            size=3,
        )
    }

    assert module.get_path_size(hierarchy, ('foo',)) == 3
    assert module.get_path_size(hierarchy, ('foo', 'bar')) == 3


def test_get_path_size_returns_file_size():
    archive_path = module.borgmatic_browse.archive.Archive_path('-', 'foo.txt', '', 7)
    hierarchy = {'foo.txt': archive_path}

    assert module.get_path_size(hierarchy, ('foo.txt',)) == 7


def test_get_path_size_with_no_path_components_returns_whole_hierarchy_size():
    hierarchy = {
        'foo.txt': module.borgmatic_browse.archive.Archive_path('-', 'foo.txt', '', 7),
        'etc': module.Directory(size=3),
    }

    assert module.get_path_size(hierarchy, ()) == 10


def test_get_path_size_with_unknown_path_returns_zero():
    hierarchy = {'foo': module.Directory()}

    assert module.get_path_size(hierarchy, ('foo', 'bar')) == 0


def test_get_path_size_with_file_in_path_returns_zero():
    archive_path = module.borgmatic_browse.archive.Archive_path('-', 'foo.txt', '', 7)

    assert module.get_path_size({'foo.txt': archive_path}, ('foo.txt', 'bar')) == 0


def test_get_path_mtime_returns_directory_mtime():
    hierarchy = {
        'foo': module.Directory(
            {'bar': module.Directory(mtime='2026-10-31T17:50:09')}, mtime='2026-10-30T08:00:00'
        )
    }

    assert module.get_path_mtime(hierarchy, ('foo',)) == '2026-10-30T08:00:00'
    assert module.get_path_mtime(hierarchy, ('foo', 'bar')) == '2026-10-31T17:50:09'


def test_get_path_mtime_returns_file_mtime():
    archive_path = module.borgmatic_browse.archive.Archive_path(
        '-', 'foo.txt', '', 7, '2026-11-01T09:52:52.447550+11:00'
    )

    assert (
        module.get_path_mtime({'foo.txt': archive_path}, ('foo.txt',))
        == '2026-11-01T09:52:52.447550+11:00'
    )


def test_get_path_mtime_with_unknown_path_returns_none():
    hierarchy = {'foo': module.Directory()}

    assert module.get_path_mtime(hierarchy, ('foo', 'bar')) is None
    assert module.get_path_mtime(hierarchy, ('nope',)) is None


def test_get_path_mtime_with_file_in_path_returns_none():
    archive_path = module.borgmatic_browse.archive.Archive_path(
        '-', 'foo.txt', '', 7, '2026-10-31T17:50:09'
    )

    assert module.get_path_mtime({'foo.txt': archive_path}, ('foo.txt', 'bar')) is None


def test_get_path_mtime_with_no_path_components_returns_none():
    assert module.get_path_mtime({'foo': module.Directory(mtime='2026-10-31T17:50:09')}, ()) is None


def test_get_path_mtime_with_no_mtime_returns_none():
    archive_path = module.borgmatic_browse.archive.Archive_path('-', 'foo.txt', '', 7)
    hierarchy = {'foo.txt': archive_path, 'etc': module.Directory()}

    assert module.get_path_mtime(hierarchy, ('foo.txt',)) is None
    assert module.get_path_mtime(hierarchy, ('etc',)) is None


def test_load_archive_paths_publishes_a_batch_of_archive_paths():
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_paths').and_yield(
        'foo.txt', 'bar.txt'
    )
    path_loaded = flexmock()
    path_loaded.should_receive('publish').with_args(('foo.txt', 'bar.txt')).once()
    path_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.load_archive_paths.__wrapped__(
        browse_app=flexmock(),
        path_loaded=path_loaded,
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
    )


def test_load_archive_paths_publishes_full_batches():
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_paths').and_yield(
        *range(module.BATCH_SIZE + 1)
    )
    path_loaded = flexmock()
    path_loaded.should_receive('publish').with_args(tuple(range(module.BATCH_SIZE))).once()
    path_loaded.should_receive('publish').with_args((module.BATCH_SIZE,)).once()
    path_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.load_archive_paths.__wrapped__(
        browse_app=flexmock(),
        path_loaded=path_loaded,
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
    )


def test_load_file_preview_publishes_file_contents():
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_file_content').and_return(
        'hi'
    )
    file_preview_loaded = flexmock()
    file_preview_loaded.should_receive('publish').with_args('hi').once()

    module.load_file_preview.__wrapped__(
        browse_app=flexmock(),
        file_preview_loaded=file_preview_loaded,
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        file_path='foo/bar/baz.txt',
    )


FAILURES = (
    subprocess.CalledProcessError(13, 'borg list', output='Repository /x does not exist.'),
    OSError('no such file'),
    ValueError('bad value'),
)


def failure_detail(error):
    '''
    Given an exception, return the detail that a failed worker should report for it.
    '''
    return getattr(error, 'output', None) or str(error)


def make_browse_app(detail):
    '''
    Given the expected error detail, return a fake Browse_app that expects exactly one error
    notification whose message includes the literal detail and that isn't parsed as markup.
    '''
    browse_app = flexmock()
    browse_app.should_receive('notify').replace_with(
        lambda message, severity=None, markup=True: (
            None if severity == 'error' and markup is False and detail in message else 1 / 0
        )
    ).once()

    return browse_app


@pytest.mark.parametrize('error', FAILURES)
def test_add_repository_archives_with_failure_notifies_logs_and_publishes_loading_done(error):
    flexmock(module.borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        error
    )
    flexmock(module.logger).should_receive('error').once()
    archive_loaded = flexmock()
    archive_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.add_repository_archives.__wrapped__(
        browse_app=make_browse_app(failure_detail(error)),
        archive_loaded=archive_loaded,
        config={},
        repository=flexmock(),
    )


def test_add_repository_archives_with_empty_output_failure_reports_str_of_error():
    error = subprocess.CalledProcessError(13, 'borg list', output='')
    flexmock(module.borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        error
    )
    flexmock(module.logger).should_receive('error').once()
    archive_loaded = flexmock()
    archive_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.add_repository_archives.__wrapped__(
        browse_app=make_browse_app(str(error)),
        archive_loaded=archive_loaded,
        config={},
        repository=flexmock(),
    )


def test_add_repository_archives_with_failure_does_not_escape_markup_in_notification():
    error = subprocess.CalledProcessError(13, 'borg list', output='bad [/nope] path')
    flexmock(module.borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        error
    )
    flexmock(module.logger).should_receive('error').once()
    archive_loaded = flexmock()
    archive_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.add_repository_archives.__wrapped__(
        browse_app=make_browse_app('bad [/nope] path'),
        archive_loaded=archive_loaded,
        config={},
        repository=flexmock(),
    )


@pytest.mark.parametrize('error', FAILURES)
def test_load_archive_paths_with_failure_publishes_partial_batch_then_loading_done(error):
    def failing_paths(*args, **kwargs):
        yield 'foo.txt'
        raise error

    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_paths').replace_with(
        failing_paths
    )
    flexmock(module.logger).should_receive('error').once()
    path_loaded = flexmock()
    path_loaded.should_receive('publish').with_args(('foo.txt',)).once().ordered()
    path_loaded.should_receive('publish').with_args(module.LOADING_DONE).once().ordered()

    module.load_archive_paths.__wrapped__(
        browse_app=make_browse_app(failure_detail(error)),
        path_loaded=path_loaded,
        config={},
        repository=flexmock(),
        archive_name='archive',
    )


@pytest.mark.parametrize('error', FAILURES)
def test_load_file_preview_with_failure_notifies_logs_and_publishes_loading_failed(error):
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_file_content').and_raise(
        error
    )
    flexmock(module.logger).should_receive('error').once()
    file_preview_loaded = flexmock()
    file_preview_loaded.should_receive('publish').with_args(module.LOADING_FAILED).once()

    module.load_file_preview.__wrapped__(
        browse_app=make_browse_app(failure_detail(error)),
        file_preview_loaded=file_preview_loaded,
        config={},
        repository=flexmock(),
        archive_name='archive',
        file_path='foo/bar/baz.txt',
    )


BORG_PASSPHRASE_ERROR = (
    'Passphrase supplied in BORG_PASSPHRASE, by BORG_PASSCOMMAND or via BORG_PASSPHRASE_FD is '
    'incorrect.'
)


def make_capturing_browse_app(notifications):
    '''
    Given a list, return a fake Browse_app that appends each (message, severity) notification to it,
    provided that the notification isn't parsed as markup.
    '''
    browse_app = flexmock()
    browse_app.should_receive('notify').replace_with(
        lambda message, severity=None, markup=True: (
            notifications.append((message, severity)) if markup is False else 1 / 0
        )
    )

    return browse_app


@pytest.mark.parametrize(
    'detail',
    ('x[$var]', 'back\\', 'end\\[', 'a\\[b]', 'bad[/name]', '[bold]x', '[/]', 'plain'),
)
def test_report_loading_error_notifies_with_literal_message_and_markup_disabled(detail):
    notifications = []
    flexmock(module.logger).should_receive('error').with_args(
        f'Error listing repository: {detail}'
    ).once()
    browse_app = flexmock()
    browse_app.should_receive('notify').replace_with(
        lambda *args, **kwargs: notifications.append((args, kwargs))
    )

    module.report_loading_error(
        browse_app,
        'Error listing repository',
        subprocess.CalledProcessError(13, 'borg list', output=detail),
        {},
    )

    assert notifications == [
        ((f'Error listing repository: {detail}',), {'severity': 'error', 'markup': False})
    ]


def test_report_loading_error_returns_the_message_it_logged_and_notified():
    notifications = []
    flexmock(module.logger).should_receive('error')

    message = module.report_loading_error(
        make_capturing_browse_app(notifications),
        'Error listing repository',
        subprocess.CalledProcessError(13, 'borg list', output='Repository /x does not exist.'),
        {},
    )

    assert message == 'Error listing repository: Repository /x does not exist.'
    assert notifications == [(message, 'error')]


def test_report_loading_error_without_output_returns_message_with_exception_text():
    flexmock(module.logger).should_receive('error')

    message = module.report_loading_error(
        flexmock(notify=lambda *args, **kwargs: None),
        'Error piping foo to a command',
        OSError('no such file'),
        {},
    )

    assert message == 'Error piping foo to a command: no such file'


def test_report_loading_error_with_empty_passphrase_returns_substituted_message():
    flexmock(module.logger).should_receive('error')

    message = module.report_loading_error(
        flexmock(notify=lambda *args, **kwargs: None),
        'Error listing repository',
        subprocess.CalledProcessError(52, 'borg list', output=BORG_PASSPHRASE_ERROR),
        {'encryption_passphrase': ''},
    )

    assert message == f'Error listing repository: {module.NO_PASSPHRASE_MESSAGE}'


def test_no_passphrase_message_mentions_the_configuration_option():
    assert 'encryption_passphrase' in module.NO_PASSPHRASE_MESSAGE


def test_report_loading_error_with_empty_passphrase_and_borg_passphrase_error_explains_it():
    notifications = []
    flexmock(module.logger).should_receive('error').with_args(
        f'Error listing repository: {module.NO_PASSPHRASE_MESSAGE}'
    ).once()

    module.report_loading_error(
        make_capturing_browse_app(notifications),
        'Error listing repository',
        subprocess.CalledProcessError(52, 'borg list', output=BORG_PASSPHRASE_ERROR),
        {'encryption_passphrase': ''},
    )

    assert notifications == [
        (
            f'Error listing repository: {module.NO_PASSPHRASE_MESSAGE}',
            'error',
        )
    ]
    assert 'Passphrase supplied in' not in notifications[0][0]


def test_report_loading_error_with_empty_passphrase_and_other_error_keeps_borg_message():
    notifications = []
    flexmock(module.logger).should_receive('error').with_args(
        'Error listing repository: Repository /x does not exist.'
    ).once()

    module.report_loading_error(
        make_capturing_browse_app(notifications),
        'Error listing repository',
        subprocess.CalledProcessError(13, 'borg list', output='Repository /x does not exist.'),
        {'encryption_passphrase': ''},
    )

    assert notifications == [('Error listing repository: Repository /x does not exist.', 'error')]


@pytest.mark.parametrize('config', ({'encryption_passphrase': 'secret'}, {}))
def test_report_loading_error_without_empty_passphrase_keeps_borg_passphrase_message(config):
    notifications = []
    flexmock(module.logger).should_receive('error').with_args(
        f'Error listing repository: {BORG_PASSPHRASE_ERROR}'
    ).once()

    module.report_loading_error(
        make_capturing_browse_app(notifications),
        'Error listing repository',
        subprocess.CalledProcessError(52, 'borg list', output=BORG_PASSPHRASE_ERROR),
        config,
    )

    assert notifications == [(f'Error listing repository: {BORG_PASSPHRASE_ERROR}', 'error')]


def test_add_repository_archives_with_empty_passphrase_and_borg_passphrase_error_explains_it():
    notifications = []
    flexmock(module.borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        subprocess.CalledProcessError(52, 'borg', output=BORG_PASSPHRASE_ERROR)
    )
    flexmock(module.logger).should_receive('error').once()
    archive_loaded = flexmock()
    archive_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.add_repository_archives.__wrapped__(
        browse_app=make_capturing_browse_app(notifications),
        archive_loaded=archive_loaded,
        config={'encryption_passphrase': ''},
        repository=flexmock(),
    )

    assert notifications == [
        (
            f'Error listing repository: {module.NO_PASSPHRASE_MESSAGE}',
            'error',
        )
    ]


def test_load_archive_paths_with_empty_passphrase_and_borg_passphrase_error_explains_it():
    notifications = []
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_paths').and_raise(
        subprocess.CalledProcessError(52, 'borg', output=BORG_PASSPHRASE_ERROR)
    )
    flexmock(module.logger).should_receive('error').once()
    path_loaded = flexmock()
    path_loaded.should_receive('publish').with_args(module.LOADING_DONE).once()

    module.load_archive_paths.__wrapped__(
        browse_app=make_capturing_browse_app(notifications),
        path_loaded=path_loaded,
        config={'encryption_passphrase': ''},
        repository=flexmock(),
        archive_name='archive',
    )

    assert notifications == [
        (
            f'Error listing archive archive: {module.NO_PASSPHRASE_MESSAGE}',
            'error',
        )
    ]


def test_load_file_preview_with_empty_passphrase_and_borg_passphrase_error_explains_it():
    notifications = []
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_file_content').and_raise(
        subprocess.CalledProcessError(52, 'borg', output=BORG_PASSPHRASE_ERROR)
    )
    flexmock(module.logger).should_receive('error').once()
    file_preview_loaded = flexmock()
    file_preview_loaded.should_receive('publish').with_args(module.LOADING_FAILED).once()

    module.load_file_preview.__wrapped__(
        browse_app=make_capturing_browse_app(notifications),
        file_preview_loaded=file_preview_loaded,
        config={'encryption_passphrase': ''},
        repository=flexmock(),
        archive_name='archive',
        file_path='foo/bar/baz.txt',
    )

    assert notifications == [
        (
            f'Error loading foo/bar/baz.txt: {module.NO_PASSPHRASE_MESSAGE}',
            'error',
        )
    ]


def test_loading_failed_is_distinct_from_none_and_loading_done():
    assert module.LOADING_FAILED is not None
    assert module.LOADING_FAILED is not module.LOADING_DONE


def make_recording_signal():
    '''
    Return a fake signal that starts out not failed, along with a list that records the (data,
    failed) pair for each publish, where failed is the signal's failed flag at that moment.
    '''
    published = []
    signal = flexmock(failed=False)
    signal.should_receive('publish').replace_with(
        lambda data: published.append((data, signal.failed))
    )

    return signal, published


@pytest.mark.parametrize('error', FAILURES)
def test_add_repository_archives_with_failure_marks_signal_failed_before_publishing(error):
    flexmock(module.borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        error
    )
    flexmock(module.logger).should_receive('error')
    archive_loaded, published = make_recording_signal()

    module.add_repository_archives.__wrapped__(
        browse_app=flexmock(notify=lambda *args, **kwargs: None),
        archive_loaded=archive_loaded,
        config={},
        repository=flexmock(),
    )

    assert archive_loaded.failed is True
    assert published == [(module.LOADING_DONE, True)]


@pytest.mark.parametrize('error', FAILURES)
def test_load_archive_paths_with_failure_marks_signal_failed_before_publishing(error):
    def failing_paths(*args, **kwargs):
        yield 'foo.txt'
        raise error

    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_paths').replace_with(
        failing_paths
    )
    flexmock(module.logger).should_receive('error')
    path_loaded, published = make_recording_signal()

    module.load_archive_paths.__wrapped__(
        browse_app=flexmock(notify=lambda *args, **kwargs: None),
        path_loaded=path_loaded,
        config={},
        repository=flexmock(),
        archive_name='archive',
    )

    assert path_loaded.failed is True
    assert published == [(('foo.txt',), True), (module.LOADING_DONE, True)]


@pytest.mark.parametrize('error', FAILURES)
def test_load_file_preview_with_failure_marks_signal_failed_before_publishing(error):
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_file_content').and_raise(
        error
    )
    flexmock(module.logger).should_receive('error')
    file_preview_loaded, published = make_recording_signal()

    module.load_file_preview.__wrapped__(
        browse_app=flexmock(notify=lambda *args, **kwargs: None),
        file_preview_loaded=file_preview_loaded,
        config={},
        repository=flexmock(),
        archive_name='archive',
        file_path='foo.txt',
    )

    assert file_preview_loaded.failed is True
    assert published == [(module.LOADING_FAILED, True)]


def test_add_repository_archives_without_failure_leaves_signal_not_failed():
    archive = module.borgmatic_browse.archive.Archive('1', 'foo', '2026-10-31 17:40')
    flexmock(module.borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (archive,)
    )
    archive_loaded, published = make_recording_signal()

    module.add_repository_archives.__wrapped__(
        browse_app=flexmock(),
        archive_loaded=archive_loaded,
        config={},
        repository=flexmock(),
    )

    assert archive_loaded.failed is False
    assert published == [(archive, False), (module.LOADING_DONE, False)]


def test_load_archive_paths_without_failure_leaves_signal_not_failed():
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_paths').and_yield(
        'foo.txt'
    )
    path_loaded, published = make_recording_signal()

    module.load_archive_paths.__wrapped__(
        browse_app=flexmock(),
        path_loaded=path_loaded,
        config={},
        repository=flexmock(),
        archive_name='archive',
    )

    assert path_loaded.failed is False
    assert published == [(('foo.txt',), False), (module.LOADING_DONE, False)]


def test_load_file_preview_without_failure_leaves_signal_not_failed():
    flexmock(module.borgmatic_browse.archive).should_receive('get_archive_file_content').and_return(
        'hi'
    )
    file_preview_loaded, published = make_recording_signal()

    module.load_file_preview.__wrapped__(
        browse_app=flexmock(),
        file_preview_loaded=file_preview_loaded,
        config={},
        repository=flexmock(),
        archive_name='archive',
        file_path='foo.txt',
    )

    assert file_preview_loaded.failed is False
    assert published == [('hi', False)]


# Issue #11: piping a file to a command.


def test_command_output_loaded_defaults():
    assert module.Command_output_loaded.failed is False
    assert module.Command_output_loaded.cancelled is False
    assert module.Command_output_loaded.processes == ()
    assert module.Command_output_loaded.error_message is None


def make_command_output_loaded():
    return flexmock(failed=False, cancelled=False, processes=(), error_message=None)


def test_pipe_file_publishes_command_result():
    result = flexmock()
    flexmock(module.borgmatic_browse.archive).should_receive('pipe_archive_file').and_return(result)
    command_output_loaded = make_command_output_loaded()
    command_output_loaded.should_receive('publish').with_args(result).once()

    module.pipe_file.__wrapped__(
        browse_app=flexmock(),
        command_output_loaded=command_output_loaded,
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        file_path='foo/bar/baz.txt',
        command='jq .',
    )


def test_pipe_file_passes_arguments_to_pipe_archive_file_with_on_start_callback():
    config = flexmock()
    repository = flexmock()
    captured = {}

    def pipe_archive_file(*args, **kwargs):
        captured['args'] = args
        captured['on_start'] = kwargs.pop('on_start')
        captured['kwargs'] = kwargs

        return flexmock()

    flexmock(module.borgmatic_browse.archive).should_receive('pipe_archive_file').replace_with(
        pipe_archive_file
    )
    command_output_loaded = make_command_output_loaded()
    command_output_loaded.should_receive('publish')

    module.pipe_file.__wrapped__(
        browse_app=flexmock(),
        command_output_loaded=command_output_loaded,
        config=config,
        repository=repository,
        archive_name='archive',
        file_path='foo/bar/baz.txt',
        command='jq .',
    )

    assert captured['args'] == (config, repository, 'archive', 'foo/bar/baz.txt', 'jq .')
    assert captured['kwargs'] == {}
    assert callable(captured['on_start'])


def test_pipe_file_on_start_records_processes_without_stopping_them():
    processes = (flexmock(), flexmock())
    flexmock(module.borgmatic_browse.archive).should_receive('stop_processes').never()

    def pipe_archive_file(*args, on_start, **kwargs):
        on_start(*processes)

        return flexmock()

    flexmock(module.borgmatic_browse.archive).should_receive('pipe_archive_file').replace_with(
        pipe_archive_file
    )
    command_output_loaded = make_command_output_loaded()
    command_output_loaded.should_receive('publish')

    module.pipe_file.__wrapped__(
        browse_app=flexmock(),
        command_output_loaded=command_output_loaded,
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        file_path='foo.txt',
        command='cat',
    )

    assert command_output_loaded.processes == processes


def test_pipe_file_on_start_stops_processes_right_away_if_already_cancelled():
    processes = (flexmock(), flexmock())
    flexmock(module.borgmatic_browse.archive).should_receive('stop_processes').with_args(
        *processes
    ).once()

    def pipe_archive_file(*args, on_start, **kwargs):
        on_start(*processes)

        return flexmock()

    flexmock(module.borgmatic_browse.archive).should_receive('pipe_archive_file').replace_with(
        pipe_archive_file
    )
    command_output_loaded = make_command_output_loaded()
    command_output_loaded.cancelled = True
    command_output_loaded.should_receive('publish')

    module.pipe_file.__wrapped__(
        browse_app=flexmock(),
        command_output_loaded=command_output_loaded,
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        file_path='foo.txt',
        command='cat',
    )

    assert command_output_loaded.processes == processes


@pytest.mark.parametrize('error', FAILURES)
def test_pipe_file_with_failure_reports_error_and_publishes_loading_failed(error):
    config = {}
    browse_app = flexmock()
    flexmock(module.borgmatic_browse.archive).should_receive('pipe_archive_file').and_raise(error)
    flexmock(module).should_receive('report_loading_error').with_args(
        browse_app, 'Error piping foo/bar/baz.txt to a command', error, config
    ).and_return('Error piping foo/bar/baz.txt to a command: the detail').once()
    command_output_loaded = make_command_output_loaded()
    seen_error_messages = []
    command_output_loaded.should_receive('publish').with_args(module.LOADING_FAILED).replace_with(
        lambda data: seen_error_messages.append(command_output_loaded.error_message)
    ).once()

    module.pipe_file.__wrapped__(
        browse_app=browse_app,
        command_output_loaded=command_output_loaded,
        config=config,
        repository=flexmock(),
        archive_name='archive',
        file_path='foo/bar/baz.txt',
        command='jq .',
    )

    assert command_output_loaded.failed is True
    assert command_output_loaded.error_message == (
        'Error piping foo/bar/baz.txt to a command: the detail'
    )
    # The error message is set before the failure is published, so subscribers can show it.
    assert seen_error_messages == ['Error piping foo/bar/baz.txt to a command: the detail']


@pytest.mark.parametrize('error', FAILURES)
def test_pipe_file_with_failure_after_cancelling_publishes_loading_failed_without_reporting(error):
    flexmock(module.borgmatic_browse.archive).should_receive('pipe_archive_file').and_raise(error)
    flexmock(module).should_receive('report_loading_error').never()
    command_output_loaded = make_command_output_loaded()
    command_output_loaded.cancelled = True
    command_output_loaded.should_receive('publish').with_args(module.LOADING_FAILED).once()

    module.pipe_file.__wrapped__(
        browse_app=flexmock(),
        command_output_loaded=command_output_loaded,
        config={},
        repository=flexmock(),
        archive_name='archive',
        file_path='foo/bar/baz.txt',
        command='jq .',
    )

    assert command_output_loaded.failed is True
    assert command_output_loaded.error_message is None
