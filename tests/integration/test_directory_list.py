import re
import time as time_module

import pytest
import rich.console
import rich.text
import textual.app
import textual.binding
import textual.widgets
import textual.widgets.option_list
from flexmock import flexmock

from borgmatic_browse import directory_list as module
from borgmatic_browse.workers import Directory


def rendered_text(renderable):
    '''
    Given a Rich renderable, return its rendered plain text.
    '''
    console = rich.console.Console(width=60, color_system=None)

    with console.capture() as capture:
        console.print(renderable, end='')

    return capture.get()


def make_option(prompt, option_id, path_type='-', size=0, timestamp=None):
    '''
    Make a textual.widgets.option_list.Option with the given prompt and ID, stashing the prompt as
    prompt_text the way that real directory list and loading indicator options do, along with the
    path type, size and timestamp that real directory list options carry.
    '''
    option = textual.widgets.option_list.Option(prompt, id=option_id)
    option.prompt_text = prompt
    option.path_type = path_type
    option.size = size
    option.timestamp = timestamp

    return option


class Bare_directory_list(module.Directory_list):
    '''
    A Directory_list without the loading indicator, border title and parent option of a real one, so
    that tests can place options and a path hierarchy directly. It still sorts like a real one.
    '''

    def __init__(self, path_components, path_loaded):
        textual.widgets.OptionList.__init__(self)
        self.path_components = path_components
        self.path_loaded = path_loaded
        self.highlighted_option_changed = False
        self.init_sort()


def test_make_size_path_prompt_aligns_paths_regardless_of_size_length():
    bytes_prompt = module.make_size_path_prompt(0, 'path')
    kilobytes_prompt = module.make_size_path_prompt(1024, 'path')

    assert isinstance(bytes_prompt, rich.text.Text)
    assert rendered_text(bytes_prompt).index('path') == rendered_text(kilobytes_prompt).index(
        'path'
    )


def test_make_size_path_prompt_aligns_bytes_number_with_larger_size_numbers():
    bytes_text = rendered_text(module.make_size_path_prompt(358, 'path'))
    kilobytes_text = rendered_text(module.make_size_path_prompt(1024, 'path'))

    assert bytes_text.index('358') + len('358') == kilobytes_text.index('1.02') + len('1.02')


def test_add_archive_paths_with_only_duplicate_paths_bails():
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy={}))
    directory_list.add_option(make_option('foo', option_id='foo'))
    directory_list.add_option(make_option('bar', option_id='bar'))
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(directory_list).should_receive('clear_options').never()
    flexmock(directory_list).should_receive('add_options').never()

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='-', file_path='etc/foo/one.txt', link_target='', size=1),
            flexmock(path_type='-', file_path='etc/foo/two.txt', link_target='', size=1),
        ),
    )


def test_add_archive_paths_adds_ands_sorts_and_filters_and_deduplicates():
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy={}))
    directory_list.add_option(make_option('📄 foo', option_id='foo'))
    directory_list.add_option(make_option('📄 bar', option_id='bar'))
    directory_list.highlighted = 1
    directory_list.highlighted_option_changed = True
    config = {'repositories': [{'path': 'test.borg'}]}

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='d', file_path='etc/quux', link_target='', size=0),
            flexmock(path_type='-', file_path='etc/foo', link_target='', size=0, mtime=None),
            flexmock(path_type='-', file_path='etc/baz', link_target='', size=0, mtime=None),
            flexmock(path_type='d', file_path='root/nope', link_target='', size=0),
            flexmock(path_type='d', file_path='etc/other', link_target='', size=0),
        ),
    )

    assert len(directory_list.options) == 5
    assert directory_list.options[0].prompt_text == '📁 other (0 B)'
    assert directory_list.options[0].id == 'other'
    assert directory_list.options[1].prompt_text == '📁 quux (0 B)'
    assert directory_list.options[1].id == 'quux'
    assert directory_list.options[2].prompt_text == '📄 bar'
    assert directory_list.options[2].id == 'bar'
    assert directory_list.options[3].prompt_text == '📄 baz (0 B)'
    assert directory_list.options[3].id == 'baz'
    assert directory_list.options[4].prompt_text == '📄 foo (0 B)'
    assert directory_list.options[4].id == 'foo'
    assert directory_list.highlighted == 2


