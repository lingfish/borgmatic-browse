import rich.text
import textual.binding
import textual.containers
import textual.screen
import textual.widgets

import borgmatic_browse.archive
import borgmatic_browse.loading
import borgmatic_browse.workers

NO_OUTPUT_MESSAGE = '(no output)'
FAILED_MESSAGE = 'Close this and press v to view the logs.'
TRUNCATED_MESSAGE = (
    f'Output over {borgmatic_browse.archive.MAXIMUM_COMMAND_OUTPUT_SIZE:,} bytes was cut off, and '
    'the command was stopped.'
)


class Command_prompt(textual.screen.ModalScreen):
    '''
    A modal screen asking for a shell command to pipe a file to. Dismissing it gives the command, or
    None if the user cancelled or didn't enter one.
    '''

    BINDINGS = (
        textual.binding.Binding(key='escape', action='cancel', description='cancel'),
        textual.binding.Binding(key='up', action='history(-1)', show=False),
        textual.binding.Binding(key='down', action='history(1)', show=False),
    )
    DEFAULT_CSS = '''
        Command_prompt {
            align: center middle;
        }

        Command_prompt > Vertical {
            border: round $primary;
            width: 80%;
            height: auto;
            padding: 0 1;
        }
    '''

    def __init__(self, file_path, history):
        '''
        Given the path of the file to pipe and a list of previously entered commands, oldest first,
        prepare to ask for a command, starting with the most recent one.
        '''
        self.file_path = file_path
        self.history = history
        self.history_index = max(len(history) - 1, 0)

        super().__init__()

    def compose(self):
        '''
        Compose a label saying which file is being piped, and an input for the command.
        '''
        with textual.containers.Vertical():
            yield textual.widgets.Label(rich.text.Text(f'Pipe {self.file_path} to:'))
            yield textual.widgets.Input(
                value=self.history[-1] if self.history else '',
                placeholder='A shell command, like: jq .',
                id='command',
            )

    def action_history(self, step):
        '''
        Given a step of -1 or 1, go back or forward through previously entered commands. Stop at the
        oldest one, and clear the input after the newest one.
        '''
        self.history_index = min(max(self.history_index + step, 0), len(self.history))
        self.query_one('#command', textual.widgets.Input).value = (
            self.history[self.history_index] if self.history_index < len(self.history) else ''
        )

    def action_cancel(self):
        '''
        Dismiss this screen without a command.
        '''
        self.dismiss(None)

    def on_input_submitted(self, event):
        '''
        When the user enters a command, dismiss this screen with it, or with None if it's blank.
        '''
        self.dismiss(event.value.strip() or None)


class Command_output(textual.screen.ModalScreen):
    '''
    A modal screen that pipes a file stored in a Borg archive to a shell command and shows the
    command's output.
    '''

    BINDINGS = (textual.binding.Binding(key='escape,q', action='close', description='close'),)
    DEFAULT_CSS = '''
        Command_output {
            align: center middle;
        }

        Command_output > RichLog {
            border: round $primary;
            border-title-color: $text-primary;
            width: 90%;
            height: 90%;
        }
    '''

    def __init__(self, config, repository, archive_name, file_path, command):
        '''
        Given a configuration dict, a repository dict, an archive name or ID to give Borg, the path
        of a file in the archive, and a shell command, prepare to pipe the file to the command.
        Piping kicks off in on_mount() below.
        '''
        self.config = config
        self.repository = repository
        self.archive_name = archive_name
        self.file_path = file_path
        self.command = command
        self.result_loaded = False
        self.loading_timer = None
        self.command_output_loaded = borgmatic_browse.workers.Command_output_loaded(
            self, 'command output loaded'
        )

        super().__init__()

    def compose(self):
        '''
        Compose a log for the command's output, titled with the command.
        '''
        rich_log = textual.widgets.RichLog(wrap=True, id='command-output')
        rich_log.border_title = rich.text.Text(f'| {self.command}')

        yield rich_log

    def on_mount(self):
        '''
        Show a loading indicator, subscribe to the command's result, and then start piping the file
        to the command, so that the result can't be missed.
        '''
        rich_log = self.query_one('#command-output', textual.widgets.RichLog)
        self.loading_timer = borgmatic_browse.loading.add_inline_loading_indicator(rich_log)
        self.command_output_loaded.subscribe(self, self.on_command_output_loaded)

        borgmatic_browse.workers.pipe_file(
            self.app,
            command_output_loaded=self.command_output_loaded,
            config=self.config,
            repository=self.repository,
            archive_name=self.archive_name,
            file_path=self.file_path,
            command=self.command,
        )

    def on_command_output_loaded(self, result):
        '''
        When the command finishes, show its output with any ANSI colours, and its exit status. Say
        if its output was cut off. But if piping failed, show the error instead.
        '''
        self.result_loaded = True
        self.loading_timer.stop()
        rich_log = self.query_one('#command-output', textual.widgets.RichLog)
        rich_log.clear()

        if result is borgmatic_browse.workers.LOADING_FAILED:
            rich_log.write(
                rich.text.Text(
                    self.command_output_loaded.error_message or 'Error piping this file.'
                )
            )
            rich_log.write(FAILED_MESSAGE)
            return

        rich_log.write(
            rich.text.Text.from_ansi(result.output.decode(errors='replace'))
            if result.output
            else NO_OUTPUT_MESSAGE
        )
        rich_log.border_subtitle = f'exit status {result.exit_code}'

        if result.truncated:
            rich_log.write(TRUNCATED_MESSAGE)

    def action_close(self):
        '''
        Close this screen. If the command is still running, stop it and Borg, and mark it as
        cancelled so that the resulting failure isn't reported.
        '''
        self.command_output_loaded.cancelled = True

        if not self.result_loaded and self.command_output_loaded.processes:
            borgmatic_browse.archive.stop_processes(*self.command_output_loaded.processes)

        self.dismiss()


def pipe_file(app, config, repository, archive_name, file_path):
    '''
    Given a running Browse_app instance, a configuration dict, a repository dict, an archive name or
    ID to give Borg, and the path of a file in the archive, ask the user for a shell command, and
    then pipe the file to it and show the output. Remember the command for next time, unless it's
    the same as the last one.
    '''

    def on_command(command):
        if command is None:
            return

        if command not in app.command_history[-1:]:
            app.command_history.append(command)

        app.push_screen(Command_output(config, repository, archive_name, file_path, command))

    app.push_screen(Command_prompt(file_path, app.command_history), on_command)
