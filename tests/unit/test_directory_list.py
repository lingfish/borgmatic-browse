import rich.console
import rich.text
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