def test_add_archive_paths_updates_existing_option_size():
    hierarchy = {}

    for file_name in ('bar.txt', 'baz.txt'):
        module.borgmatic_browse.workers.record_path(
            archive_path=module.borgmatic_browse.archive.Archive_path(
                '-', f'etc/foo/{file_name}', '', 1024
            ),
            hierarchy=hierarchy,
            path_components=('etc', 'foo', file_name),
        )

    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy=hierarchy))
    # The option's size as of before baz.txt loaded.
    directory_list.add_option(make_option('📁 foo (1.02 kB)', option_id='foo'))
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(directory_list).should_call('replace_option_prompt').with_args('foo', object).once()
    flexmock(directory_list).should_receive('clear_options').never()
    flexmock(directory_list).should_receive('add_options').never()

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='-', file_path='etc/foo/baz.txt', link_target='', size=1024),
        ),
    )

    assert directory_list.options[0].prompt_text == '📁 foo (2.05 kB)'


def test_add_archive_paths_does_not_repaint_unchanged_size():
    hierarchy = {}
    module.borgmatic_browse.workers.record_path(
        archive_path=module.borgmatic_browse.archive.Archive_path('-', 'etc/foo/bar.txt', '', 2048),
        hierarchy=hierarchy,
        path_components=('etc', 'foo', 'bar.txt'),
    )
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy=hierarchy))
    directory_list.add_option(make_option('📁 foo (2.05 kB)', option_id='foo'))
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(directory_list).should_receive('replace_option_prompt').never()
    flexmock(directory_list).should_receive('clear_options').never()
    flexmock(directory_list).should_receive('add_options').never()

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='-', file_path='etc/foo/bar.txt', link_target='', size=2048),
        ),
    )


def test_add_archive_paths_ignores_link_target_for_directory_row():
    hierarchy = {}
    module.borgmatic_browse.workers.record_path(
        archive_path=module.borgmatic_browse.archive.Archive_path(
            'l', 'etc/foo/link', '/home/foo/.git', 0
        ),
        hierarchy=hierarchy,
        path_components=('etc', 'foo', 'link'),
    )
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy=hierarchy))
    directory_list.add_option(make_option('📁 foo (0 B)', option_id='foo'))
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(directory_list).should_receive('replace_option_prompt').never()
    flexmock(directory_list).should_receive('clear_options').never()
    flexmock(directory_list).should_receive('add_options').never()

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='l', file_path='etc/foo/link', link_target='/home/foo/.git', size=0),
        ),
    )


def test_add_archive_paths_computes_one_size_update_per_directory_for_a_batch():
    archive_paths = tuple(
        module.borgmatic_browse.archive.Archive_path('-', f'etc/foo/{name}', '', 100)
        for name in ('one', 'two', 'three')
    )
    hierarchy = {}
    for archive_path in archive_paths:
        module.borgmatic_browse.workers.record_path(
            archive_path, hierarchy, ('etc', 'foo', archive_path.file_path.rsplit('/', 1)[1])
        )
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy=hierarchy))
    directory_list.add_option(make_option('📁 foo (100 B)', option_id='foo'))
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(directory_list).should_receive('replace_option_prompt').once()
    flexmock(directory_list).should_receive('clear_options').never()
    flexmock(directory_list).should_receive('add_options').never()

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=archive_paths,
    )

    assert directory_list.get_option('foo').prompt_text == '📁 foo (300 B)'


def test_add_archive_paths_highlights_first_option_if_highlight_has_not_changed():
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy={}))
    directory_list.add_option(make_option('📄 foo', option_id='foo'))
    directory_list.add_option(make_option('📄 bar', option_id='bar'))
    directory_list.highlighted = None
    directory_list.highlighted_option_changed = False
    config = {'repositories': [{'path': 'test.borg'}]}

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='-', file_path='etc/baz', link_target='', size=0, mtime=None),
        ),
    )

    assert len(directory_list.options) == 3
    assert directory_list.options[0].prompt_text == '📄 bar'
    assert directory_list.options[0].id == 'bar'
    assert directory_list.options[1].prompt_text == '📄 baz (0 B)'
    assert directory_list.options[1].id == 'baz'
    assert directory_list.options[2].prompt_text == '📄 foo'
    assert directory_list.options[2].id == 'foo'
    assert directory_list.highlighted == 0


