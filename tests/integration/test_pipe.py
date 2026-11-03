import pytest
import textual.app
import textual.widgets
from flexmock import flexmock

from borgmatic_browse import pipe as module


class Pipe_test_app(textual.app.App):
    def __init__(self, command_history=None):
        super().__init__()
        self.command_history = command_history if command_history is not None else []


def log_text(rich_log):
    '''
    Given a textual.widgets.RichLog, return the plain text of everything written to it.
    '''
    return '\n'.join(strip.text for strip in rich_log.lines)


def make_command_output(command='jq .', file_path='etc/foo.json'):
    return module.Command_output(
        {'repositories': [{'path': 'test.borg'}]},
        {'path': 'test.borg'},
        'archive',
        file_path,
        command,
    )


def make_result(output=b'', exit_code=0, truncated=False):
    return module.borgmatic_browse.archive.Command_result(output, exit_code, truncated)


async def push_prompt(app, pilot, history):
    results = []
    app.push_screen(module.Command_prompt('etc/foo.json', history), results.append)
    await pilot.pause()

    return results, app.screen.query_one('#command', textual.widgets.Input)


async def push_output(app, pilot, **kwargs):
    flexmock(module.borgmatic_browse.workers).should_receive('pipe_file')
    screen = make_command_output(**kwargs)
    app.push_screen(screen)
    await pilot.pause()

    return screen, screen.query_one('#command-output', textual.widgets.RichLog)


# Command_prompt


async def test_command_prompt_shows_file_path_in_label():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        await push_prompt(app, pilot, [])

        assert any(
            'Pipe etc/foo.json to:' in str(label.render())
            for label in app.screen.query(textual.widgets.Label)
        )


async def test_command_prompt_with_file_path_that_looks_like_markup_shows_it_literally():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        app.push_screen(module.Command_prompt('etc/[bold]foo[/].txt', []))
        await pilot.pause()

        assert any(
            'Pipe etc/[bold]foo[/].txt to:' in str(label.render())
            for label in app.screen.query(textual.widgets.Label)
        )


async def test_command_prompt_prefills_most_recent_command():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _results, command_input = await push_prompt(app, pilot, ['wc -l', 'jq .'])

        assert command_input.value == 'jq .'


async def test_command_prompt_without_history_starts_empty():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _results, command_input = await push_prompt(app, pilot, [])

        assert command_input.value == ''


async def test_command_prompt_up_and_down_step_through_history():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _results, command_input = await push_prompt(app, pilot, ['first', 'second', 'third'])

        await pilot.press('up')
        assert command_input.value == 'second'

        await pilot.press('up')
        assert command_input.value == 'first'

        await pilot.press('down')
        assert command_input.value == 'second'


async def test_command_prompt_up_at_oldest_entry_stays_there():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _results, command_input = await push_prompt(app, pilot, ['first', 'second'])

        await pilot.press('up', 'up', 'up')

        assert command_input.value == 'first'


async def test_command_prompt_down_past_newest_entry_clears_value():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _results, command_input = await push_prompt(app, pilot, ['first', 'second'])

        await pilot.press('down')

        assert command_input.value == ''


async def test_command_prompt_up_and_down_with_empty_history_leave_value_empty():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _results, command_input = await push_prompt(app, pilot, [])

        await pilot.press('up')
        assert command_input.value == ''

        await pilot.press('down')
        assert command_input.value == ''


async def test_command_prompt_up_after_down_past_end_returns_to_newest_entry():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _results, command_input = await push_prompt(app, pilot, ['first', 'second'])

        await pilot.press('down')
        await pilot.press('up')

        assert command_input.value == 'second'


async def test_command_prompt_enter_dismisses_with_stripped_command():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        results, command_input = await push_prompt(app, pilot, [])
        command_input.value = '  jq . | head  '

        await pilot.press('enter')
        await pilot.pause()

        assert results == ['jq . | head']


async def test_command_prompt_enter_with_prefilled_history_dismisses_with_that_command():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        results, _command_input = await push_prompt(app, pilot, ['wc -l'])

        await pilot.press('enter')
        await pilot.pause()

        assert results == ['wc -l']


