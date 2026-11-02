import pytest
import rich.text
import textual.app
import textual.widgets.option_list
from flexmock import flexmock

from borgmatic_browse import archives_list as module


def dim_text(text):
    '''
    Given a rich.text.Text instance, return the pieces of its plain text that are styled dim.
    '''
    return [text.plain[span.start : span.end] for span in text.spans if str(span.style) == 'dim']


async def test_archives_list_on_mount_does_not_raise():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.workers).should_receive('add_repository_archives')
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    flexmock(archives_list.archive_loaded).should_receive('subscribe')

    async with textual.app.App().run_test():
        archives_list.on_mount()


def test_archives_list_on_archive_loaded_with_loading_done_removes_loading_indicator():
    loading_timer = flexmock()
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(loading_timer)
    archives_list = module.Archives_list(config={}, repository=flexmock())
    flexmock(loading_timer).should_receive('stop')
    flexmock(archives_list).should_receive('remove_option').with_args('loading-indicator').once()
    flexmock(archives_list).should_receive('apply_sort').once()

    archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)


def test_archives_list_on_archive_loaded_adds_archive_name():
    loading_timer = flexmock()
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(loading_timer)
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    flexmock(loading_timer).should_receive('stop').never()
    loading_indicator = textual.widgets.option_list.Option('Loading', id='loading-indicator')
    flexmock(archives_list).should_receive('get_option').and_return(loading_indicator)
    flexmock(archives_list).should_receive('remove_option').with_args('loading-indicator').once()
    flexmock(archives_list).should_receive('add_options').at_least().once()

    archives_list.on_archive_loaded(
        module.borgmatic_browse.archive.Archive('id', 'archive', '2026-10-31 17:40')
    )


async def test_archives_list_with_identically_named_archives_adds_an_option_for_each():
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    flexmock(module.borgmatic_browse.workers).should_receive('add_repository_archives')

    class Test_app(textual.app.App):
        def compose(self):
            yield archives_list

    async with Test_app().run_test():
        for selector, time in (('id2', '2026-10-31 18:50'), ('id1', '2026-10-31 17:40')):
            archives_list.on_archive_loaded(
                module.borgmatic_browse.archive.Archive(selector, 'dup', time)
            )

        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

        assert [option.id for option in archives_list.options] == ['id2', 'id1']
        assert archives_list.archive_names == {'id2': 'dup', 'id1': 'dup'}
        latest, older = (option.prompt for option in archives_list.options[:2])

        assert isinstance(latest, rich.text.Text)
        assert latest.plain == '2026-10-31 18:50  dup (latest)'
        assert dim_text(latest) == ['2026-10-31 18:50', '(latest)']
        assert isinstance(older, rich.text.Text)
        assert older.plain == '2026-10-31 17:40  dup'
        assert dim_text(older) == ['2026-10-31 17:40']


def test_archives_list_on_archive_loaded_with_markup_like_name_adds_text_prompt_without_escaping():
    def add_loading_indicator(archives_list):
        # Like the real loading indicator, put its option in the list. That's what makes the first
        # loaded archive the latest one.
        archives_list.add_option(
            textual.widgets.option_list.Option('Loading', id='loading-indicator')
        )

        return flexmock()

    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).replace_with(add_loading_indicator)
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())

    archives_list.on_archive_loaded(
        module.borgmatic_browse.archive.Archive('id', 'bad[/name]', '2026-10-31 17:40')
    )

    prompt = archives_list.get_option('id').prompt
    assert [option.id for option in archives_list.options] == ['id', 'loading-indicator']
    assert isinstance(prompt, rich.text.Text)
    assert prompt.plain == '2026-10-31 17:40  bad[/name] (latest)'
    assert dim_text(prompt) == ['2026-10-31 17:40', '(latest)']


