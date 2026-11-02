import pytest
from flexmock import flexmock

import borgmatic_browse.app
import borgmatic_browse.archive
import borgmatic_browse.archives_list
import borgmatic_browse.carousel
import borgmatic_browse.logs
import borgmatic_browse.repositories_list


def make_app(match_archives='bad[/x]', archives=()):
    config = {'repositories': [{'path': 'test1.borg'}]}

    if match_archives is not None:
        config['match_archives'] = match_archives

    app = borgmatic_browse.app.Browse_app(configs={'test1.yaml': config})
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        archives
    )

    return app


async def open_archives_list(app, pilot):
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    await pilot.pause()

    return app.query_one(borgmatic_browse.archives_list.Archives_list)


def painted_lines(panel):
    return [panel.render_line(y).text.strip() for y in range(panel.size.height)]


@pytest.mark.parametrize(
    'match_archives,expected',
    (
        ('bad[/x]', 'No archives match "bad[/x]". Use -a \'*\' to list them all.'),
        ('[bold]x', 'No archives match "[bold]x". Use -a \'*\' to list them all.'),
        ('*', 'This repository has no archives.'),
        (
            None,
            "No archives match the configured archive name format. Use -a '*' to list them all.",
        ),
    ),
)
async def test_empty_archives_list_paints_the_no_archives_message_literally(
    match_archives, expected
):
    app = make_app(match_archives=match_archives)

    async with app.run_test(size=(120, 40)) as pilot:
        archives_list = await open_archives_list(app, pilot)

        assert app.focused is archives_list
        assert app._exception is None
        assert expected in painted_lines(archives_list)[:3]
        assert [option.id for option in archives_list.options] == ['no-archives']
        assert not any('loading' in line for line in painted_lines(archives_list))


async def test_empty_archives_list_does_not_advance_when_enter_is_pressed():
    app = make_app()

    async with app.run_test(size=(120, 40)) as pilot:
        archives_list = await open_archives_list(app, pilot)
        carousel = app.query_one(borgmatic_browse.carousel.Carousel)

        assert [option.id for option in archives_list.options] == ['no-archives']

        await pilot.press('enter')
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app._exception is None
        assert carousel.focused_panel is archives_list
        assert len(carousel.panels) == 2


async def test_left_from_empty_archives_list_goes_back_to_repositories_list():
    app = make_app()

    async with app.run_test(size=(120, 40)) as pilot:
        archives_list = await open_archives_list(app, pilot)

        assert [option.id for option in archives_list.options] == ['no-archives']

        await pilot.press('left')
        await pilot.pause()

        carousel = app.query_one(borgmatic_browse.carousel.Carousel)

        assert isinstance(
            carousel.focused_panel, borgmatic_browse.repositories_list.Repositories_list
        )


async def test_selecting_repository_again_after_empty_archives_list_does_not_rerun_borg():
    app = make_app()
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        ()
    ).once()

    async with app.run_test(size=(120, 40)) as pilot:
        archives_list = await open_archives_list(app, pilot)

        assert [option.id for option in archives_list.options] == ['no-archives']

        await pilot.press('left')
        await pilot.pause()
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        await pilot.pause()

        carousel = app.query_one(borgmatic_browse.carousel.Carousel)

        assert carousel.focused_panel is archives_list
        assert archives_list.load_failed is False


async def test_empty_archives_list_highlights_nothing_and_keeps_it_that_way_when_keys_are_pressed():
    app = make_app()

    async with app.run_test(size=(120, 40)) as pilot:
        archives_list = await open_archives_list(app, pilot)

        assert [option.id for option in archives_list.options] == ['no-archives']
        assert archives_list.highlighted is None

        for key in ('j', 'down', 'enter', 's', 'r'):
            await pilot.press(key)
            await pilot.pause()

            assert archives_list.highlighted is None