@pytest.mark.parametrize('blank', ('', '   '))
async def test_command_prompt_enter_with_blank_command_dismisses_with_none(blank):
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        results, command_input = await push_prompt(app, pilot, [])
        command_input.value = blank

        await pilot.press('enter')
        await pilot.pause()

        assert results == [None]


async def test_command_prompt_escape_dismisses_with_none():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        results, _command_input = await push_prompt(app, pilot, ['wc -l'])

        await pilot.press('escape')
        await pilot.pause()

        assert results == [None]


# Command_output


def test_command_output_has_command_loaded_signal():
    screen = make_command_output()

    assert isinstance(
        screen.command_output_loaded, module.borgmatic_browse.workers.Command_output_loaded
    )


async def test_command_output_on_mount_subscribes_then_starts_piping_worker():
    app = Pipe_test_app()
    captured = {}
    config = {'repositories': [{'path': 'test.borg'}]}
    repository = {'path': 'test.borg'}
    screen = module.Command_output(config, repository, 'archive', 'etc/foo.json', 'jq .')
    flexmock(screen.command_output_loaded).should_receive('subscribe').with_args(
        screen, screen.on_command_output_loaded
    ).once().ordered()

    def pipe_file(*args, **kwargs):
        captured['args'] = args
        captured['kwargs'] = kwargs

    flexmock(module.borgmatic_browse.workers).should_receive('pipe_file').replace_with(
        pipe_file
    ).once().ordered()

    async with app.run_test() as pilot:
        app.push_screen(screen)
        await pilot.pause()

    assert captured['args'] == (app,)
    assert captured['kwargs'] == {
        'command_output_loaded': screen.command_output_loaded,
        'config': config,
        'repository': repository,
        'archive_name': 'archive',
        'file_path': 'etc/foo.json',
        'command': 'jq .',
    }


async def test_command_output_shows_command_in_border_title_and_loading_indicator():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        _screen, rich_log = await push_output(app, pilot, command='jq .')

        assert '| jq .' in rich_log.border_title
        assert 'loading' in log_text(rich_log)


async def test_command_output_renders_ansi_colours_as_styled_text_without_escape_codes():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.on_command_output_loaded(make_result(b'\x1b[31mred\x1b[0m plain\n'))
        await pilot.pause()

        assert 'red plain' in log_text(rich_log)
        assert '\x1b' not in log_text(rich_log)
        assert 'loading' not in log_text(rich_log)
        assert any(
            segment.style and segment.style.color
            for strip in rich_log.lines
            for segment in strip
            if 'red' in segment.text
        )


async def test_command_output_with_invalid_utf8_does_not_raise():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.on_command_output_loaded(make_result(b'ok \xff\xfe done\n'))
        await pilot.pause()

        assert 'ok' in log_text(rich_log)
        assert 'done' in log_text(rich_log)


async def test_command_output_with_no_output_says_so():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.on_command_output_loaded(make_result(b''))
        await pilot.pause()

        assert module.NO_OUTPUT_MESSAGE in log_text(rich_log)


@pytest.mark.parametrize('exit_code', (0, 1, 127, -15))
async def test_command_output_shows_exit_status_in_subtitle(exit_code):
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.on_command_output_loaded(make_result(b'hi\n', exit_code=exit_code))
        await pilot.pause()

        assert rich_log.border_subtitle == f'exit status {exit_code}'


async def test_command_output_with_truncated_result_says_output_was_cut_off():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.on_command_output_loaded(make_result(b'lots\n', exit_code=-15, truncated=True))
        await pilot.pause()

        assert 'lots' in log_text(rich_log)
        assert 'Output over 1,000,000 bytes was cut off, and the command was stopped.' in log_text(
            rich_log
        )


async def test_command_output_with_untruncated_result_does_not_say_cut_off():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.on_command_output_loaded(make_result(b'lots\n'))
        await pilot.pause()

        assert 'cut off' not in log_text(rich_log)


