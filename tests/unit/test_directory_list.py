import pytest
import rich.console
import rich.text
import textual.widgets.option_list
from flexmock import flexmock

from borgmatic_browse import directory_list as module


def test_get_relative_archive_path_components_strips_off_current_directory():
    assert module.get_relative_archive_path_components(
        flexmock(file_path='foo/bar/baz/quux.txt'), ('foo', 'bar')
    ) == ('baz', 'quux.txt')


def test_get_relative_archive_path_components_with_root_current_directory_strips_off_nothing():
    assert module.get_relative_archive_path_components(
        flexmock(file_path='foo/bar/baz/quux.txt'), ()
    ) == ('foo', 'bar', 'baz', 'quux.txt')


def test_get_relative_archive_path_components_with_non_matching_paths_returns_none():
    assert (
        module.get_relative_archive_path_components(
            flexmock(file_path='foo/bar/baz/quux.txt'), ('etc',)
        )
        is None
    )


BLANK_TIME = ' ' * 16


def test_option_time_column_width_fits_a_formatted_time():
    assert module.OPTION_TIME_COLUMN_WIDTH == 16


def test_make_size_path_prompt_with_bytes_size_pads_unit():
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(358).and_return(
        '358 B'
    )

    prompt = module.make_size_path_prompt(358, 'path')

    assert isinstance(prompt, module.rich.text.Text)
    assert prompt.plain == f'    358 B   {BLANK_TIME}  path'


def test_make_size_path_prompt_with_larger_size_does_not_pad_unit():
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(
        1024
    ).and_return('1.02 kB')

    assert module.make_size_path_prompt(1024, 'path').plain == f'   1.02 kB  {BLANK_TIME}  path'


def test_make_size_path_prompt_with_no_size_leaves_size_column_blank():
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').never()

    assert module.make_size_path_prompt(None, 'path').plain == f'            {BLANK_TIME}  path'


def test_make_size_path_prompt_shows_formatted_time_between_size_and_path():
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(
        1024
    ).and_return('1.02 kB')
    flexmock(module.borgmatic_browse.times).should_receive('format_time').with_args(
        '2026-10-31T17:50:09'
    ).and_return('2026-10-31 17:50')

    assert (
        module.make_size_path_prompt(1024, 'path', '2026-10-31T17:50:09').plain
        == '   1.02 kB  2026-10-31 17:50  path'
    )


def test_make_size_path_prompt_left_justifies_time_in_its_column():
    flexmock(module.borgmatic_browse.times).should_receive('format_time').and_return('short')

    assert (
        module.make_size_path_prompt(None, 'path', 'whatever').plain
        == f'            {"short":<16}  path'
    )


def test_make_size_path_prompt_with_and_without_time_line_up_paths():
    with_time = module.make_size_path_prompt(0, 'path', '2026-10-31T17:50:09').plain
    without_time = module.make_size_path_prompt(0, 'path').plain

    assert with_time.index('path') == without_time.index('path')


def test_make_size_path_prompt_styles_only_the_time_dim():
    console = rich.console.Console()
    prompt = module.make_size_path_prompt(1024, 'path', '2026-10-31T17:50:09')
    time_offset = prompt.plain.index('2026-10-31 17:50')

    assert prompt.get_style_at_offset(console, time_offset).dim
    assert not prompt.get_style_at_offset(console, prompt.plain.index('path')).dim
    assert not prompt.get_style_at_offset(console, prompt.plain.index('1.02')).dim


def test_make_size_path_prompt_puts_path_after_both_columns():
    prompt = module.make_size_path_prompt(1024, 'path')

    assert prompt.plain.index('path') == module.OPTION_SIZE_COLUMN_WIDTH + 2 + 16 + 2


def expect_size_path_prompt(prompt, size, path_text):
    '''
    Make make_size_path_prompt() expect the given size and path text (with no time, since these
    tests pass none) and return the given prompt.
    '''

    def fake_make_size_path_prompt(actual_size, actual_path_text, mtime=None):
        assert (actual_size, actual_path_text, mtime) == (size, path_text, None)

        return prompt

    flexmock(module).should_receive('make_size_path_prompt').replace_with(
        fake_make_size_path_prompt
    )