@pytest.mark.parametrize(
    'name',
    (
        'bad[/name]',
        '[bold]name',
        'name[1]',
        '[#fff]name',
        '[/]',
        '[@click=foo]name',
        'x[$var]',
        'back\\',
        'end\\[',
        'a\\[b]',
        'plain',
    ),
)
async def test_archives_list_displays_archive_name_literally(name):
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    flexmock(module.borgmatic_browse.workers).should_receive('add_repository_archives')

    class Test_app(textual.app.App):
        def compose(self):
            yield archives_list

    app = Test_app()

    async with app.run_test() as pilot:
        archives_list.on_archive_loaded(
            module.borgmatic_browse.archive.Archive('id', name, '2026-10-31 17:40')
        )
        archives_list.on_archive_loaded(
            module.borgmatic_browse.archive.Archive('id2', name, '2026-10-30 17:40')
        )
        await pilot.pause()

        displayed = [archives_list.render_line(y).text.strip() for y in range(2)]

        assert app._exception is None
        assert displayed == [
            f'2026-10-31 17:40  {name} (latest)',
            f'2026-10-30 17:40  {name}',
        ]


def test_archives_list_on_option_list_option_highlighted_with_highlighted_none_marks_it_unchanged():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    archives_list.highlighted = None
    archives_list.on_option_list_option_highlighted(event=flexmock())

    assert archives_list.highlighted_option_changed is False


def test_archives_list_on_option_list_option_highlighted_with_highlighted_zero_marks_it_unchanged():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    archives_list.highlighted = 0
    archives_list.on_option_list_option_highlighted(event=flexmock())

    assert archives_list.highlighted_option_changed is False


def test_archives_list_on_option_list_option_highlighted_with_existing_option_and_highlighted_zero_marks_it_unchanged():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    archives_list.add_option(textual.widgets.option_list.Option('zero', id='zero'))
    archives_list.highlighted = 0
    archives_list.on_option_list_option_highlighted(event=flexmock())

    assert archives_list.highlighted_option_changed is False


def test_archives_list_on_option_list_option_highlighted_with_highlighted_non_zero_marks_it_changed():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    archives_list.add_option(textual.widgets.option_list.Option('zero', id='zero'))
    archives_list.add_option(textual.widgets.option_list.Option('one', id='one'))
    archives_list.highlighted = 1
    archives_list.on_option_list_option_highlighted(event=flexmock())

    assert archives_list.highlighted_option_changed is True


def test_archives_list_is_sortable_with_time_and_name_modes():
    assert issubclass(module.Archives_list, module.borgmatic_browse.sorting.Sortable)
    assert module.Archives_list.SORT_MODES == ('time', 'name')
    assert module.Archives_list.DEFAULT_SORT_MODE == 'time'
    assert module.Archives_list.DEFAULT_REVERSED == {'time': True, 'name': False}


def test_archives_list_starts_sorted_by_time_newest_first():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())

    assert archives_list.sort_mode == 'time'
    assert archives_list.sort_reversed is True
    assert archives_list.border_subtitle == 'sort: time ↓'


def test_archives_list_on_archive_loaded_with_loading_done_applies_sort_after_removing_indicator():
    loading_timer = flexmock()
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(loading_timer)
    archives_list = module.Archives_list(config={}, repository=flexmock())
    flexmock(loading_timer).should_receive('stop')
    flexmock(archives_list).should_receive('remove_option').with_args(
        'loading-indicator'
    ).once().ordered()
    flexmock(archives_list).should_receive('apply_sort').once().ordered()

    archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)


# Archives as the worker publishes them: newest first.
NEWEST_FIRST = (
    ('id3', 'zeta', '2026-10-31 17:40'),
    ('id2', 'alpha', '2026-10-30 17:40'),
    ('id1', 'mid', '2026-10-29 17:40'),
)


def make_archives_list_app(load=NEWEST_FIRST, done=True):
    '''
    Return an Archives_list and an app to run it in, and a function that loads the given archives
    into the list, followed by a loading done signal if asked.
    '''
    flexmock(module.borgmatic_browse.workers).should_receive('add_repository_archives')
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())

    class Test_app(textual.app.App):
        def compose(self):
            yield archives_list

    def load_archives():
        for selector, name, time in load:
            archives_list.on_archive_loaded(
                module.borgmatic_browse.archive.Archive(selector, name, time)
            )

        if done:
            archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

    return archives_list, Test_app(), load_archives