def test_add_archive_paths_retains_loading_indicator_at_bottom():
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy={}))
    directory_list.add_option(make_option('📄 foo', option_id='foo'))
    directory_list.add_option(make_option('📄 bar', option_id='bar'))
    directory_list.add_option(make_option('loading!!!', option_id='loading-indicator'))
    directory_list.highlighted = 0
    directory_list.highlighted_option_changed = True
    config = {'repositories': [{'path': 'test.borg'}]}

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='-', file_path='etc/baz', link_target='', size=0, mtime=None),
        ),
    )

    assert len(directory_list.options) == 4
    assert directory_list.options[0].prompt_text == '📄 bar'
    assert directory_list.options[0].id == 'bar'
    assert directory_list.options[1].prompt_text == '📄 baz (0 B)'
    assert directory_list.options[1].id == 'baz'
    assert directory_list.options[2].prompt_text == '📄 foo'
    assert directory_list.options[2].id == 'foo'
    assert directory_list.options[3].prompt_text == 'loading!!!'
    assert directory_list.options[3].id == 'loading-indicator'
    assert directory_list.highlighted == 2


def test_directory_list_with_root_directory_adds_loading_indicator():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator').once()

    directory_list = module.Directory_list(
        config=flexmock(), repository=flexmock(), archive_name='archive'
    )
    assert directory_list.border_title == '📁 archive (0 B)'
    assert len(directory_list.options) == 0
    assert not directory_list.path_loaded.complete


def test_directory_list_with_already_complete_loading_skips_loading_indicator():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator').never()
    flexmock(module.borgmatic_browse.workers).should_receive('load_archive_paths').never()
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())

    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=True, path_hierarchy={}),
        path_components=('etc',),
    )
    assert directory_list.border_title == '📁 etc (0 B)'
    assert len(directory_list.options) == 1
    assert directory_list.options[0].prompt_text == '📁 ..'
    assert directory_list.options[0].id == '..'


def test_directory_list_on_mount_with_root_directory_loads_archive_paths():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    flexmock(module.borgmatic_browse.workers).should_receive('load_archive_paths').once()
    flexmock(module).should_receive('add_archive_paths').never()
    directory_list = module.Directory_list(
        config=flexmock(), repository=flexmock(), archive_name='archive'
    )
    flexmock(directory_list.path_loaded).should_receive('subscribe')

    directory_list.on_mount()


def test_directory_list_on_mount_with_non_root_directory_adds_archive_paths():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    flexmock(module.borgmatic_browse.workers).should_receive('load_archive_paths').never()
    flexmock(module).should_receive('add_archive_paths').once()
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=False, path_hierarchy={'etc': Directory()}),
        path_components=('etc',),
    )
    flexmock(directory_list.path_loaded).should_receive('subscribe')

    directory_list.on_mount()


def test_on_archive_path_loaded_with_loading_done_signal_removes_loading_indicator():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    flexmock(module).should_receive('add_archive_paths').never()
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=False, path_hierarchy={'etc': Directory()}),
        path_components=('etc',),
    )
    directory_list.timer = flexmock(stop=lambda: None)
    flexmock(directory_list).should_receive('remove_option').once()

    directory_list.on_archive_path_loaded(data=module.borgmatic_browse.workers.LOADING_DONE)


def test_on_archive_path_loaded_with_path_loaded_signal_adds_archive_path():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    flexmock(module).should_receive('add_archive_paths').once()
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=False, path_hierarchy={'etc': Directory()}),
        path_components=('etc',),
    )
    flexmock(directory_list).should_receive('remove_option').never()

    directory_list.on_archive_path_loaded(data=flexmock())


def test_directory_list_on_option_list_option_highlighted_with_highlighted_none_marks_it_unchanged():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=False, path_hierarchy={'etc': Directory()}),
        path_components=('etc',),
    )
    directory_list.highlighted = None

    directory_list.on_option_list_option_highlighted(event=flexmock())

    assert directory_list.highlighted_option_changed is False


def test_directory_list_on_option_list_option_highlighted_with_highlighted_zero_marks_it_unchanged():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=False, path_hierarchy={'etc': Directory()}),
        path_components=('etc',),
    )
    directory_list.add_option(make_option('zero', option_id='zero'))
    directory_list.highlighted = 0

    directory_list.on_option_list_option_highlighted(event=flexmock())

    assert directory_list.highlighted_option_changed is False