def test_make_directory_list_option_with_file_path_makes_file_option():
    prompt = flexmock()
    expect_size_path_prompt(prompt, 1024, '📄 baz.txt')
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(
        1024
    ).and_return('1.02 kB')
    flexmock(module.textual.widgets.option_list).should_receive('Option').replace_with(flexmock)

    option = module.make_directory_list_option(
        flexmock(path_type='-', file_path='foo/bar/baz.txt', link_target=''), ('baz.txt',), 1024
    )

    assert option.prompt == prompt
    assert option.prompt_text == '📄 baz.txt (1.02 kB)'
    assert option.path_type == '-'
    assert option.id == 'baz.txt'


def test_make_directory_list_option_with_directory_path_makes_directory_option():
    prompt = flexmock()
    expect_size_path_prompt(prompt, 2048, '📁 baz')
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(
        2048
    ).and_return('2.05 kB')
    flexmock(module.textual.widgets.option_list).should_receive('Option').replace_with(flexmock)

    option = module.make_directory_list_option(
        flexmock(path_type='d', file_path='foo/bar/baz', link_target=''), ('baz',), 2048
    )

    assert option.prompt == prompt
    assert option.prompt_text == '📁 baz (2.05 kB)'
    assert option.path_type == 'd'
    assert option.id == 'baz'


def test_make_directory_list_option_with_contained_file_path_makes_directory_option():
    prompt = flexmock()
    expect_size_path_prompt(prompt, 0, '📁 bar')
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(0).and_return(
        '0 B'
    )
    flexmock(module.textual.widgets.option_list).should_receive('Option').replace_with(flexmock)

    option = module.make_directory_list_option(
        flexmock(path_type='d', file_path='foo/bar/baz.txt', link_target=''),
        (
            'bar',
            'baz.txt',
        ),
        0,
    )

    assert option.prompt == prompt
    assert option.prompt_text == '📁 bar (0 B)'
    assert option.path_type == 'd'
    assert option.id == 'bar'


def test_make_directory_list_option_with_contained_symlink_path_has_no_link_target():
    prompt = flexmock()
    expect_size_path_prompt(prompt, 0, '📁 mnt')
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(0).and_return(
        '0 B'
    )
    flexmock(module.textual.widgets.option_list).should_receive('Option').replace_with(flexmock)

    option = module.make_directory_list_option(
        flexmock(path_type='l', file_path='mnt/link', link_target='/home/foo/.git'),
        (
            'mnt',
            'link',
        ),
        0,
    )

    assert option.prompt == prompt
    assert option.prompt_text == '📁 mnt (0 B)'
    assert option.path_type == 'd'
    assert option.id == 'mnt'


def test_make_directory_list_option_with_link_path_makes_link_option():
    prompt = flexmock()
    expect_size_path_prompt(prompt, 0, '🔗 baz.txt → quux.txt')
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(0).and_return(
        '0 B'
    )
    flexmock(module.textual.widgets.option_list).should_receive('Option').replace_with(flexmock)

    option = module.make_directory_list_option(
        flexmock(path_type='l', file_path='foo/bar/baz.txt', link_target='quux.txt'),
        ('baz.txt',),
        0,
    )

    assert option.prompt == prompt
    assert option.prompt_text == '🔗 baz.txt → quux.txt (0 B)'
    assert option.path_type == 'l'
    assert option.id == 'baz.txt'


def test_make_directory_list_option_with_pipe_path_makes_pipe_option():
    prompt = flexmock()
    expect_size_path_prompt(prompt, 0, '🚰 baz.txt')
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(0).and_return(
        '0 B'
    )
    flexmock(module.textual.widgets.option_list).should_receive('Option').replace_with(flexmock)

    option = module.make_directory_list_option(
        flexmock(path_type='p', file_path='foo/bar/baz.txt', link_target=''), ('baz.txt',), 0
    )

    assert option.prompt == prompt
    assert option.prompt_text == '🚰 baz.txt (0 B)'
    assert option.path_type == 'p'
    assert option.id == 'baz.txt'