def option_ids(option_list):
    return [option.id for option in option_list.options]


async def test_archives_list_default_order_is_load_order():
    archives_list, app, load_archives = make_archives_list_app(done=False)

    async with app.run_test():
        load_archives()

        assert option_ids(archives_list) == ['id3', 'id2', 'id1', 'loading-indicator']


async def test_archives_list_reversed_time_order_is_oldest_first_and_keeps_indicator_last():
    archives_list, app, load_archives = make_archives_list_app(done=False)

    async with app.run_test():
        load_archives()
        archives_list.action_reverse_sort()

        assert option_ids(archives_list) == ['id1', 'id2', 'id3', 'loading-indicator']
        assert archives_list.border_subtitle == 'sort: time ↑'


async def test_archives_list_time_order_uses_load_order_for_archives_in_the_same_minute():
    archives_list, app, load_archives = make_archives_list_app(
        load=(('x', 'a', 'same'), ('y', 'b', 'same'), ('z', 'c', 'same'))
    )

    async with app.run_test():
        load_archives()
        assert option_ids(archives_list) == ['x', 'y', 'z']

        archives_list.action_reverse_sort()

        assert option_ids(archives_list) == ['z', 'y', 'x']


async def test_archives_list_records_increasing_load_index_on_each_option_in_load_order():
    archives_list, app, load_archives = make_archives_list_app()

    async with app.run_test():
        load_archives()

        load_indexes = [
            archives_list.get_option(selector).load_index for selector in ('id3', 'id2', 'id1')
        ]

        assert load_indexes == sorted(set(load_indexes))


async def test_archives_list_name_order_sorts_by_archive_name():
    archives_list, app, load_archives = make_archives_list_app(done=False)

    async with app.run_test():
        load_archives()
        archives_list.set_sort_mode('name')

        assert option_ids(archives_list) == ['id2', 'id1', 'id3', 'loading-indicator']
        assert archives_list.border_subtitle == 'sort: name ↑'

        archives_list.action_reverse_sort()

        assert option_ids(archives_list) == ['id3', 'id1', 'id2', 'loading-indicator']
        assert archives_list.border_subtitle == 'sort: name ↓'


async def test_archives_list_name_order_breaks_ties_by_load_order():
    archives_list, app, load_archives = make_archives_list_app(
        load=(('id2', 'dup', 't2'), ('id1', 'dup', 't1'), ('id0', 'aaa', 't0'))
    )

    async with app.run_test():
        load_archives()
        archives_list.set_sort_mode('name')

        assert option_ids(archives_list) == ['id0', 'id2', 'id1']


@pytest.mark.parametrize('sort_mode', ('time', 'name'))
@pytest.mark.parametrize('reverse', (False, True))
async def test_archives_list_keeps_latest_label_on_first_loaded_archive_in_every_order(
    sort_mode, reverse
):
    archives_list, app, load_archives = make_archives_list_app()

    async with app.run_test():
        load_archives()
        archives_list.set_sort_mode(sort_mode)

        if reverse:
            archives_list.action_reverse_sort()

        labelled = [
            option.id
            for option in archives_list.options
            if option.prompt.plain.endswith('(latest)')
        ]

        assert labelled == ['id3']


async def test_archives_list_places_archive_loaded_during_name_sort_in_sorted_position():
    archives_list, app, load_archives = make_archives_list_app(
        load=(('i1', 'b', 't1'), ('i2', 'd', 't2')), done=False
    )

    async with app.run_test():
        archives_list.set_sort_mode('name')
        load_archives()
        assert option_ids(archives_list) == ['i1', 'i2', 'loading-indicator']

        archives_list.on_archive_loaded(module.borgmatic_browse.archive.Archive('i3', 'c', 't3'))

        assert option_ids(archives_list) == ['i1', 'i3', 'i2', 'loading-indicator']