def test_directory_list_on_option_list_option_highlighted_with_highlighted_non_zero_marks_it_changed():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=False, path_hierarchy={'etc': Directory()}),
        path_components=('etc',),
    )
    directory_list.add_option(make_option('zero', option_id='zero'))
    directory_list.add_option(make_option('one', option_id='one'))
    directory_list.highlighted = 1

    directory_list.on_option_list_option_highlighted(event=flexmock())

    assert directory_list.highlighted_option_changed is True


def test_directory_list_update_border_title_reflects_newly_loaded_directory_size():
    hierarchy = {'etc': Directory()}
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=True, path_hierarchy=hierarchy),
        path_components=('etc',),
    )
    assert directory_list.border_title == '📁 etc (0 B)'

    module.borgmatic_browse.workers.record_path(
        archive_path=module.borgmatic_browse.archive.Archive_path('-', 'etc/bar.txt', '', 1024),
        hierarchy=hierarchy,
        path_components=('etc', 'bar.txt'),
    )

    directory_list.update_border_title()

    assert directory_list.border_title == '📁 etc (1.02 kB)'


def test_directory_list_update_border_title_reflects_newly_loaded_archive_size():
    hierarchy = {'etc': Directory()}
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=True, path_hierarchy=hierarchy),
    )
    assert directory_list.border_title == '📁 archive (0 B)'

    for file_path in ('etc/bar.txt', 'foo.txt'):
        module.borgmatic_browse.workers.record_path(
            archive_path=module.borgmatic_browse.archive.Archive_path('-', file_path, '', 512),
            hierarchy=hierarchy,
            path_components=tuple(file_path.split('/')),
        )

    directory_list.update_border_title()

    assert directory_list.border_title == '📁 archive (1.02 kB)'


def test_directory_list_border_title_shows_archive_label_instead_of_archive_id():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    directory_list = module.Directory_list(
        config=flexmock(), repository=flexmock(), archive_name='abc123', archive_label='archive'
    )

    assert directory_list.archive_name == 'abc123'
    assert 'archive' in directory_list.border_title
    assert 'abc123' not in directory_list.border_title


DATE_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}')


@pytest.fixture
def auckland_time(monkeypatch):
    # Auckland is UTC+13 on the dates below, so a missing time zone conversion shows up no matter
    # which time zone the tests happen to run in.
    monkeypatch.setenv('TZ', 'Pacific/Auckland')
    time_module.tzset()
    yield
    monkeypatch.undo()
    time_module.tzset()


def make_loaded_directory_list():
    '''
    Make a root-level option list backed by a real Archive_path_loaded signal, along with that
    signal.
    '''
    path_loaded = module.borgmatic_browse.workers.Archive_path_loaded(owner=flexmock(), name='Bob')
    directory_list = Bare_directory_list((), path_loaded)

    return directory_list, path_loaded


def load_batch(directory_list, path_loaded, archive_paths):
    '''
    Publish a batch of archive paths to the signal's hierarchy and then add it to the directory list,
    the way Directory_list does when a batch loads.
    '''
    path_loaded.publish(archive_paths)
    config = {'repositories': [{'path': 'test.borg'}]}

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=archive_paths,
    )


def test_add_archive_paths_shows_file_its_own_time():
    directory_list, path_loaded = make_loaded_directory_list()

    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('-', 'a.txt', '', 3, '2026-10-31T17:40:59'),),
    )

    assert directory_list.get_option('a.txt').prompt.plain == (
        module.make_size_path_prompt(3, '📄 a.txt', '2026-10-31T17:40:59').plain
    )
    assert '2026-10-31 17:40' in directory_list.get_option('a.txt').prompt.plain


def test_add_archive_paths_shows_directory_with_own_entry_that_time():
    directory_list, path_loaded = make_loaded_directory_list()

    load_batch(
        directory_list,
        path_loaded,
        (
            module.borgmatic_browse.archive.Archive_path('d', 'etc', '', 0, '2026-10-30T08:00:00'),
            module.borgmatic_browse.archive.Archive_path(
                '-', 'etc/a.txt', '', 3, '2026-10-31T17:40:59'
            ),
        ),
    )

    # The directory shows its own time, not its newest child's.
    assert directory_list.get_option('etc').prompt.plain == (
        module.make_size_path_prompt(3, '📁 etc', '2026-10-30T08:00:00').plain
    )
    assert '2026-10-30 08:00' in directory_list.get_option('etc').prompt.plain


