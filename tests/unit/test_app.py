import contextlib
import os
import subprocess

import pytest
import textual.app
from flexmock import flexmock

from borgmatic_browse import app as module


def test_terminate_child_processes_terminates_each_child():
    children = (flexmock(), flexmock())
    flexmock(module.psutil).should_receive('Process').and_return(
        flexmock(children=lambda recursive: children)
    )

    for child in children:
        child.should_receive('terminate').once()

    module.terminate_child_processes()


def test_terminate_child_processes_ignores_child_that_already_exited():
    exited_child = flexmock()
    exited_child.should_receive('terminate').and_raise(module.psutil.NoSuchProcess(pid=1))
    running_child = flexmock()
    running_child.should_receive('terminate').once()
    flexmock(module.psutil).should_receive('Process').and_return(
        flexmock(children=lambda recursive: (exited_child, running_child))
    )

    module.terminate_child_processes()


def make_app():
    return module.Browse_app(configs={'test1.yaml': {'repositories': [{'path': 'test1.borg'}]}})


def fake_suspend(events):
    '''
    Given a list to append to, return a replacement for App.suspend that records entering and
    leaving the suspended state.
    '''

    @contextlib.contextmanager
    def suspend():
        events.append('suspend')
        yield
        events.append('resume')

    return suspend


def fake_run(events, calls=None, returncode=0):
    '''
    Given a list to append to, return a replacement for subprocess.run that records that it was
    called, and optionally the arguments it was called with, rather than running anything.
    '''

    def run(*args, **kwargs):
        events.append('run')

        if calls is not None:
            calls.append((args, kwargs))

        return subprocess.CompletedProcess(args, returncode)

    return run


@pytest.fixture
def stub_foreground_process_group(monkeypatch):
    '''
    Replace the functions that look at and change the terminal's foreground process group with
    no-ops, so that tests of opening a shell never touch the real terminal.
    '''
    monkeypatch.setattr(module, 'get_foreground_process_group', lambda: None)
    monkeypatch.setattr(module, 'restore_foreground_process_group', lambda process_group: None)


@pytest.mark.usefixtures('stub_foreground_process_group')
def test_action_open_shell_runs_shell_from_environment(monkeypatch):
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    events, calls = [], []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))
    monkeypatch.setattr(subprocess, 'run', fake_run(events, calls))

    app.action_open_shell()

    assert [args for args, kwargs in calls] == [(('/bin/fancysh',),)]


@pytest.mark.parametrize('shell', (None, ''), ids=('unset', 'empty'))
@pytest.mark.usefixtures('stub_foreground_process_group')
def test_action_open_shell_without_usable_shell_variable_runs_default_shell(monkeypatch, shell):
    if shell is None:
        monkeypatch.delenv('SHELL', raising=False)
    else:
        monkeypatch.setenv('SHELL', shell)

    events, calls = [], []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))
    monkeypatch.setattr(subprocess, 'run', fake_run(events, calls))

    app.action_open_shell()

    assert module.DEFAULT_SHELL == '/bin/sh'
    assert [args for args, kwargs in calls] == [(('/bin/sh',),)]


@pytest.mark.usefixtures('stub_foreground_process_group')
def test_action_open_shell_marks_shell_environment_without_changing_ours(monkeypatch):
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    monkeypatch.setenv('SOME_OTHER_VARIABLE', 'kept')
    monkeypatch.delenv('BORGMATIC_BROWSE_SHELL', raising=False)
    events, calls = [], []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))
    monkeypatch.setattr(subprocess, 'run', fake_run(events, calls))

    app.action_open_shell()

    ((_args, kwargs),) = calls
    assert kwargs['env']['BORGMATIC_BROWSE_SHELL'] == '1'
    assert kwargs['env']['SOME_OTHER_VARIABLE'] == 'kept'
    assert kwargs['env']['SHELL'] == '/bin/fancysh'
    assert 'BORGMATIC_BROWSE_SHELL' not in os.environ


@pytest.mark.usefixtures('stub_foreground_process_group')
def test_action_open_shell_runs_shell_without_checking_exit_status(monkeypatch):
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    events, calls = [], []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))
    flexmock(app).should_receive('notify').never()
    monkeypatch.setattr(subprocess, 'run', fake_run(events, calls, returncode=1))

    app.action_open_shell()

    ((_args, kwargs),) = calls
    assert kwargs['check'] is False


@pytest.mark.usefixtures('stub_foreground_process_group')
def test_action_open_shell_runs_shell_and_prints_hint_inside_suspend(monkeypatch, capsys):
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    events = []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))

    def printing_run(*args, **kwargs):
        events.append(('run', capsys.readouterr().out))

        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, 'run', printing_run)

    app.action_open_shell()

    assert events == [
        'suspend',
        ('run', 'Type "exit" to return to borgmatic-browse.\n'),
        'resume',
    ]


@pytest.mark.usefixtures('stub_foreground_process_group')
def test_action_open_shell_with_error_starting_shell_notifies_literal_error(monkeypatch):
    monkeypatch.setenv('SHELL', '/no/such/[shell]')
    events = []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))
    error = FileNotFoundError(2, 'No such file or directory', '/no/such/[shell]')

    def failing_run(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, 'run', failing_run)
    flexmock(app).should_receive('notify').with_args(
        f'Error opening shell: {error}', severity='error', markup=False
    ).once()

    app.action_open_shell()

    assert events == ['suspend', 'resume']


def test_action_open_shell_with_suspend_not_supported_notifies_warning_and_skips_shell(
    monkeypatch,
):
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    events = []
    app = make_app()

    @contextlib.contextmanager
    def unsupported_suspend():
        raise textual.app.SuspendNotSupported('nope')
        yield

    flexmock(app).should_receive('suspend').replace_with(unsupported_suspend)
    monkeypatch.setattr(subprocess, 'run', fake_run(events))
    flexmock(app).should_receive('notify').with_args(
        'Opening a shell is not supported here', severity='warning'
    ).once()

    app.action_open_shell()

    assert events == []


