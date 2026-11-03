import contextlib
import functools
import os
import signal
import subprocess
import sys

import psutil
import textual.app
import textual.binding
import textual.widgets

import borgmatic_browse.carousel
import borgmatic_browse.configuration_files_list
import borgmatic_browse.logs
import borgmatic_browse.repositories_list
import borgmatic_browse.sorting

DEFAULT_SHELL = '/bin/sh'


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


def get_foreground_process_group():
    '''
    Return the process group in the foreground of the terminal that the app runs in, or None if it
    can't be found, e.g. because standard input isn't a terminal.
    '''
    try:
        return os.tcgetpgrp(sys.__stdin__.fileno())
    except OSError:
        return None


def restore_foreground_process_group(process_group):
    '''
    Given a process group from get_foreground_process_group(), or None, put that process group back
    in the foreground of the terminal if something else is there, e.g. a shell that was killed before
    it could hand the terminal back. Otherwise Textual gets stopped by SIGTTOU when it resumes, which
    leaves the app stuck.

    Ignore SIGTTOU while doing so, since it also stops a background process that changes the terminal.
    Do nothing given None, and ignore any error.
    '''
    if process_group is None:
        return

    with contextlib.suppress(OSError):
        descriptor = sys.__stdin__.fileno()

        if os.tcgetpgrp(descriptor) == process_group:
            return

        previous_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)

        try:
            os.tcsetpgrp(descriptor, process_group)
        finally:
            signal.signal(signal.SIGTTOU, previous_handler)


class Browse_app(textual.app.App):
    '''
    The main app / entry point for the browse action UI.
    '''

    BINDINGS = (
        textual.binding.Binding(key='q', action='quit', description='quit'),
        textual.binding.Binding(key='v', action='toggle_logs', description='view logs'),
        textual.binding.Binding(key='b', action='open_shell', description='shell'),
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

    def get_system_commands(self, screen):
        '''
        Remove the screenshot system command because it produces broken screenshots. (Emoji
        weirdness, etc.) Also remove minimize and maximize because they don't accomplish much with
        out particular layout. And if the focused panel can be sorted, add commands for sorting it.
        '''
        yield from (
            command
            for command in super().get_system_commands(screen)
            if command.title not in {'Screenshot', 'Minimize', 'Maximize'}
        )

        for carousel in screen.query(borgmatic_browse.carousel.Carousel):
            panel = carousel.focused_panel

            if isinstance(panel, borgmatic_browse.sorting.Sortable):
                for mode in panel.SORT_MODES:
                    yield textual.app.SystemCommand(
                        f'Sort by {mode}',
                        f'Sort this list by {mode}',
                        functools.partial(panel.set_sort_mode, mode),
                    )

                yield textual.app.SystemCommand(
                    'Reverse sort order',
                    'Reverse the order of this list',
                    panel.action_reverse_sort,
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

    def action_open_shell(self):
        '''
        Suspend the UI and run the user's shell until it exits. Set an environment variable in the
        shell so that the user can show it in their prompt, since prompts can't be changed reliably
        from here. If the shell can't be run or the UI can't be suspended, notify the user instead. Take
        back the terminal afterwards in case the shell didn't hand it back.

        Catch an error from the shell within the suspend block, because Textual doesn't resume the UI
        if an exception escapes that block. Don't parse the error notification as markup, because the
        message contains a path, which might look like markup.
        '''
        shell = os.environ.get('SHELL') or DEFAULT_SHELL

        try:
            with self.suspend():
                print('Type "exit" to return to borgmatic-browse.', flush=True)  # noqa: T201
                foreground_process_group = get_foreground_process_group()

                try:
                    subprocess.run(  # noqa: S603
                        (shell,), check=False, env={**os.environ, 'BORGMATIC_BROWSE_SHELL': '1'}
                    )
                except OSError as error:
                    self.notify(f'Error opening shell: {error}', severity='error', markup=False)

                restore_foreground_process_group(foreground_process_group)
        except textual.app.SuspendNotSupported:
            self.notify('Opening a shell is not supported here', severity='warning')

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