def test_add_archive_paths_shows_directory_known_only_as_parent_the_no_entry_label():
    directory_list, path_loaded = make_loaded_directory_list()

    load_batch(
        directory_list,
        path_loaded,
        (
            module.borgmatic_browse.archive.Archive_path(
                '-', 'etc/a.txt', '', 3, '2026-10-31T17:40:59'
            ),
        ),
    )

    option = directory_list.get_option('etc')
    assert DATE_PATTERN.search(option.prompt.plain) is None
    assert option.prompt.plain == (
        module.make_size_path_prompt(
            3, '📁 etc', time_placeholder=module.NO_DIRECTORY_ENTRY_TEXT
        ).plain
    )
    assert '<no dir entry>' in option.prompt.plain
    assert '<no dir entry>' not in option.prompt_text
    assert option.timestamp is None


def test_add_archive_paths_replaces_prompt_when_directory_entry_arrives_after_its_children():
    directory_list, path_loaded = make_loaded_directory_list()
    load_batch(
        directory_list,
        path_loaded,
        (
            module.borgmatic_browse.archive.Archive_path(
                '-', 'etc/a.txt', '', 3, '2026-10-31T17:40:59'
            ),
        ),
    )
    assert DATE_PATTERN.search(directory_list.get_option('etc').prompt.plain) is None
    assert '<no dir entry>' in directory_list.get_option('etc').prompt.plain
    flexmock(directory_list).should_call('replace_option_prompt').with_args('etc', object).once()
    flexmock(directory_list).should_receive('clear_options').never()

    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('d', 'etc', '', 0, '2026-10-30T08:00:00'),),
    )

    option = directory_list.get_option('etc')
    assert (
        option.prompt.plain
        == module.make_size_path_prompt(3, '📁 etc', '2026-10-30T08:00:00').plain
    )
    assert '2026-10-30 08:00' in option.prompt_text
    assert '<no dir entry>' not in option.prompt.plain


def test_add_archive_paths_with_nested_path_in_later_batch_keeps_directory_time():
    directory_list, path_loaded = make_loaded_directory_list()
    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('d', 'etc', '', 0, '2026-10-30T08:00:00'),),
    )
    assert '2026-10-30 08:00' in directory_list.get_option('etc').prompt.plain

    load_batch(
        directory_list,
        path_loaded,
        (
            module.borgmatic_browse.archive.Archive_path(
                '-', 'etc/sub/b.txt', '', 1024, '2026-10-31T17:40:59'
            ),
        ),
    )

    # The size grew, so the prompt was replaced, but the time must survive that.
    assert directory_list.get_option('etc').prompt.plain == (
        module.make_size_path_prompt(1024, '📁 etc', '2026-10-30T08:00:00').plain
    )


def test_add_archive_paths_does_not_repaint_unchanged_directory_time():
    directory_list, path_loaded = make_loaded_directory_list()
    archive_paths = (
        module.borgmatic_browse.archive.Archive_path('d', 'etc', '', 0, '2026-10-30T08:00:00'),
    )
    load_batch(directory_list, path_loaded, archive_paths)
    flexmock(directory_list).should_receive('replace_option_prompt').never()

    module.add_archive_paths(
        directory_list=directory_list,
        config={},
        repository={},
        archive_name='archive',
        archive_paths=archive_paths,
    )


def test_add_archive_paths_repaints_file_whose_time_changed():
    directory_list, path_loaded = make_loaded_directory_list()
    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('-', 'a.txt', '', 3, '2026-10-31T17:40:59'),),
    )
    flexmock(directory_list).should_call('replace_option_prompt').with_args('a.txt', object).once()

    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('-', 'a.txt', '', 3, '2026-11-01T09:52:52'),),
    )

    assert '2026-11-01 09:52' in directory_list.get_option('a.txt').prompt.plain


def test_directory_list_parent_option_leaves_time_column_blank():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())

    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=True, path_hierarchy={}),
        path_components=('etc',),
    )

    assert (
        directory_list.get_option('..').prompt.plain
        == module.make_size_path_prompt(None, '📁 ..').plain
    )
    assert directory_list.get_option('..').prompt.plain.index('📁') == (
        module.OPTION_SIZE_COLUMN_WIDTH + 2 + module.OPTION_TIME_COLUMN_WIDTH + 2
    )