def test_get_foreground_process_group_returns_foreground_group_of_standard_input(monkeypatch):
    monkeypatch.setattr(module.sys, '__stdin__', flexmock(fileno=lambda: 5))
    flexmock(module.os).should_receive('tcgetpgrp').with_args(5).and_return(1234).once()

    assert module.get_foreground_process_group() == 1234


def test_get_foreground_process_group_without_terminal_returns_none(monkeypatch):
    monkeypatch.setattr(module.sys, '__stdin__', flexmock(fileno=lambda: 5))
    flexmock(module.os).should_receive('tcgetpgrp').and_raise(OSError(25, 'Not a tty'))

    assert module.get_foreground_process_group() is None


def test_restore_foreground_process_group_given_none_does_nothing():
    flexmock(module.os).should_receive('tcgetpgrp').never()
    flexmock(module.os).should_receive('tcsetpgrp').never()
    flexmock(module.signal).should_receive('signal').never()

    module.restore_foreground_process_group(None)


def test_restore_foreground_process_group_already_in_foreground_does_nothing(monkeypatch):
    monkeypatch.setattr(module.sys, '__stdin__', flexmock(fileno=lambda: 5))
    flexmock(module.os).should_receive('tcgetpgrp').with_args(5).and_return(1234)
    flexmock(module.os).should_receive('tcsetpgrp').never()
    flexmock(module.signal).should_receive('signal').never()

    module.restore_foreground_process_group(1234)


def test_restore_foreground_process_group_sets_group_while_ignoring_sigttou(monkeypatch):
    events = []
    previous_handler = object()
    monkeypatch.setattr(module.sys, '__stdin__', flexmock(fileno=lambda: 5))
    flexmock(module.os).should_receive('tcgetpgrp').with_args(5).and_return(999)
    flexmock(module.os).should_receive('tcsetpgrp').replace_with(
        lambda descriptor, group: events.append(('tcsetpgrp', descriptor, group))
    ).once()

    def fake_signal(signal_number, handler):
        events.append(('signal', signal_number, handler))

        return previous_handler

    flexmock(module.signal).should_receive('signal').replace_with(fake_signal)

    module.restore_foreground_process_group(1234)

    assert events == [
        ('signal', module.signal.SIGTTOU, module.signal.SIG_IGN),
        ('tcsetpgrp', 5, 1234),
        ('signal', module.signal.SIGTTOU, previous_handler),
    ]


def test_restore_foreground_process_group_with_error_setting_group_restores_handler(monkeypatch):
    events = []
    previous_handler = object()
    monkeypatch.setattr(module.sys, '__stdin__', flexmock(fileno=lambda: 5))
    flexmock(module.os).should_receive('tcgetpgrp').with_args(5).and_return(999)

    def failing_tcsetpgrp(descriptor, group):
        events.append('tcsetpgrp')

        raise OSError(1, 'Operation not permitted')

    flexmock(module.os).should_receive('tcsetpgrp').replace_with(failing_tcsetpgrp)

    def fake_signal(signal_number, handler):
        events.append(('signal', signal_number, handler))

        return previous_handler

    flexmock(module.signal).should_receive('signal').replace_with(fake_signal)

    module.restore_foreground_process_group(1234)

    assert events == [
        ('signal', module.signal.SIGTTOU, module.signal.SIG_IGN),
        'tcsetpgrp',
        ('signal', module.signal.SIGTTOU, previous_handler),
    ]


def test_restore_foreground_process_group_with_error_getting_group_sets_nothing(monkeypatch):
    monkeypatch.setattr(module.sys, '__stdin__', flexmock(fileno=lambda: 5))
    flexmock(module.os).should_receive('tcgetpgrp').and_raise(OSError(25, 'Not a tty'))
    flexmock(module.os).should_receive('tcsetpgrp').never()
    flexmock(module.signal).should_receive('signal').never()

    module.restore_foreground_process_group(1234)


def test_action_open_shell_restores_foreground_group_after_shell_inside_suspend(monkeypatch):
    monkeypatch.setenv('SHELL', '/bin/fancysh')
    events = []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))
    monkeypatch.setattr(subprocess, 'run', fake_run(events))
    flexmock(module).should_receive('get_foreground_process_group').replace_with(
        lambda: events.append('get-foreground') or 1234
    ).once()
    flexmock(module).should_receive('restore_foreground_process_group').replace_with(
        lambda process_group: events.append(('restore', process_group))
    ).once()

    app.action_open_shell()

    assert events == ['suspend', 'get-foreground', 'run', ('restore', 1234), 'resume']


def test_action_open_shell_with_error_starting_shell_still_restores_foreground_group(monkeypatch):
    monkeypatch.setenv('SHELL', '/no/such/shell')
    events = []
    app = make_app()
    flexmock(app).should_receive('suspend').replace_with(fake_suspend(events))
    flexmock(app).should_receive('notify')

    def failing_run(*args, **kwargs):
        raise FileNotFoundError(2, 'No such file or directory', '/no/such/shell')

    monkeypatch.setattr(subprocess, 'run', failing_run)
    flexmock(module).should_receive('get_foreground_process_group').replace_with(
        lambda: events.append('get-foreground') or 1234
    )
    flexmock(module).should_receive('restore_foreground_process_group').replace_with(
        lambda process_group: events.append(('restore', process_group))
    )

    app.action_open_shell()

    assert events == ['suspend', 'get-foreground', ('restore', 1234), 'resume']
