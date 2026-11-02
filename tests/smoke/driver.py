import dataclasses
import fcntl
import os
import pty
import re
import select
import signal
import struct
import termios
import time

import pyte

SCREEN_COLUMNS = 120
SCREEN_LINES = 40
EXIT_WAIT_SECONDS = 12
EXIT_WAIT_AFTER_FAILURE_SECONDS = 3
SECONDS_BEFORE_KEY = 0.3


@dataclasses.dataclass
class Result:
    '''
    The outcome of running a command in a pseudo-terminal.

      * code: The exit status, the negative signal number if killed by a signal, or None if the
        command was still running when the driver gave up on it and killed it.
      * failed: A description of the wait that timed out, or None if every wait succeeded.
      * shots: The screen as a string at the moment each wait succeeded, before sending its keys.
      * final: The screen as a string once finished.
      * tail: All output after the last step, with terminal escape sequences removed.
      * terminal_restored: Whether the command left the alternate screen on its way out.
    '''

    code: int | None
    failed: str | None
    shots: list
    final: str
    tail: str
    terminal_restored: bool

    @property
    def crashed(self):
        '''
        Return whether the output contains a Python traceback.
        '''
        return bool(re.search(r'Traceback|WorkerFailed', f'{self.tail}{self.final}'))


def get_screen_text(screen):
    '''
    Given a pyte.Screen, return its non-blank lines as a string.
    '''
    return '\n'.join(line.rstrip() for line in screen.display if line.strip())


def run(command, steps=(), timeout=25, environment=None):
    '''
    Given a command as a sequence of arguments, a sequence of steps, a timeout in seconds for each
    step, and an optional environment dict, run the command in a pseudo-terminal and return a Result.

    Each step is a tuple of a regular expression to wait for on the screen and then the keys to send,
    which may be empty. The keys may instead be a callable that returns them, for changing something
    at that point in the run. Stop at the first wait that times out. Then wait for the command to exit, and
    kill it if it doesn't.
    '''
    process_id, descriptor = pty.fork()

    if process_id == 0:  # pragma: no cover
        os.execvpe(command[0], command, environment or os.environ)  # noqa: S606

    fcntl.ioctl(
        descriptor, termios.TIOCSWINSZ, struct.pack('HHHH', SCREEN_LINES, SCREEN_COLUMNS, 0, 0)
    )
    screen = pyte.Screen(SCREEN_COLUMNS, SCREEN_LINES)
    stream = pyte.ByteStream(screen)
    output = bytearray()
    alive = True

    def read_output(wait_seconds):
        '''
        Read any available output into the screen, and return False if the output has ended.
        '''
        ready, _, _ = select.select([descriptor], [], [], wait_seconds)

        if not ready:
            return True

        try:
            data = os.read(descriptor, 65536)
        except OSError:
            return False

        output.extend(data)
        stream.feed(data)

        return bool(data)

    failed = None
    shots = []

    for wait_pattern, keys in steps:
        end_time = time.monotonic() + timeout

        while (
            alive
            and time.monotonic() < end_time
            and not re.search(wait_pattern, '\n'.join(screen.display))
        ):
            alive = read_output(0.1)

        if not re.search(wait_pattern, '\n'.join(screen.display)):
            failed = f'Timed out waiting for {wait_pattern!r}'
            break

        shots.append(get_screen_text(screen))

        keys_to_send = keys() if callable(keys) else keys

        if keys_to_send and alive:
            time.sleep(SECONDS_BEFORE_KEY)
            os.write(descriptor, keys_to_send.encode())

    tail_start = len(output)
    end_time = time.monotonic() + (EXIT_WAIT_AFTER_FAILURE_SECONDS if failed else EXIT_WAIT_SECONDS)
    status = None

    while time.monotonic() < end_time:
        if alive:
            alive = read_output(0.1)
        else:
            time.sleep(0.05)

        waited_id, waited_status = os.waitpid(process_id, os.WNOHANG)

        if waited_id:
            status = waited_status
            break

    if status is None:
        os.kill(process_id, signal.SIGKILL)
        os.waitpid(process_id, 0)
        code = None
    else:
        code = os.waitstatus_to_exitcode(status)

    os.close(descriptor)

    return Result(
        code=code,
        failed=failed,
        shots=shots,
        final=get_screen_text(screen),
        tail=re.sub(rb'\x1b\[[0-9;?<>=]*[A-Za-z]', b'', bytes(output[tail_start:])).decode(
            'utf-8', 'replace'
        ),
        terminal_restored=b'\x1b[?1049l' in output,
    )


def get_listed_lines(screen_text):
    '''
    Given a screen as a string, return the lines listing an option, with any panel border removed.
    '''
    return tuple(
        line.strip(' │').rstrip()
        for line in screen_text.splitlines()
        if line.startswith('│') and line.strip(' │')
    )