def test_make_directory_list_option_with_unknown_path_makes_unknown_option():
    prompt = flexmock()
    expect_size_path_prompt(prompt, 0, '❓ baz.txt')
    flexmock(module.borgmatic_browse.sizes).should_receive('format_size').with_args(0).and_return(
        '0 B'
    )
    flexmock(module.textual.widgets.option_list).should_receive('Option').replace_with(flexmock)

    option = module.make_directory_list_option(
        flexmock(path_type='wtf', file_path='foo/bar/baz.txt', link_target=''), ('baz.txt',), 0
    )

    assert option.prompt == prompt
    assert option.prompt_text == '❓ baz.txt (0 B)'
    assert option.path_type == 'wtf'
    assert option.id == 'baz.txt'


def test_make_directory_list_option_shows_mtime_in_prompt():
    option = module.make_directory_list_option(
        flexmock(path_type='-', file_path='foo/baz.txt', link_target=''),
        ('baz.txt',),
        1024,
        '2026-10-31T17:50:09',
    )

    assert option.prompt.plain == '   1.02 kB  2026-10-31 17:50  📄 baz.txt'


def test_make_directory_list_option_passes_mtime_to_prompt():
    calls = []

    def fake_make_size_path_prompt(size, path_text, mtime=None):
        calls.append((size, path_text, mtime))
        return flexmock()

    flexmock(module).should_receive('make_size_path_prompt').replace_with(
        fake_make_size_path_prompt
    )

    module.make_directory_list_option(
        flexmock(path_type='-', file_path='foo/baz.txt', link_target=''),
        ('baz.txt',),
        1024,
        mtime='2026-10-31T17:50:09',
    )

    assert calls == [(1024, '📄 baz.txt', '2026-10-31T17:50:09')]


def test_make_directory_list_option_prompt_text_includes_formatted_time():
    option = module.make_directory_list_option(
        flexmock(path_type='-', file_path='foo/baz.txt', link_target=''),
        ('baz.txt',),
        1024,
        '2026-10-31T17:50:09',
    )

    assert option.prompt_text.startswith('📄 baz.txt (1.02 kB)')
    assert option.prompt_text.endswith('2026-10-31 17:50')


def test_make_directory_list_option_with_changed_mtime_changes_prompt_text():
    archive_path = flexmock(path_type='-', file_path='foo/baz.txt', link_target='')

    before = module.make_directory_list_option(
        archive_path, ('baz.txt',), 1024, '2026-10-31T17:50:09'
    )
    after = module.make_directory_list_option(
        archive_path, ('baz.txt',), 1024, '2026-11-01T09:52:52'
    )

    assert before.prompt_text != after.prompt_text


def test_make_directory_list_option_with_mtime_added_changes_prompt_text():
    archive_path = flexmock(path_type='d', file_path='foo/baz', link_target='')

    before = module.make_directory_list_option(archive_path, ('baz',), 1024)
    after = module.make_directory_list_option(archive_path, ('baz',), 1024, '2026-10-31T17:50:09')

    assert before.prompt_text != after.prompt_text


def test_make_directory_list_option_time_does_not_affect_sort_order():
    older_a = module.make_directory_list_option(
        flexmock(path_type='-', file_path='a', link_target=''), ('a',), 0, '2026-01-01T00:00:00'
    )
    newer_b = module.make_directory_list_option(
        flexmock(path_type='-', file_path='b', link_target=''), ('b',), 0, '2026-12-31T00:00:00'
    )
    newer_a = module.make_directory_list_option(
        flexmock(path_type='-', file_path='a', link_target=''), ('a',), 0, '2026-12-31T00:00:00'
    )
    older_b = module.make_directory_list_option(
        flexmock(path_type='-', file_path='b', link_target=''), ('b',), 0, '2026-01-01T00:00:00'
    )

    for a, b in ((older_a, newer_b), (newer_a, older_b)):
        assert sorted((b, a), key=lambda option: option.prompt_text) == [a, b]


def test_make_directory_list_option_records_size_and_timestamp():
    option = module.make_directory_list_option(
        flexmock(path_type='-', file_path='foo/baz.txt', link_target=''),
        ('baz.txt',),
        1024,
        '2026-10-31T17:50:09+11:00',
    )

    assert option.size == 1024
    assert option.timestamp == module.borgmatic_browse.times.get_timestamp(
        '2026-10-31T17:50:09+11:00'
    )


def test_make_directory_list_option_without_mtime_records_no_timestamp():
    option = module.make_directory_list_option(
        flexmock(path_type='d', file_path='foo/baz', link_target=''), ('baz',), 2048
    )

    assert option.size == 2048
    assert option.timestamp is None