async def test_command_output_with_loading_failed_shows_error_message_then_failure_message():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)
        screen.command_output_loaded.error_message = 'Error piping etc/foo.json: Repository gone.'

        screen.on_command_output_loaded(module.borgmatic_browse.workers.LOADING_FAILED)
        await pilot.pause()

        text = log_text(rich_log)
        assert 'Error piping etc/foo.json: Repository gone.' in text
        assert module.FAILED_MESSAGE in text
        assert text.index('Repository gone.') < text.index(module.FAILED_MESSAGE)
        assert 'loading' not in text.replace('Error piping', '')
        assert not rich_log.border_subtitle


async def test_command_output_with_loading_failed_and_no_error_message_shows_fallback():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)
        assert screen.command_output_loaded.error_message is None

        screen.on_command_output_loaded(module.borgmatic_browse.workers.LOADING_FAILED)
        await pilot.pause()

        text = log_text(rich_log)
        assert 'Error piping this file.' in text
        assert module.FAILED_MESSAGE in text
        assert not rich_log.border_subtitle


async def test_command_output_with_loading_failed_shows_markup_looking_error_literally():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)
        screen.command_output_loaded.error_message = 'Error: [bold]bad[/bold] [/] path[$var]'

        screen.on_command_output_loaded(module.borgmatic_browse.workers.LOADING_FAILED)
        await pilot.pause()

        assert 'Error: [bold]bad[/bold] [/] path[$var]' in log_text(rich_log)


def test_failed_message_only_tells_user_to_close_and_view_logs():
    assert module.FAILED_MESSAGE == 'Close this and press v to view the logs.'


async def test_command_output_receives_result_published_on_signal():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.command_output_loaded.publish(make_result(b'from signal\n', exit_code=2))
        await pilot.pause()

        assert 'from signal' in log_text(rich_log)
        assert rich_log.border_subtitle == 'exit status 2'


async def test_command_output_result_is_not_parsed_as_markup():
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, rich_log = await push_output(app, pilot)

        screen.on_command_output_loaded(make_result(b'[bold]not markup[/bold]\n'))
        await pilot.pause()

        assert '[bold]not markup[/bold]' in log_text(rich_log)


@pytest.mark.parametrize('key', ('escape', 'q'))
async def test_command_output_close_key_dismisses_screen_without_quitting_app(key):
    app = Pipe_test_app()

    async with app.run_test() as pilot:
        screen, _rich_log = await push_output(app, pilot)
        assert app.screen is screen

        await pilot.press(key)
        await pilot.pause()

        assert app.screen is not screen
        assert not isinstance(app.screen, module.Command_output)
        assert not app._exit


@pytest.mark.parametrize('key', ('escape', 'q'))
async def test_command_output_close_before_result_cancels_and_stops_processes(key):
    app = Pipe_test_app()
    processes = (flexmock(), flexmock())
    flexmock(module.borgmatic_browse.archive).should_receive('stop_processes').with_args(
        *processes
    ).once()

    async with app.run_test() as pilot:
        screen, _rich_log = await push_output(app, pilot)
        screen.command_output_loaded.processes = processes

        await pilot.press(key)
        await pilot.pause()

        assert screen.command_output_loaded.cancelled is True


async def test_command_output_close_before_processes_start_cancels_without_stopping_anything():
    app = Pipe_test_app()
    flexmock(module.borgmatic_browse.archive).should_receive('stop_processes').never()

    async with app.run_test() as pilot:
        screen, _rich_log = await push_output(app, pilot)

        await pilot.press('escape')
        await pilot.pause()

        assert screen.command_output_loaded.cancelled is True
        assert app.screen is not screen


async def test_command_output_close_after_result_does_not_stop_processes():
    app = Pipe_test_app()
    processes = (flexmock(), flexmock())
    flexmock(module.borgmatic_browse.archive).should_receive('stop_processes').never()

    async with app.run_test() as pilot:
        screen, _rich_log = await push_output(app, pilot)
        screen.command_output_loaded.processes = processes
        screen.on_command_output_loaded(make_result(b'done\n'))

        await pilot.press('escape')
        await pilot.pause()

        assert app.screen is not screen