async def test_directory_list_paints_file_size_then_time_then_name(auckland_time):
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.workers).should_receive('load_archive_paths')
    directory_list = module.Directory_list(
        config=flexmock(), repository=flexmock(), archive_name='archive'
    )

    class Test_app(textual.app.App):
        def compose(self):
            yield directory_list

    app = Test_app()

    async with app.run_test() as pilot:
        archive_paths = (
            module.borgmatic_browse.archive.Archive_path(
                '-', 'a.txt', '', 1024, '2026-10-31T12:40:59Z'
            ),
        )
        directory_list.path_loaded.publish(archive_paths)
        directory_list.on_archive_path_loaded(archive_paths)
        await pilot.pause()

        line = directory_list.render_line(0).text

        assert app._exception is None
        assert line.strip() == '1.02 kB  2026-11-01 01:40  📄 a.txt'


async def test_directory_list_paints_no_entry_label_for_parent_only_directory_lined_up(
    auckland_time,
):
    directory_list = make_mounted_directory_list()

    class Test_app(textual.app.App):
        def compose(self):
            yield directory_list

    app = Test_app()

    async with app.run_test() as pilot:
        archive_paths = (
            module.borgmatic_browse.archive.Archive_path(
                '-', 'etc/a.txt', '', 1024, '2026-10-31T12:40:59Z'
            ),
            module.borgmatic_browse.archive.Archive_path(
                'd', 'home', '', 0, '2026-10-31T12:40:59Z'
            ),
        )
        directory_list.path_loaded.publish(archive_paths)
        directory_list.on_archive_path_loaded(archive_paths)
        await pilot.pause()

        lines = [directory_list.render_line(y).text for y in range(len(directory_list.options))]
        etc_line = next(line for line in lines if 'etc' in line)
        home_line = next(line for line in lines if 'home' in line)

        assert app._exception is None
        assert '<no dir entry>' in etc_line
        assert '2026-11-01 01:40' in home_line
        assert '<no dir entry>' not in home_line
        assert etc_line.index('<no dir entry>') == home_line.index('2026-11-01 01:40')
        assert etc_line.index('etc') == home_line.index('home')


def test_add_archive_paths_records_size_and_timestamp_on_new_options():
    directory_list, path_loaded = make_loaded_directory_list()

    load_batch(
        directory_list,
        path_loaded,
        (
            module.borgmatic_browse.archive.Archive_path(
                '-', 'a.txt', '', 3, '2026-10-31T17:40:59+11:00'
            ),
            module.borgmatic_browse.archive.Archive_path('-', 'b.txt', '', 4),
        ),
    )

    assert directory_list.get_option('a.txt').size == 3
    assert directory_list.get_option('a.txt').timestamp == (
        module.borgmatic_browse.times.get_timestamp('2026-10-31T17:40:59+11:00')
    )
    assert directory_list.get_option('b.txt').size == 4
    assert directory_list.get_option('b.txt').timestamp is None


def test_add_archive_paths_updates_existing_option_size_and_timestamp_when_prompt_changes():
    directory_list, path_loaded = make_loaded_directory_list()
    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('-', 'a.txt', '', 3, '2026-10-31T17:40:59'),),
    )

    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('-', 'a.txt', '', 9, '2026-11-01T09:52:52'),),
    )

    assert directory_list.get_option('a.txt').size == 9
    assert directory_list.get_option('a.txt').timestamp == (
        module.borgmatic_browse.times.get_timestamp('2026-11-01T09:52:52')
    )


def test_add_archive_paths_updates_growing_directory_size_on_existing_option():
    directory_list, path_loaded = make_loaded_directory_list()
    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('-', 'etc/a.txt', '', 3),),
    )
    assert directory_list.get_option('etc').size == 3

    load_batch(
        directory_list,
        path_loaded,
        (module.borgmatic_browse.archive.Archive_path('-', 'etc/b.txt', '', 4),),
    )

    assert directory_list.get_option('etc').size == 7


