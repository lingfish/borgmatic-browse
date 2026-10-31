import contextlib

import psutil
import textual.app
import textual.binding
import textual.widgets

import borgmatic_browse.carousel
import borgmatic_browse.configuration_files_list
import borgmatic_browse.logs
import borgmatic_browse.repositories_list


def terminate_child_processes():
    '''
    Terminate every child process of this process, recursively, such as a Borg subprocess started
    by a worker thread (and any SSH process that Borg itself started). Ignore any process that has
    already exited.

    Worker threads block while reading Borg's output, and Python waits for them at exit, so without
    this a long-running Borg command would delay quitting until it finished.
    '''
    for child in psutil.Process().children(recursive=True):
        with contextlib.suppress(psutil.NoSuchProcess):
            child.terminate()


class Browse_app(textual.app.App):
    '''
    The main app / entry point for the browse action UI.
    '''

    BINDINGS = (
        textual.binding.Binding(key='q', action='quit', description='quit'),
        textual.binding.Binding(key='v', action='toggle_logs', description='view logs'),
        textual.binding.Binding(
            key='c', action='command_palette', description='commands', show=False
        ),
    )
    COMMAND_PALETTE_BINDING = 'c'
    CSS = '''
        .panel {
            border: round $primary;
            border-title-color: $text-primary;
            width: 100%;
            height: 100%;
        }

        #logs {
            width: 100%;
            height: 50%;
            display: none;
        }
    '''

    def __init__(self, configs):
        self.configs = configs

        super().__init__()

    def get_system_commands(self, screen):  # pragma: no cover
        '''
        Remove the screenshot system command because it produces broken screenshots. (Emoji
        weirdness, etc.) Also remove minimize and maximize because they don't accomplish much with
        out particular layout.
        '''
        yield from (
            command
            for command in super().get_system_commands(screen)
            if command.title not in {'Screenshot', 'Minimize', 'Maximize'}
        )

    def compose(self):
        '''
        Compose a UI consisting of:

          * a header with the application name
          * a carousel container that contains the main UI panels
          * a logs panel where Python logs show up (panel hidden by default)
          * a footer with available keys listed
        '''
        yield textual.widgets.Header()
        yield borgmatic_browse.carousel.Carousel(
            [borgmatic_browse.configuration_files_list.Configuration_files_list(self.configs)]
            if len(self.configs) > 1
            else [
                borgmatic_browse.repositories_list.Repositories_list(
                    next(iter(self.configs.values()))
                )
            ]
        )

        logs_panel = borgmatic_browse.logs.Logs()
        yield logs_panel
        yield textual.widgets.Footer()

        borgmatic_browse.logs.log_to_widget(logs_panel)

    def on_mount(self):
        '''
        Set the application title, which ends up in the header.
        '''
        self.title = 'borgmatic browse'

    def action_toggle_logs(self):
        '''
        Toggle the show/hide status of the logs panel.
        '''
        logs_panel = self.query_one('#logs')
        logs_panel.styles.display = 'none' if logs_panel.styles.display == 'block' else 'block'

    def exit(self, *args, **kwargs):
        '''
        Exit the application. But first terminate any ongoing Borg subprocesses to encourage a fast
        exit.

        Terminate only this process's children rather than signalling the whole process group,
        because a group-wide signal also hits whatever launched the app, and a wrapper like "uv run"
        then forwards the signal back here.
        '''
        terminate_child_processes()

        super().exit(*args, **kwargs)