async def test_archives_list_places_archive_loaded_during_oldest_first_sort_in_sorted_position():
    archives_list, app, load_archives = make_archives_list_app(
        load=(('id3', 'c', 't3'), ('id2', 'b', 't2')), done=False
    )

    async with app.run_test():
        archives_list.action_reverse_sort()
        load_archives()
        assert option_ids(archives_list) == ['id2', 'id3', 'loading-indicator']

        archives_list.on_archive_loaded(module.borgmatic_browse.archive.Archive('id1', 'a', 't1'))

        assert option_ids(archives_list) == ['id1', 'id2', 'id3', 'loading-indicator']


async def test_archives_list_keeps_highlighted_archive_highlighted_when_sorting():
    archives_list, app, load_archives = make_archives_list_app()

    async with app.run_test():
        load_archives()
        archives_list.highlighted = 1
        assert archives_list.options[archives_list.highlighted].id == 'id2'

        archives_list.set_sort_mode('name')

        assert archives_list.options[archives_list.highlighted].id == 'id2'


async def test_archives_list_loading_done_resorts_in_current_order():
    archives_list, app, load_archives = make_archives_list_app(done=False)

    async with app.run_test():
        load_archives()
        archives_list.set_sort_mode('name')
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

        assert option_ids(archives_list) == ['id2', 'id1', 'id3']


@pytest.mark.parametrize('failed', (True, False))
def test_archives_list_load_failed_reflects_archive_loaded_signal(failed):
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    archives_list.archive_loaded.failed = failed

    assert archives_list.load_failed is failed


def test_archives_list_load_failed_is_read_only():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())

    with pytest.raises(AttributeError):
        archives_list.load_failed = True


@pytest.mark.parametrize(
    'config,expected',
    (
        ({'match_archives': '*'}, 'This repository has no archives.'),
        ({'match_archives': 're:.*'}, 'This repository has no archives.'),
        ({'match_archives': 'sh:*'}, 'This repository has no archives.'),
        (
            {'match_archives': 'host-*'},
            'No archives match "host-*". Use -a \'*\' to list them all.',
        ),
        (
            {'match_archives': 'bad[/x]'},
            'No archives match "bad[/x]". Use -a \'*\' to list them all.',
        ),
        (
            {},
            "No archives match the configured archive name format. Use -a '*' to list them all.",
        ),
        (
            {'match_archives': None},
            "No archives match the configured archive name format. Use -a '*' to list them all.",
        ),
    ),
)
def test_make_no_archives_message_describes_why_no_archives_are_shown(config, expected):
    assert module.make_no_archives_message(config) == expected


def test_no_archives_option_id_is_no_archives():
    assert module.NO_ARCHIVES_OPTION_ID == 'no-archives'


def make_no_archives_app(config=None, failed=False):
    '''
    Return an Archives_list with the given configuration dict and an app to run it in. Loading is
    mocked out, so the caller decides which signals the list receives.
    '''
    flexmock(module.borgmatic_browse.workers).should_receive('add_repository_archives')
    archives_list = module.Archives_list(
        config={'match_archives': 'bad[/x]'} if config is None else config,
        repository=flexmock(),
    )
    archives_list.archive_loaded.failed = failed

    class Test_app(textual.app.App):
        def compose(self):
            yield archives_list

    return archives_list, Test_app()


async def test_archives_list_with_no_archives_loaded_adds_one_disabled_dim_text_option():
    archives_list, app = make_no_archives_app()

    async with app.run_test():
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

        assert option_ids(archives_list) == ['no-archives']
        option = archives_list.get_option('no-archives')
        assert option.disabled is True
        assert isinstance(option.prompt, rich.text.Text)
        assert option.prompt.plain == (
            'No archives match "bad[/x]". Use -a \'*\' to list them all.'
        )
        assert option.prompt.style == 'dim'


