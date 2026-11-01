import pytest
import textual.app
from flexmock import flexmock

import borgmatic_browse.app
import borgmatic_browse.archive
import borgmatic_browse.archives_list
import borgmatic_browse.carousel
import borgmatic_browse.configuration_files_list
import borgmatic_browse.directory_list
import borgmatic_browse.file_preview
import borgmatic_browse.logs
import borgmatic_browse.repositories_list
import borgmatic_browse.sorting
import borgmatic_browse.workers

ARCHIVES = (
    # Oldest first, the way Borg lists them.
    borgmatic_browse.archive.Archive('i1', 'mm', '2026-10-29 10:00'),
    borgmatic_browse.archive.Archive('i2', 'aa', '2026-10-30 10:00'),
    borgmatic_browse.archive.Archive('i3', 'zz', '2026-10-31 10:00'),
)
Archive_path = borgmatic_browse.archive.Archive_path
ARCHIVE_PATHS = (
    Archive_path('d', 'bdir', '', 0, '2026-03-01T00:00:00'),
    Archive_path('-', 'bdir/y', '', 1000, '2026-01-01T00:00:00'),
    Archive_path('d', 'adir', '', 0, '2026-03-05T00:00:00'),
    Archive_path('-', 'adir/x', '', 5, '2026-01-01T00:00:00'),
    Archive_path('-', 'a.txt', '', 300, '2026-01-01T00:00:00'),
    Archive_path('-', 'b.txt', '', 20, '2026-01-02T00:00:00'),
    Archive_path('-', 'c.txt', '', 10, '2026-01-03T00:00:00'),
)


def painted_names(panel):
    '''
    Return the last word painted on each line of the given option list (ignoring a trailing
    "(latest)" label), which is each option's name here, with any loading indicator animation
    normalised.
    '''
    names = []

    for y in range(len(panel.options)):
        words = panel.render_line(y).text.split()
        names.append(words[-2] if words[-1] == '(latest)' else words[-1])

    return ['loading-indicator' if name.startswith('loading') else name for name in names]


def make_app():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        ARCHIVES
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').and_return(ARCHIVE_PATHS)

    return app


async def drill_down(app, pilot, presses):
    for _ in range(presses):
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        await pilot.pause()


async def test_pressing_s_and_r_in_directory_list_changes_painted_order_and_subtitle():
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 2)
        directory_list = app.query_one(borgmatic_browse.directory_list.Directory_list)

        assert app.focused is directory_list
        assert painted_names(directory_list) == ['adir', 'bdir', 'a.txt', 'b.txt', 'c.txt']
        assert directory_list.border_subtitle == 'sort: name ↑'

        for key, subtitle, expected in (
            ('s', 'sort: size ↓', ['bdir', 'adir', 'a.txt', 'b.txt', 'c.txt']),
            ('r', 'sort: size ↑', ['adir', 'bdir', 'c.txt', 'b.txt', 'a.txt']),
            ('s', 'sort: time ↓', ['adir', 'bdir', 'c.txt', 'b.txt', 'a.txt']),
            ('r', 'sort: time ↑', ['bdir', 'adir', 'a.txt', 'b.txt', 'c.txt']),
            ('s', 'sort: name ↑', ['adir', 'bdir', 'a.txt', 'b.txt', 'c.txt']),
            ('r', 'sort: name ↓', ['bdir', 'adir', 'c.txt', 'b.txt', 'a.txt']),
        ):
            await pilot.press(key)
            await pilot.pause()

            assert directory_list.border_subtitle == subtitle
            assert painted_names(directory_list) == expected


@pytest.mark.parametrize('key', ('s', 'r'))
async def test_sorting_in_directory_list_keeps_highlighted_entry_highlighted(key):
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 2)
        directory_list = app.query_one(borgmatic_browse.directory_list.Directory_list)

        for _ in range(3):
            await pilot.press('j')

        assert directory_list.options[directory_list.highlighted].id == 'b.txt'

        await pilot.press(key)
        await pilot.pause()

        assert directory_list.options[directory_list.highlighted].id == 'b.txt'


async def test_pressing_s_and_r_in_archives_list_changes_painted_order_and_subtitle():
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 1)
        archives_list = app.query_one(borgmatic_browse.archives_list.Archives_list)

        assert app.focused is archives_list
        assert painted_names(archives_list) == ['zz', 'aa', 'mm']
        assert archives_list.border_subtitle == 'sort: time ↓'

        for key, subtitle, expected in (
            ('s', 'sort: name ↑', ['aa', 'mm', 'zz']),
            ('r', 'sort: name ↓', ['zz', 'mm', 'aa']),
            ('s', 'sort: time ↓', ['zz', 'aa', 'mm']),
            ('r', 'sort: time ↑', ['mm', 'aa', 'zz']),
        ):
            await pilot.press(key)
            await pilot.pause()

            assert archives_list.border_subtitle == subtitle
            assert painted_names(archives_list) == expected