def test_add_archive_paths_sorts_with_the_directory_lists_sort_options():
    directory_list = Bare_directory_list(('etc',), flexmock(path_hierarchy={}))
    directory_list.add_option(make_option('📄 foo', option_id='foo'))
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(directory_list).should_call('sort_options').once()

    module.add_archive_paths(
        directory_list=directory_list,
        config=config,
        repository=config['repositories'][0],
        archive_name='archive',
        archive_paths=(
            flexmock(path_type='-', file_path='etc/bar', link_target='', size=0, mtime=None),
        ),
    )

    assert [option.id for option in directory_list.options] == ['bar', 'foo']


def test_add_archive_paths_puts_new_option_in_sorted_position_for_current_sort():
    directory_list, path_loaded = make_loaded_directory_list()
    load_batch(
        directory_list,
        path_loaded,
        (
            module.borgmatic_browse.archive.Archive_path('-', 'small', '', 1),
            module.borgmatic_browse.archive.Archive_path('-', 'big', '', 100),
        ),
    )
    directory_list.set_sort_mode('size')
    assert [option.id for option in directory_list.options] == ['big', 'small']

    load_batch(
        directory_list,
        path_loaded,
        (
            module.borgmatic_browse.archive.Archive_path('-', 'medium', '', 10),
            module.borgmatic_browse.archive.Archive_path('d', 'adir', '', 0),
        ),
    )

    assert [option.id for option in directory_list.options] == ['adir', 'big', 'medium', 'small']


def make_mounted_directory_list(**kwargs):
    flexmock(module.borgmatic_browse.workers).should_receive('load_archive_paths')

    return module.Directory_list(
        config=flexmock(), repository=flexmock(), archive_name='archive', **kwargs
    )


def painted_ids(directory_list):
    return [
        directory_list.render_line(y).text.split()[-1] for y in range(len(directory_list.options))
    ]


async def test_on_archive_path_loaded_with_loading_done_resorts_by_size_that_grew_without_new_options():
    directory_list = make_mounted_directory_list(sort_mode='size')

    class Test_app(textual.app.App):
        def compose(self):
            yield directory_list

    async with Test_app().run_test() as pilot:
        for batch in (
            (
                module.borgmatic_browse.archive.Archive_path('-', 'd1/x', '', 100),
                module.borgmatic_browse.archive.Archive_path('-', 'd2/x', '', 10),
            ),
            # No new options arrive in this batch, but d2 now outweighs d1.
            (module.borgmatic_browse.archive.Archive_path('-', 'd2/y', '', 1000),),
        ):
            directory_list.path_loaded.publish(batch)
            directory_list.on_archive_path_loaded(batch)

        directory_list.on_archive_path_loaded(module.borgmatic_browse.workers.LOADING_DONE)
        await pilot.pause()

        assert [option.id for option in directory_list.options] == ['d2', 'd1']
        assert painted_ids(directory_list) == ['d2', 'd1']


def test_on_archive_path_loaded_with_loading_done_applies_sort_after_removing_loading_indicator():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.directory_list.Directory_list).should_receive(
        'app'
    ).and_return(flexmock())
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=flexmock(complete=False, path_hierarchy={'etc': Directory()}),
        path_components=('etc',),
    )
    directory_list.timer = flexmock(stop=lambda: None)
    flexmock(directory_list).should_receive('remove_option').with_args(
        'loading-indicator'
    ).once().ordered()
    flexmock(directory_list).should_receive('apply_sort').once().ordered()

    directory_list.on_archive_path_loaded(data=module.borgmatic_browse.workers.LOADING_DONE)


@pytest.mark.parametrize(
    'path_components,failed,expected',
    (
        (None, True, True),
        (None, False, False),
        (('etc',), True, False),
        (('etc',), False, False),
    ),
)
def test_directory_list_load_failed_is_true_only_for_failed_root_list(
    path_components, failed, expected
):
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    path_loaded = module.borgmatic_browse.workers.Archive_path_loaded(flexmock(), 'Bob')
    path_loaded.failed = failed
    directory_list = module.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=path_loaded,
        path_components=path_components,
    )

    assert directory_list.load_failed is expected


def test_directory_list_load_failed_is_read_only():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    directory_list = module.Directory_list(
        config=flexmock(), repository=flexmock(), archive_name='archive'
    )

    with pytest.raises(AttributeError):
        directory_list.load_failed = True


# Issue #11: piping a file to a command.


def test_directory_list_has_pipe_binding():
    bindings = [
        binding
        for binding in module.Directory_list.BINDINGS
        if isinstance(binding, textual.binding.Binding) and binding.key == 'vertical_line'
    ]

    assert len(bindings) == 1
    assert bindings[0].action == 'pipe'
    assert bindings[0].description == 'pipe'
    assert bindings[0].key_display == '|'


