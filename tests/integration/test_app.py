import contextlib
import subprocess

import pytest
import textual.widgets._toast
import textual.worker
from flexmock import flexmock

import borgmatic_browse.app
import borgmatic_browse.archive
import borgmatic_browse.archives_list
import borgmatic_browse.configuration_files_list
import borgmatic_browse.file_preview
import borgmatic_browse.logs
import borgmatic_browse.repositories_list


async def test_browse_app_with_multiple_configs_uses_configuration_files_list():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test():
        app.query_one(selector='Header')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1
        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].configs == app.configs

        app.query_one(selector='Logs')
        app.query_one(selector='Footer')


async def test_browse_app_with_one_config_uses_repositories_list():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test():
        app.query_one(selector='Header')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1
        assert isinstance(carousel.panels[0], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[0].config == app.configs['test1.yaml']

        app.query_one(selector='Logs')
        app.query_one(selector='Footer')


async def test_browse_app_quit_key_terminates_child_processes_and_exits():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.app).should_receive('terminate_child_processes').once()

    async with app.run_test() as pilot:
        await pilot.press('q')
        await pilot.pause()

    assert app.return_code == 0


async def test_browse_app_with_unexpected_error_in_worker_has_error_return_code():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        RuntimeError('boom')
    )

    with pytest.raises(textual.worker.WorkerFailed, match='boom'):
        async with app.run_test() as pilot:
            await pilot.press('enter')
            await app.workers.wait_for_complete()
            await pilot.pause()

    assert app.return_code == 1


async def test_browse_app_with_borg_error_has_success_return_code_after_quitting():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        subprocess.CalledProcessError(13, 'borg list', output='Repository /x does not exist.')
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app.is_running

        await pilot.press('q')
        await pilot.pause()

    assert app.return_code == 0


async def test_browse_app_key_toggles_logs_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        logs_panel = app.query_one('#logs')

        await pilot.press('v')
        await pilot.pause()
        assert logs_panel.styles.display == 'block'


async def test_browse_app_with_borg_error_loading_archives_stays_running_and_notifies():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        subprocess.CalledProcessError(13, 'borg list', output='Repository /x does not exist.')
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app._exception is None
        assert app.is_running

        archives_list = app.query_one(borgmatic_browse.archives_list.Archives_list)
        assert app.focused is archives_list
        assert 'loading-indicator' not in {option.id for option in archives_list.options}
        assert any('does not exist' in notification.message for notification in app._notifications)

        await pilot.press('left')
        await pilot.pause()

        assert isinstance(app.focused, borgmatic_browse.repositories_list.Repositories_list)


@pytest.mark.parametrize(
    'text',
    ('x[$var]', 'back\\', 'end\\[', 'a\\[b]', 'bad[/name]', '[bold]x', '[/]', 'plain'),
)
async def test_browse_app_with_markup_like_borg_error_shows_it_literally_in_notification(text):
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        subprocess.CalledProcessError(13, 'borg', output=text)
    )

    async with app.run_test(notifications=True) as pilot:
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert app._exception is None

        toasts = app.screen.query(textual.widgets._toast.Toast)
        assert len(toasts) == 1
        assert toasts.first().render().plain == f'Error listing repository: {text}'


def make_shell_app():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (borgmatic_browse.archive.Archive('i1', 'aa', '2026-10-30 10:00'),)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').and_return(
        (borgmatic_browse.archive.Archive_path('-', 'a.txt', '', 3, '2026-01-01T00:00:00'),)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_file_content').and_return('hi')

    return app


def stub_shell(monkeypatch):
    '''
    Given a monkeypatch fixture, replace App.suspend with a no-op and subprocess.run with a
    recorder, so that no real shell ever starts, and return the list of recorded run arguments.
    '''
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    calls = []

    @contextlib.contextmanager
    def suspend(self):
        yield

    def run(*args, **kwargs):
        calls.append(args)

        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(borgmatic_browse.app.Browse_app, 'suspend', suspend)
    monkeypatch.setattr(subprocess, 'run', run)
    monkeypatch.setattr(borgmatic_browse.app, 'get_foreground_process_group', lambda: None)
    monkeypatch.setattr(
        borgmatic_browse.app,
        'restore_foreground_process_group',
        lambda process_group: None,
    )

    return calls


async def drill_to_panel(app, pilot, presses):
    for key in presses:
        await pilot.press(key)
        await app.workers.wait_for_complete()
        await pilot.pause()


@pytest.mark.parametrize(
    'presses',
    (
        (),
        ('enter',),
        ('enter', 'enter'),
        ('enter', 'enter', 'enter'),
    ),
    ids=('repositories', 'archives', 'directory', 'file preview'),
)
async def test_browse_app_b_key_opens_shell_from_every_panel(monkeypatch, presses):
    calls = stub_shell(monkeypatch)
    app = make_shell_app()

    async with app.run_test() as pilot:
        await drill_to_panel(app, pilot, presses)
        await pilot.press('b')
        await pilot.pause()

    assert calls == [(('/bin/fancysh',),)]


async def test_browse_app_b_key_opens_shell_from_configuration_files_list(monkeypatch):
    calls = stub_shell(monkeypatch)
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        assert isinstance(
            app.focused, borgmatic_browse.configuration_files_list.Configuration_files_list
        )

        await pilot.press('b')
        await pilot.pause()

    assert calls == [(('/bin/fancysh',),)]


async def test_browse_app_b_key_from_file_preview_really_reaches_file_preview(monkeypatch):
    calls = stub_shell(monkeypatch)
    app = make_shell_app()

    async with app.run_test() as pilot:
        await drill_to_panel(app, pilot, ('enter', 'enter', 'enter'))

        assert isinstance(app.focused, borgmatic_browse.file_preview.File_preview)

        await pilot.press('b')
        await pilot.pause()

    assert len(calls) == 1


async def test_browse_app_b_key_when_suspend_not_supported_notifies_warning_and_skips_shell(
    monkeypatch,
):
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    calls = []
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: calls.append(args))
    app = make_shell_app()

    async with app.run_test(notifications=True) as pilot:
        assert not app._driver.can_suspend

        await pilot.press('b')
        await pilot.pause()

        assert app._exception is None
        assert calls == []
        assert [
            (notification.message, notification.severity) for notification in app._notifications
        ] == [('Opening a shell is not supported here', 'warning')]


async def test_browse_app_footer_shows_shell_binding():
    app = make_shell_app()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        shown = {
            active.binding.key: active.binding.description
            for active in app.screen.active_bindings.values()
            if active.binding.show and active.enabled
        }

        assert shown.get('b') == 'shell'

        footer = app.query_one('Footer')
        strips = app.screen._compositor.render_strips()
        footer_text = ''.join(segment.text for segment in strips[footer.region.y])

        assert 'b shell' in footer_text


def test_browse_app_starts_with_empty_command_history():
    app = borgmatic_browse.app.Browse_app(configs={'test.yaml': {'repositories': []}})

    assert app.command_history == []


def test_browse_app_command_history_is_not_shared_between_apps():
    first = borgmatic_browse.app.Browse_app(configs={})
    second = borgmatic_browse.app.Browse_app(configs={})
    first.command_history.append('jq .')

    assert second.command_history == []