async def test_sorting_in_archives_list_keeps_highlighted_archive_highlighted():
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 1)
        archives_list = app.query_one(borgmatic_browse.archives_list.Archives_list)
        await pilot.press('j')

        assert archives_list.options[archives_list.highlighted].id == 'i2'

        await pilot.press('s')
        await pilot.pause()

        assert archives_list.options[archives_list.highlighted].id == 'i2'


async def test_directory_list_entered_from_a_sorted_directory_list_inherits_its_sort():
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 2)
        await pilot.press('s')
        await pilot.press('r')
        await pilot.pause()
        await drill_down(app, pilot, 1)
        panel = app.query_one(borgmatic_browse.carousel.Carousel).focused_panel

        assert panel.path_components == ('adir',)
        assert panel.sort_mode == 'size'
        assert panel.sort_reversed is False
        assert panel.border_subtitle == 'sort: size ↑'


SORT_PATHS = (
    Archive_path('d', 'etc/zdir', '', 0, '2026-03-01T00:00:00'),
    Archive_path('-', 'etc/zdir/inner', '', 1, '2026-03-01T00:00:00'),
    Archive_path('d', 'etc/adir', '', 0, '2026-03-05T00:00:00'),
    Archive_path('-', 'etc/adir/inner', '', 99, '2026-03-05T00:00:00'),
    Archive_path('-', 'etc/a.txt', '', 300, '2026-01-01T00:00:00'),
    Archive_path('l', 'etc/lnk', '', 0, '2026-01-02T00:00:00'),
    Archive_path('p', 'etc/pipe', '', 50, None),
    Archive_path('-', 'etc/z.txt', '', 20, '2026-01-03T00:00:00'),
)


@pytest.mark.parametrize('sort_mode', ('name', 'size', 'time'))
@pytest.mark.parametrize('sort_reversed', (False, True))
async def test_parent_option_stays_on_top_and_directories_above_files_in_every_sort(
    sort_mode, sort_reversed
):
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    path_loaded = borgmatic_browse.workers.Archive_path_loaded(flexmock(), 'archive path loaded')
    path_loaded.publish(SORT_PATHS)
    directory_list = borgmatic_browse.directory_list.Directory_list(
        config=flexmock(),
        repository=flexmock(),
        archive_name='archive',
        path_loaded=path_loaded,
        path_components=('etc',),
    )

    class Test_app(textual.app.App):
        def compose(self):
            yield directory_list

    async with Test_app().run_test() as pilot:
        directory_list.set_sort_mode(sort_mode)

        if directory_list.sort_reversed != sort_reversed:
            directory_list.action_reverse_sort()

        await pilot.pause()
        names = painted_names(directory_list)

        assert directory_list.sort_mode == sort_mode
        assert directory_list.sort_reversed is sort_reversed
        assert names[0] == '..'
        assert names[-1] == 'loading-indicator'
        assert set(names[1:3]) == {'adir', 'zdir'}
        assert set(names[3:-1]) == {'a.txt', 'lnk', 'pipe', 'z.txt'}


@pytest.mark.parametrize(
    'sort_reversed,expected',
    ((False, ['b_early', 'a_late']), (True, ['a_late', 'b_early'])),
)
async def test_time_sort_orders_by_actual_time_across_a_daylight_saving_change(
    sort_reversed, expected
):
    # Daylight saving time ends at 03:00 local on 2026-04-05, so 02:30 at +11:00 is earlier than
    # 02:10 at +10:00, even though it sorts later as a string.
    paths = (
        Archive_path('-', 'a_late', '', 1, '2026-04-05T02:10:00+10:00'),
        Archive_path('-', 'b_early', '', 1, '2026-04-05T02:30:00+11:00'),
    )
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    directory_list = borgmatic_browse.directory_list.Directory_list(
        config=flexmock(), repository=flexmock(), archive_name='archive'
    )

    class Test_app(textual.app.App):
        def compose(self):
            yield directory_list

    async with Test_app().run_test() as pilot:
        directory_list.path_loaded.publish(paths)
        directory_list.on_archive_path_loaded(paths)
        directory_list.set_sort_mode('time')

        if not sort_reversed:
            directory_list.action_reverse_sort()

        await pilot.pause()

        assert painted_names(directory_list) == [*expected, 'loading-indicator']


def binding_keys(panel_class):
    return {
        key
        for binding in panel_class.BINDINGS
        for key in (binding.key if hasattr(binding, 'key') else binding[0]).split(',')
    }


def find_binding(panel_class, key):
    return next(
        binding
        for binding in panel_class.BINDINGS
        if key in (binding.key if hasattr(binding, 'key') else binding[0]).split(',')
    )


@pytest.mark.parametrize(
    'panel_class',
    (borgmatic_browse.directory_list.Directory_list, borgmatic_browse.archives_list.Archives_list),
)
def test_sortable_panels_bind_s_to_cycle_sort_and_r_to_reverse_sort(panel_class):
    sort_binding = find_binding(panel_class, 's')
    reverse_binding = find_binding(panel_class, 'r')

    assert (sort_binding.action, sort_binding.description) == ('cycle_sort', 'sort')
    assert (reverse_binding.action, reverse_binding.description) == ('reverse_sort', 'reverse')