def make_pipe_directory_list(path_components, *options):
    # Skip loading paths from an archive when the list gets mounted.
    flexmock(module.Directory_list).should_receive('on_mount')
    directory_list = Bare_directory_list(path_components, flexmock(path_hierarchy={}))
    directory_list.config = {'repositories': [{'path': 'test.borg'}]}
    directory_list.repository = {'path': 'test.borg'}
    directory_list.archive_name = 'archive'
    directory_list.add_options(options)

    return directory_list


class Directory_list_app(textual.app.App):
    def __init__(self, directory_list):
        super().__init__()
        self.directory_list = directory_list

    def compose(self):
        yield self.directory_list


@pytest.mark.parametrize(
    'path_components,expected_path',
    (((), 'foo.conf'), (('etc',), 'etc/foo.conf'), (('etc', 'nginx'), 'etc/nginx/foo.conf')),
)
async def test_directory_list_action_pipe_with_file_pipes_it_by_full_path(
    path_components, expected_path
):
    directory_list = make_pipe_directory_list(
        path_components, make_option('other', 'other', path_type='d'), make_option('x', 'foo.conf')
    )

    async with Directory_list_app(directory_list).run_test() as pilot:
        directory_list.highlighted = 1
        calls = []
        flexmock(module.borgmatic_browse.pipe).should_receive('pipe_file').replace_with(
            lambda *args: calls.append(args)
        )
        flexmock(directory_list).should_receive('notify').never()

        directory_list.action_pipe()
        await pilot.pause()

        assert calls == [
            (
                directory_list.app,
                directory_list.config,
                directory_list.repository,
                'archive',
                expected_path,
            )
        ]


@pytest.mark.parametrize('path_type', ('d', 'l', 'p'))
async def test_directory_list_action_pipe_with_non_file_warns_instead(path_type):
    directory_list = make_pipe_directory_list(
        ('etc',), make_option('thing', 'thing', path_type=path_type)
    )

    async with Directory_list_app(directory_list).run_test() as pilot:
        directory_list.highlighted = 0
        flexmock(module.borgmatic_browse.pipe).should_receive('pipe_file').never()
        flexmock(directory_list).should_receive('notify').with_args(
            'Only files can be piped to a command', severity='warning'
        ).once()

        directory_list.action_pipe()
        await pilot.pause()


@pytest.mark.parametrize('option_id', ('..', 'loading-indicator'))
async def test_directory_list_action_pipe_with_parent_or_loading_option_warns_instead(option_id):
    directory_list = make_pipe_directory_list(
        ('etc',), textual.widgets.option_list.Option('placeholder', id=option_id)
    )

    async with Directory_list_app(directory_list).run_test() as pilot:
        directory_list.highlighted = 0
        flexmock(module.borgmatic_browse.pipe).should_receive('pipe_file').never()
        flexmock(directory_list).should_receive('notify').with_args(
            'Only files can be piped to a command', severity='warning'
        ).once()

        directory_list.action_pipe()
        await pilot.pause()


async def test_directory_list_action_pipe_with_nothing_highlighted_warns_instead():
    directory_list = make_pipe_directory_list(('etc',), make_option('foo', 'foo'))

    async with Directory_list_app(directory_list).run_test() as pilot:
        directory_list.highlighted = None
        flexmock(module.borgmatic_browse.pipe).should_receive('pipe_file').never()
        flexmock(directory_list).should_receive('notify').with_args(
            'Only files can be piped to a command', severity='warning'
        ).once()

        directory_list.action_pipe()
        await pilot.pause()


async def test_directory_list_pressing_vertical_line_pipes_highlighted_file():
    directory_list = make_pipe_directory_list(('etc',), make_option('x', 'foo.conf'))
    calls = []
    flexmock(module.borgmatic_browse.pipe).should_receive('pipe_file').replace_with(
        lambda *args: calls.append(args)
    )

    async with Directory_list_app(directory_list).run_test() as pilot:
        directory_list.focus()
        directory_list.highlighted = 0
        await pilot.pause()

        await pilot.press('vertical_line')
        await pilot.pause()

        assert [call[-1] for call in calls] == ['etc/foo.conf']