def make_directory_list(**kwargs):
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    return module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=True, path_hierarchy={}),
        **kwargs,
    )


def make_sort_option(option_id, path_type='-', size=0, timestamp=None):
    option = textual.widgets.option_list.Option(option_id, id=option_id)
    option.path_type = path_type
    option.size = size
    option.timestamp = timestamp

    return option


def make_special_option(option_id):
    '''
    Make an option like the ".." or loading indicator options, which carry none of the attributes
    of a path option.
    '''
    return textual.widgets.option_list.Option(option_id, id=option_id)


def sorted_ids(directory_list, options):
    return [option.id for option in directory_list.sort_options(options)]


def test_directory_list_is_sortable_with_name_size_and_time_modes():
    assert issubclass(module.Directory_list, module.borgmatic_browse.sorting.Sortable)
    assert module.Directory_list.SORT_MODES == ('name', 'size', 'time')
    assert module.Directory_list.DEFAULT_SORT_MODE == 'name'
    assert module.Directory_list.DEFAULT_REVERSED == {'name': False, 'size': True, 'time': True}


def test_directory_list_starts_sorted_by_name_ascending():
    directory_list = make_directory_list()

    assert directory_list.sort_mode == 'name'
    assert directory_list.sort_reversed is False
    assert directory_list.border_subtitle == 'sort: name ↑'


@pytest.mark.parametrize(
    'kwargs,expected_mode,expected_reversed',
    (
        ({'sort_mode': 'size'}, 'size', True),
        ({'sort_mode': 'time'}, 'time', True),
        ({'sort_mode': 'size', 'sort_reversed': False}, 'size', False),
        ({'sort_mode': 'name', 'sort_reversed': True}, 'name', True),
        ({'sort_mode': None, 'sort_reversed': None}, 'name', False),
    ),
)
def test_directory_list_accepts_initial_sort_mode_and_direction(
    kwargs, expected_mode, expected_reversed
):
    directory_list = make_directory_list(**kwargs)

    assert directory_list.sort_mode == expected_mode
    assert directory_list.sort_reversed is expected_reversed


def test_directory_list_sort_options_by_name_is_case_sensitive():
    directory_list = make_directory_list()

    assert sorted_ids(
        directory_list, [make_sort_option(name) for name in ('b', 'B', 'a', 'A')]
    ) == ['A', 'B', 'a', 'b']


def test_directory_list_sort_options_by_name_mixes_files_and_links_and_pipes():
    directory_list = make_directory_list()
    options = [
        make_sort_option('c', path_type='-'),
        make_sort_option('b', path_type='l'),
        make_sort_option('a', path_type='p'),
        make_sort_option('d', path_type='wtf'),
    ]

    assert sorted_ids(directory_list, options) == ['a', 'b', 'c', 'd']


def test_directory_list_sort_options_by_name_reversed_sorts_descending():
    directory_list = make_directory_list(sort_mode='name', sort_reversed=True)

    assert sorted_ids(directory_list, [make_sort_option(name) for name in 'bca']) == [
        'c',
        'b',
        'a',
    ]


def test_directory_list_sort_options_puts_special_options_at_the_ends_and_directories_first():
    directory_list = make_directory_list()
    options = [
        make_special_option('loading-indicator'),
        make_sort_option('a.txt'),
        make_sort_option('zdir', path_type='d'),
        make_special_option('..'),
        make_sort_option('adir', path_type='d'),
        make_sort_option('link', path_type='l'),
    ]

    assert sorted_ids(directory_list, options) == [
        '..',
        'adir',
        'zdir',
        'a.txt',
        'link',
        'loading-indicator',
    ]


@pytest.mark.parametrize('sort_mode', ('name', 'size', 'time'))
@pytest.mark.parametrize('sort_reversed', (False, True))
def test_directory_list_sort_options_keeps_group_order_in_every_mode_and_direction(
    sort_mode, sort_reversed
):
    directory_list = make_directory_list(sort_mode=sort_mode, sort_reversed=sort_reversed)
    options = [
        make_special_option('loading-indicator'),
        make_sort_option('file1', size=5, timestamp=3.0),
        make_sort_option('dir1', path_type='d', size=1, timestamp=9.0),
        make_sort_option('link1', path_type='l', size=7, timestamp=1.0),
        make_special_option('..'),
        make_sort_option('dir2', path_type='d', size=9, timestamp=2.0),
        make_sort_option('pipe1', path_type='p', size=3, timestamp=None),
    ]

    ids = sorted_ids(directory_list, options)

    assert ids[0] == '..'
    assert ids[-1] == 'loading-indicator'
    assert set(ids[1:3]) == {'dir1', 'dir2'}
    assert set(ids[3:-1]) == {'file1', 'link1', 'pipe1'}