async def test_archives_list_with_no_archives_loaded_and_all_archives_pattern_says_repository_is_empty():
    archives_list, app = make_no_archives_app(config={'match_archives': '*'})

    async with app.run_test():
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

        option = archives_list.get_option('no-archives')
        assert option.prompt.plain == 'This repository has no archives.'


async def test_archives_list_with_no_archives_loaded_removes_loading_indicator():
    archives_list, app = make_no_archives_app()

    async with app.run_test():
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

        assert 'loading-indicator' not in option_ids(archives_list)


async def test_archives_list_with_failed_loading_does_not_add_no_archives_option():
    archives_list, app = make_no_archives_app(failed=True)

    async with app.run_test():
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

        assert 'no-archives' not in option_ids(archives_list)


async def test_archives_list_with_loaded_archives_does_not_add_no_archives_option():
    archives_list, app = make_no_archives_app()

    async with app.run_test():
        archives_list.on_archive_loaded(
            module.borgmatic_browse.archive.Archive('id', 'archive', '2026-10-31 17:40')
        )
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)

        assert option_ids(archives_list) == ['id']


async def test_archives_list_does_not_select_or_raise_when_enter_is_pressed_on_no_archives_option():
    archives_list, app = make_no_archives_app()
    selected = []

    class Recording_app(type(app)):
        def on_option_list_option_selected(self, event):
            selected.append(event.option_id)

    app = Recording_app()

    async with app.run_test() as pilot:
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)
        archives_list.focus()
        await pilot.pause()

        assert option_ids(archives_list) == ['no-archives']

        await pilot.press('enter')
        await pilot.pause()

        assert selected == []
        assert app._exception is None


async def test_archives_list_sort_options_keeps_no_archives_option_last_in_every_mode_and_direction():
    archives_list, app = make_no_archives_app()

    async with app.run_test():
        options = [
            textual.widgets.option_list.Option('No archives', id='no-archives', disabled=True)
        ]

        for sort_mode in ('time', 'name'):
            for sort_reversed in (False, True):
                archives_list.sort_mode = sort_mode
                archives_list.sort_reversed = sort_reversed

                assert [option.id for option in archives_list.sort_options(options)] == [
                    'no-archives'
                ]


@pytest.mark.parametrize(
    'sort_mode,sort_reversed,expected',
    (
        ('time', False, ['id2', 'id1']),
        ('time', True, ['id1', 'id2']),
        ('name', False, ['id1', 'id2']),
        ('name', True, ['id2', 'id1']),
    ),
)
async def test_archives_list_sort_options_puts_no_archives_option_after_archives(
    sort_mode, sort_reversed, expected
):
    archives_list, app = make_no_archives_app()

    async with app.run_test():
        archives_list.on_archive_loaded(
            module.borgmatic_browse.archive.Archive('id1', 'aaa', '2026-10-31 17:40')
        )
        archives_list.on_archive_loaded(
            module.borgmatic_browse.archive.Archive('id2', 'zzz', '2026-10-30 17:40')
        )
        # Like loading done does, drop the loading indicator before the other option goes in.
        archives_list.remove_option('loading-indicator')
        archives_list.sort_mode = sort_mode
        archives_list.sort_reversed = sort_reversed
        options = [
            textual.widgets.option_list.Option('No archives', id='no-archives', disabled=True),
            *archives_list.options,
        ]

        assert [option.id for option in archives_list.sort_options(options)] == [
            *expected,
            'no-archives',
        ]


async def test_archives_list_sorting_with_no_archives_option_does_not_raise_and_updates_subtitle():
    archives_list, app = make_no_archives_app()

    async with app.run_test() as pilot:
        archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)
        archives_list.focus()
        await pilot.pause()

        for key, subtitle in (
            ('s', 'sort: name ↑'),
            ('r', 'sort: name ↓'),
            ('s', 'sort: time ↓'),
            ('r', 'sort: time ↑'),
        ):
            await pilot.press(key)
            await pilot.pause()

            assert app._exception is None
            assert archives_list.border_subtitle == subtitle
            assert option_ids(archives_list) == ['no-archives']
