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
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    flexmock(loading_timer).should_receive('stop')
    flexmock(archives_list).should_receive('remove_option').with_args('loading-indicator').once()
    flexmock(archives_list).should_receive('add_options').never()

    archives_list.on_archive_loaded(module.borgmatic_browse.workers.LOADING_DONE)


def test_archives_list_on_archive_loaded_adds_archive_name():
    loading_timer = flexmock()
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(loading_timer)
    archives_list = module.Archives_list(config=flexmock(), repository=flexmock())
    flexmock(loading_timer).should_receive('stop').never()
    loading_indicator = flexmock()
    flexmock(archives_list).should_receive('get_option').and_return(loading_indicator)
    flexmock(archives_list).should_receive('remove_option').with_args('loading-indicator').once()
    flexmock(archives_list).should_receive('add_options').once()

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