def test_directory_list_sort_options_by_size_largest_first_by_default():
    directory_list = make_directory_list(sort_mode='size')
    options = [
        make_sort_option('small', size=1),
        make_sort_option('big', size=300),
        make_sort_option('mid', size=20),
        make_sort_option('smalldir', path_type='d', size=5),
        make_sort_option('bigdir', path_type='d', size=500),
    ]

    assert sorted_ids(directory_list, options) == ['bigdir', 'smalldir', 'big', 'mid', 'small']


def test_directory_list_sort_options_by_size_reversed_smallest_first():
    directory_list = make_directory_list(sort_mode='size', sort_reversed=False)
    options = [
        make_sort_option('small', size=1),
        make_sort_option('big', size=300),
        make_sort_option('mid', size=20),
    ]

    assert sorted_ids(directory_list, options) == ['small', 'mid', 'big']


def test_directory_list_sort_options_by_size_breaks_ties_by_name():
    directory_list = make_directory_list(sort_mode='size', sort_reversed=False)
    options = [make_sort_option(name, size=10) for name in ('c', 'a', 'b')]
    options.append(make_sort_option('big', size=100))
    options.append(make_sort_option('tiny', size=1))

    assert sorted_ids(directory_list, options) == ['tiny', 'a', 'b', 'c', 'big']


def test_directory_list_sort_options_by_time_newest_first_by_default():
    directory_list = make_directory_list(sort_mode='time')
    options = [
        make_sort_option('old', timestamp=100.0),
        make_sort_option('new', timestamp=300.0),
        make_sort_option('mid', timestamp=200.0),
    ]

    assert sorted_ids(directory_list, options) == ['new', 'mid', 'old']


def test_directory_list_sort_options_by_time_reversed_oldest_first():
    directory_list = make_directory_list(sort_mode='time', sort_reversed=False)
    options = [
        make_sort_option('old', timestamp=100.0),
        make_sort_option('new', timestamp=300.0),
        make_sort_option('mid', timestamp=200.0),
    ]

    assert sorted_ids(directory_list, options) == ['old', 'mid', 'new']


def test_directory_list_sort_options_by_time_counts_missing_time_as_oldest():
    options = [
        make_sort_option('old', timestamp=100.0),
        make_sort_option('none', timestamp=None),
        make_sort_option('new', timestamp=300.0),
    ]

    oldest_first = make_directory_list(sort_mode='time', sort_reversed=False)
    newest_first = make_directory_list(sort_mode='time', sort_reversed=True)

    assert sorted_ids(oldest_first, options) == ['none', 'old', 'new']
    assert sorted_ids(newest_first, options) == ['new', 'old', 'none']


def test_directory_list_sort_options_by_time_breaks_ties_by_name():
    directory_list = make_directory_list(sort_mode='time', sort_reversed=False)
    options = [
        make_sort_option('b', timestamp=100.0),
        make_sort_option('a', timestamp=100.0),
        make_sort_option('z', timestamp=None),
        make_sort_option('y', timestamp=None),
        make_sort_option('late', timestamp=200.0),
    ]

    assert sorted_ids(directory_list, options) == ['y', 'z', 'a', 'b', 'late']


def test_directory_list_sort_options_compares_times_by_timestamp_not_text():
    directory_list = make_directory_list(sort_mode='time', sort_reversed=False)
    early = make_sort_option(
        'b_early',
        timestamp=module.borgmatic_browse.times.get_timestamp('2026-04-05T02:30:00+11:00'),
    )
    late = make_sort_option(
        'a_late',
        timestamp=module.borgmatic_browse.times.get_timestamp('2026-04-05T02:10:00+10:00'),
    )

    assert sorted_ids(directory_list, [late, early]) == ['b_early', 'a_late']