@pytest.mark.parametrize(
    'panel_class',
    (
        borgmatic_browse.repositories_list.Repositories_list,
        borgmatic_browse.configuration_files_list.Configuration_files_list,
        borgmatic_browse.file_preview.File_preview,
    ),
)
def test_other_panels_do_not_bind_sort_keys(panel_class):
    assert not binding_keys(panel_class) & {'s', 'r'}


async def get_command_titles(app):
    return [command.title for command in app.get_system_commands(app.screen)]


async def test_system_commands_still_remove_screenshot_minimize_and_maximize():
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 2)
        titles = await get_command_titles(app)

        assert 'Quit' in titles
        assert not {'Screenshot', 'Minimize', 'Maximize'} & set(titles)


async def test_system_commands_with_non_sortable_panel_focused_have_no_sort_commands():
    app = make_app()

    async with app.run_test():
        titles = await get_command_titles(app)

        assert isinstance(
            app.query_one(borgmatic_browse.carousel.Carousel).focused_panel,
            borgmatic_browse.repositories_list.Repositories_list,
        )
        assert 'Quit' in titles
        assert not [title for title in titles if title.startswith(('Sort by', 'Reverse sort'))]


async def test_system_commands_with_directory_list_focused_offer_each_sort_mode_and_reverse():
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 2)
        directory_list = app.query_one(borgmatic_browse.directory_list.Directory_list)
        commands = {command.title: command for command in app.get_system_commands(app.screen)}

        assert [title for title in commands if title.startswith(('Sort by', 'Reverse'))] == [
            'Sort by name',
            'Sort by size',
            'Sort by time',
            'Reverse sort order',
        ]

        commands['Sort by size'].callback()
        await pilot.pause()

        assert directory_list.sort_mode == 'size'
        assert painted_names(directory_list) == ['bdir', 'adir', 'a.txt', 'b.txt', 'c.txt']

        commands['Reverse sort order'].callback()
        await pilot.pause()

        assert directory_list.sort_reversed is False
        assert painted_names(directory_list) == ['adir', 'bdir', 'c.txt', 'b.txt', 'a.txt']

        commands['Sort by time'].callback()
        await pilot.pause()

        assert directory_list.sort_mode == 'time'
        assert directory_list.border_subtitle == 'sort: time ↓'


async def test_system_commands_with_archives_list_focused_offer_each_sort_mode_and_reverse():
    app = make_app()

    async with app.run_test() as pilot:
        await drill_down(app, pilot, 1)
        archives_list = app.query_one(borgmatic_browse.archives_list.Archives_list)
        commands = {command.title: command for command in app.get_system_commands(app.screen)}

        assert [title for title in commands if title.startswith(('Sort by', 'Reverse'))] == [
            'Sort by time',
            'Sort by name',
            'Reverse sort order',
        ]

        commands['Sort by name'].callback()
        await pilot.pause()

        assert archives_list.sort_mode == 'name'
        assert painted_names(archives_list) == ['aa', 'mm', 'zz']

        commands['Reverse sort order'].callback()
        await pilot.pause()

        assert painted_names(archives_list) == ['zz', 'mm', 'aa']


def painted_footer(app):
    '''
    Return the text painted on the footer's line of the screen. Read the compositor's strips,
    since that's what lands in the terminal, including anything clipped off the end.
    '''
    footer = app.query_one('Footer')
    strips = app.screen._compositor.render_strips()

    return ''.join(segment.text for segment in strips[footer.region.y])


@pytest.mark.parametrize('presses', (1, 2), ids=('archives list', 'directory list'))
async def test_footer_on_sortable_panel_fits_every_shown_binding_and_the_logs_hint(presses):
    app = make_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await drill_down(app, pilot, presses)
        shown_descriptions = [
            active.binding.description
            for active in app.screen.active_bindings.values()
            if active.binding.show and active.enabled
        ]
        footer_text = painted_footer(app)

        assert {'sort', 'reverse', 'view logs', 'quit'} <= set(shown_descriptions)
        assert [
            description for description in shown_descriptions if description not in footer_text
        ] == []
        assert 'v view logs' in footer_text


async def test_pagedown_and_pageup_still_scroll_a_directory_list():
    app = make_app()
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').and_return(
        [Archive_path('-', f'file{index:03}.txt', '', 1) for index in range(100)]
    )

    async with app.run_test(size=(120, 40)) as pilot:
        await drill_down(app, pilot, 2)
        directory_list = app.query_one(borgmatic_browse.directory_list.Directory_list)
        assert directory_list.highlighted == 0

        await pilot.press('pagedown')
        await pilot.pause()
        paged_down = directory_list.highlighted

        assert paged_down > 1

        await pilot.press('pageup')
        await pilot.pause()

        assert directory_list.highlighted < paged_down
