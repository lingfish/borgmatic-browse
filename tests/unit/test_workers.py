import subprocess

import pytest
import rich.markup
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
    notification whose message includes the escaped detail.
    '''
    browse_app = flexmock()
    browse_app.should_receive('notify').replace_with(
        lambda message, severity=None: (
            None if severity == 'error' and rich.markup.escape(detail) in message else 1 / 0
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
        config=flexmock(),
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
        config=flexmock(),
        repository=flexmock(),
    )


def test_add_repository_archives_with_failure_escapes_markup_in_notification():
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
        config=flexmock(),
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
        config=flexmock(),
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
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        file_path='foo/bar/baz.txt',
    )


def test_loading_failed_is_distinct_from_none_and_loading_done():
    assert module.LOADING_FAILED is not None
    assert module.LOADING_FAILED is not module.LOADING_DONE