async def test_command_output_close_after_failure_does_not_stop_processes():
    app = Pipe_test_app()
    flexmock(module.borgmatic_browse.archive).should_receive('stop_processes').never()

    async with app.run_test() as pilot:
        screen, _rich_log = await push_output(app, pilot)
        screen.command_output_loaded.processes = (flexmock(), flexmock())
        screen.on_command_output_loaded(module.borgmatic_browse.workers.LOADING_FAILED)

        await pilot.press('q')
        await pilot.pause()

        assert app.screen is not screen


# pipe_file


def make_pipe_app(command_history):
    '''
    Return a fake app recording the screens pushed to it and their callbacks.
    '''
    pushed = []
    app = flexmock(command_history=command_history)
    app.should_receive('push_screen').replace_with(
        lambda screen, callback=None: pushed.append((screen, callback))
    )

    return app, pushed


def test_pipe_file_pushes_command_prompt_with_history():
    app, pushed = make_pipe_app(['old'])
    prompt = flexmock()
    flexmock(module).should_receive('Command_prompt').with_args('etc/foo.json', ['old']).and_return(
        prompt
    ).once()

    module.pipe_file(app, {}, {}, 'archive', 'etc/foo.json')

    assert len(pushed) == 1
    assert pushed[0][0] is prompt
    assert callable(pushed[0][1])


def test_pipe_file_with_command_records_history_and_pushes_command_output():
    app, pushed = make_pipe_app(['old'])
    config, repository = {'a': 1}, {'path': 'test.borg'}
    output_screen = flexmock()
    flexmock(module).should_receive('Command_prompt').and_return(flexmock())
    flexmock(module).should_receive('Command_output').with_args(
        config, repository, 'archive', 'etc/foo.json', 'jq .'
    ).and_return(output_screen).once()

    module.pipe_file(app, config, repository, 'archive', 'etc/foo.json')
    pushed[0][1]('jq .')

    assert app.command_history == ['old', 'jq .']
    assert len(pushed) == 2
    assert pushed[1][0] is output_screen


def test_pipe_file_with_command_equal_to_last_history_entry_does_not_duplicate_it():
    app, pushed = make_pipe_app(['old', 'jq .'])
    output_screen = flexmock()
    flexmock(module).should_receive('Command_prompt').and_return(flexmock())
    flexmock(module).should_receive('Command_output').and_return(output_screen).once()

    module.pipe_file(app, {}, {}, 'archive', 'etc/foo.json')
    pushed[0][1]('jq .')

    assert app.command_history == ['old', 'jq .']
    assert pushed[1][0] is output_screen


def test_pipe_file_with_command_equal_to_older_history_entry_appends_it_again():
    app, pushed = make_pipe_app(['jq .', 'wc -l'])
    flexmock(module).should_receive('Command_prompt').and_return(flexmock())
    flexmock(module).should_receive('Command_output').and_return(flexmock())

    module.pipe_file(app, {}, {}, 'archive', 'etc/foo.json')
    pushed[0][1]('jq .')

    assert app.command_history == ['jq .', 'wc -l', 'jq .']


def test_pipe_file_with_no_command_does_nothing():
    app, pushed = make_pipe_app(['old'])
    flexmock(module).should_receive('Command_prompt').and_return(flexmock())
    flexmock(module).should_receive('Command_output').never()

    module.pipe_file(app, {}, {}, 'archive', 'etc/foo.json')
    pushed[0][1](None)

    assert app.command_history == ['old']
    assert len(pushed) == 1


async def test_pipe_file_shows_prompt_then_output_in_real_app():
    app = Pipe_test_app()
    flexmock(module.borgmatic_browse.workers).should_receive('pipe_file')

    async with app.run_test() as pilot:
        module.pipe_file(app, {}, {'path': 'test.borg'}, 'archive', 'etc/foo.json')
        await pilot.pause()
        assert isinstance(app.screen, module.Command_prompt)

        app.screen.query_one('#command', textual.widgets.Input).value = 'cat'
        await pilot.press('enter')
        await pilot.pause()

        assert isinstance(app.screen, module.Command_output)
        assert app.command_history == ['cat']
