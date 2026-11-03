'''
Check the app's main behaviours against real Borg 1 and Borg 2, using fixtures from make_fixtures.sh.
Each check prints whether it passed, and the script exits with an error if any failed.

This isn't part of the pytest suite, because it's slow and needs Borg installed.
'''

import os
import pathlib
import socket
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import driver

LOADED = r'^(?![\s\S]*loading)[\s\S]*sort: '


def main():
    '''
    Given a fixtures directory on the command line, run each check and report the results.
    '''
    fixtures = pathlib.Path(sys.argv[1]).resolve()
    app = str(pathlib.Path(sys.executable).parent / 'borgmatic-browse')
    host = socket.gethostname()
    failures = 0

    def check(name, config, steps, wanted, *flags, base='base1', code=0, user_shell=None):
        '''
        Given a check's name, a configuration name, steps for the driver, a string that the last
        screen must contain, any flags for the app, the name of a Borg base directory, the expected
        exit status, and an optional shell for the app to open, run the app and report whether the check passed.
        '''
        nonlocal failures
        environment = {
            **os.environ,
            'BORG_BASE_DIR': str(fixtures / base),
            **({'SHELL': user_shell} if user_shell else {}),
        }
        result = driver.run(
            [app, '-c', str(fixtures / 'configs' / f'{config}.yaml'), *flags],
            steps,
            timeout=20,
            environment=environment,
        )
        screen = result.shots[-1] if result.shots else result.final
        passed = (
            result.failed is None
            and not result.crashed
            and result.code == code
            and result.terminal_restored
            and wanted in screen
        )
        failures += not passed
        print(f'{"ok  " if passed else "FAIL"} {name}')

        if not passed:
            print(f'     code={result.code} failed={result.failed} crashed={result.crashed}')
            print(f'     restored={result.terminal_restored} wanted={wanted!r}')
            print('\n'.join(f'     {line}' for line in driver.get_listed_lines(screen)))

    def tree_steps(label):
        '''
        Given a repository label, return steps for reaching the "tree" directory's contents in the
        latest archive.
        '''
        return [(label, '\r'), (r'\(latest\)', '\r'), ('📁 tree', '\r'), (r'hello\.py', '')]

    def long_file_steps(file_index):
        '''
        Given the index in the "tree" directory listing of a file, return steps for opening that
        file's preview in the latest of all archives with Borg 1. Each step moves the highlight with
        "j" until the file is reached, and the last one selects it.
        '''
        return [
            ('borg1all', '\r'),
            (r'\(latest\)', 'j'),
            (f'{host}-1', '\r'),
            ('📁 tree', '\r'),
            (r'hello\.py', 'j' * file_index + '\r'),
        ]

    check(
        'Borg 1: default filter hides other archives',
        'borg1',
        [('borg1', '\r'), (LOADED, 'q')],
        f'{host}-implicit',
    )
    check(
        'Borg 1: -a lists a matching archive',
        'borg1',
        [('borg1', '\r'), (LOADED, 'q')],
        'other-1',
        '-a',
        'other-*',
    )
    check(
        'Borg 1: a directory shows its time',
        'borg1-all',
        [
            ('borg1all', '\r'),
            (r'\(latest\)', 'j'),
            (f'{host}-1', '\r'),
            ('📁 tree', '\r'),
            (r'hello\.py', 'q'),
        ],
        '2025-05-05 05:05  📁 zdir',
    )
    check(
        'Borg 1: a symlink shows its target',
        'borg1-all',
        [
            ('borg1all', '\r'),
            (r'\(latest\)', 'j'),
            (f'{host}-1', '\r'),
            ('📁 tree', '\r'),
            (r'hello\.py', 'q'),
        ],
        '🔗 lnk → hello.py',
    )
    check(
        'Borg 1: a parent without an entry shows the label',
        'borg1',
        [('borg1', '\r'), (r'implicit.*\(latest\)', '\r'), ('📁 implicit', 'q')],
        '<no dir entry>    📁 implicit',
    )
    check(
        'Borg 1: sorting by size shows on the border',
        'borg1-all',
        [
            ('borg1all', '\r'),
            (r'\(latest\)', 'j'),
            (f'{host}-1', '\r'),
            ('📁 tree', '\r'),
            (r'hello\.py', 's'),
            ('sort: size', 'q'),
        ],
        'sort: size ↓',
    )
    check(
        'Borg 1: a long line scrolls right to its end',
        'borg1-all',
        [
            *long_file_steps(8),
            # Page scrolling starts from the current position, so keys sent together collapse into
            # one. Send each as its own step, relying on the driver's pause before each key to let
            # the scroll animation settle.
            ('LONGSTART', '\x1b[6;5~'),
            *[('word', '\x1b[6;5~')] * 5,
            ('LONGEND', 'q'),
        ],
        'LONGEND',
    )
    check(
        'Borg 1: w wraps a long line',
        'borg1-all',
        [*long_file_steps(8), ('LONGSTART', 'w'), ('LONGEND', 'q')],
        'LONGEND',
    )
    check(
        'Borg 1: a line over the maximum width says it was cut off',
        'borg1-all',
        [*long_file_steps(6), ('cut off', 'q')],
        'Press w',
    )
    check(
        'Borg 1: wrapping a line over the maximum width shows its end',
        'borg1-all',
        [*long_file_steps(6), ('HUGESTART', 'w\x1b[F'), ('HUGEEND', 'q')],
        'HUGEEND',
    )
    check(
        'Borg 1: left scrolls a preview back rather than leaving it',
        'borg1-all',
        [
            *long_file_steps(8),
            ('LONGSTART', '\x1b[C'),
            (r'│ONGSTART', '\x1b[D'),
            (r'│LONGSTART', 'q'),
        ],
        'long.txt preview',
    )
    check(
        'Borg 1: left at the start of a preview goes to the directory listing',
        'borg1-all',
        [
            *long_file_steps(8),
            ('LONGSTART', '\x1b[D'),
            (r'hello\.py.*\n[\s\S]*long\.txt', 'q'),
        ],
        'hello.py',
    )

    check(
        'Borg 2: identically named archives both list',
        'borg2',
        [('borg2', '\r'), (LOADED, 'q')],
        'dup (latest)',
        base='base2',
    )
    check(
        'Borg 2: the latest archive previews its own contents',
        'borg2',
        [
            *tree_steps('borg2'),
            (r'hello\.py', 'j'),
            (r'hello\.py', 'j'),
            (r'hello\.py', 'j'),
            (r'hello\.py', 'j'),
            (r'hello\.py', 'j'),
            (r'hello\.py', '\r'),
            ('more', 'q'),
        ],
        'more',
        base='base2',
    )
    check(
        'A missing repository shows an error',
        'missing-repo',
        [('missingrepo', '\r'), ('does not exist', 'q')],
        'does not exist',
    )
    check(
        'A missing passphrase shows an error instead of prompting',
        'no-passphrase',
        [('nopass', '\r'), ('none is configured', 'q')],
        'none is configured',
    )
    check(
        'A wrong passphrase shows an error',
        'wrong-passphrase',
        [('wrongpass', '\r'), ('Error listing', 'q')],
        'Error listing',
    )
    check(
        'A missing Borg shows an error',
        'no-borg',
        [('noborg', '\r'), ('Error listing', 'q')],
        'Error listing',
    )
    check(
        'A failed archive listing shows an error',
        'fail-list',
        [('fail-list', '\r'), (r'\(latest\)', '\r'), ('simulated', 'q')],
        'simulated',
    )
    check(
        'Quitting during a slow load exits cleanly',
        'slow',
        [('slow', '\r'), ('loading', 'q')],
        'loading',
    )

    check(
        'An error containing something like markup displays literally',
        'markup-path',
        [('markuppath', '\r'), ('does not exist', 'q')],
        'x[$var].borg',
    )
    check(
        'A pattern matching nothing says so',
        'borg1',
        [('borg1', '\r'), ('No archives match', 's'), ('sort: name', 'q')],
        '''No archives match "nothing-[/x]". Use -a '*' to list them all.''',
        '-a',
        'nothing-[/x]',
    )
    check(
        'The default filter matching nothing says so',
        'empty-repo',
        [('emptyrepo', '\r'), ('No archives match', 'q')],
        'configured archive name format',
    )
    check(
        'A repository with no archives says so',
        'empty-repo',
        [('emptyrepo', '\r'), ('no archives', 'q')],
        'This repository has no archives.',
        '-a',
        '*',
    )

    # The screen keeps the UI's text while in a shell, because pyte ignores the switch away from the
    # alternate screen. So wait for arithmetic in the shell's output, which can't match what's typed,
    # and for the shell's output to get painted over on returning.
    for shell in ('/bin/bash', '/bin/dash'):
        check(
            f'A shell opens with its marker and returns to the same panel: {shell}',
            'borg1',
            [
                ('borg1', 'b'),
                ('Type "exit"', 'echo MARKER${BORGMATIC_BROWSE_SHELL}$((40 + 2))\r'),
                ('MARKER142', 'exit\r'),
                (r'^(?![\s\S]*MARKER142)[\s\S]*borg1', '\r'),
                (r'\(latest\)', 'q'),
            ],
            f'{host}-implicit',
            user_shell=shell,
        )
        check(
            f'Ctrl-C in a shell spares the app and a running load: {shell}',
            'pause',
            [
                ('pause', '\r'),
                ('loading', 'b'),
                ('Type "exit"', 'sleep 30\r'),
                ('Type "exit"', '\x03'),
                ('Type "exit"', 'sleep 5; echo DONE$((1 + 1))\r'),
                ('DONE2', 'exit\r'),
                (r'\(latest\)', 'q'),
            ],
            '(latest)',
            user_shell=shell,
        )

    check(
        'A killed shell returns to the app rather than leaving it stopped',
        'borg1',
        [
            ('borg1', 'b'),
            ('Type "exit"', 'echo KILLING$((1 + 1)); kill -9 $$\r'),
            ('KILLING2', ''),
            (r'^(?![\s\S]*KILLING2)[\s\S]*borg1', '\r'),
            (r'\(latest\)', 'q'),
        ],
        '(latest)',
        user_shell='/bin/bash',
    )
    check(
        'A shell that cannot start shows an error and leaves the app working',
        'borg1',
        [('borg1', 'b'), ('Error opening shell', '\r'), (r'\(latest\)', 'q')],
        '(latest)',
        user_shell='/no/such/[shell]',
    )

    def pipe_steps(config_label, file_index, command):
        '''
        Given a repository label for a configuration listing all archives with Borg 1, the index of a
        file in the "tree/adir" directory listing, and a command, return steps for piping that file
        to the command from the directory listing.
        '''
        return [
            (config_label, '\r'),
            (r'\(latest\)', 'j'),
            (f'{host}-1', '\r'),
            ('📁 tree', '\r'),
            (r'hello\.py', 'j\r'),
            (r'small\.bin', 'j' * file_index + '|'),
            ('to:', f'{command}\r'),
        ]

    # The output window covers the listing, so wait for each command's output there, and then check
    # that closing it leads back to the listing.
    check(
        'Piping a file to jq shows its output and exit status',
        'borg1-all',
        [
            *pipe_steps('borg1all', 1, 'jq -C .name'),
            (r'"smoke"[\s\S]*exit status 0', '\x1b'),
            (r'small\.bin', 'q'),
        ],
        'data.json',
    )
    check(
        'Piping a file streams all of it, past the preview limit',
        'borg1-all',
        [
            *pipe_steps('borg1all', 2, 'wc -c'),
            (r'3488895[\s\S]*exit status 0', '\x1b'),
            (r'small\.bin', 'q'),
        ],
        'lines.txt',
    )
    check(
        'A command that stops reading early is not an error',
        'borg1-all',
        [
            *pipe_steps('borg1all', 2, 'head -n 2'),
            (r'line 2[\s\S]*exit status 0', ''),
            (r'^(?![\s\S]*Error piping)[\s\S]*exit status 0', '\x1b'),
            (r'small\.bin', 'q'),
        ],
        'lines.txt',
    )
    check(
        'Too much output is cut off and the command stopped',
        'borg1-all',
        [
            *pipe_steps('borg1all', 2, 'yes'),
            ('the command was stopped', '\x1b'),
            (r'small\.bin', 'q'),
        ],
        'lines.txt',
    )
    check(
        'A command that does not exist shows the shell error',
        'borg1-all',
        [
            *pipe_steps('borg1all', 1, 'no-such-command'),
            (r'not found[\s\S]*exit status 127', '\x1b'),
            (r'small\.bin', 'q'),
        ],
        'data.json',
    )
    check(
        'Closing a running command returns to the listing without an error',
        'borg1-all',
        [
            *pipe_steps('borg1all', 2, 'sleep 30'),
            ('loading', '\x1b'),
            (r'^(?![\s\S]*sleep 30)[\s\S]*small\.bin', ''),
            (r'^(?![\s\S]*Error piping)[\s\S]*small\.bin', 'q'),
        ],
        'lines.txt',
    )
    check(
        'The prompt remembers the last command',
        'borg1-all',
        [
            *pipe_steps('borg1all', 2, 'wc -l'),
            (r'300000[\s\S]*exit status 0', '\x1b'),
            (r'^(?![\s\S]*300000)[\s\S]*small\.bin', '|'),
            ('wc -l', '\r'),
            (r'300000[\s\S]*exit status 0', '\x1b'),
            (r'^(?![\s\S]*300000)[\s\S]*small\.bin', 'q'),
        ],
        'lines.txt',
    )
    check(
        'A directory cannot be piped',
        'borg1-all',
        [*pipe_steps('borg1all', 0, '')[:-2], (r'small\.bin', '|'), ('Only files', 'q')],
        'Only files can be piped',
    )
    check(
        'A file preview can be piped',
        'borg1-all',
        [
            *long_file_steps(5),
            ('hello smoke', '|'),
            ('to:', 'tr a-z A-Z\r'),
            (r'HELLO SMOKE[\s\S]*exit status 0', '\x1b'),
            (r'^(?![\s\S]*HELLO SMOKE)[\s\S]*hello smoke', 'q'),
        ],
        'hello.py preview',
    )
    check(
        'A binary file can be piped',
        'borg1-all',
        [
            *long_file_steps(4),
            ('Cannot display', '|'),
            ('to:', 'wc -c\r'),
            (r'2000[\s\S]*exit status 0', '\x1b'),
            ('Cannot display', 'q'),
        ],
        'blob.bin preview',
    )
    check(
        'Borg 2: a file can be piped',
        'borg2',
        [
            ('borg2', '\r'),
            (r'\(latest\)', '\r'),
            ('📁 tree', '\r'),
            (r'hello\.py', 'jjjjj|'),
            ('to:', 'tail -n 1\r'),
            (r'more[\s\S]*exit status 0', '\x1b'),
            (r'small|hello\.py', 'q'),
        ],
        'hello.py',
        base='base2',
    )
    check(
        'Borg failing while piping shows an error',
        'fail-extract',
        [
            *pipe_steps('fail-extract', 1, 'cat'),
            (r'simulated extract failure[\s\S]*view the logs', '\x1b'),
            (r'small\.bin', 'q'),
        ],
        'data.json',
    )

    crash_code = (
        'import sys\n'
        'import borgmatic_browse.archive, borgmatic_browse.cli\n'
        'def crash(*args, **kwargs):\n'
        '    raise RuntimeError("simulated crash")\n'
        'borgmatic_browse.archive.get_repository_archives = crash\n'
        f'sys.argv = ["borgmatic-browse", "-c", "{fixtures / "configs" / "borg1.yaml"}"]\n'
        'sys.exit(borgmatic_browse.cli.main())\n'
    )
    crash_result = driver.run(
        [sys.executable, '-c', crash_code],
        [('borg1', '\r')],
        timeout=20,
        environment={**os.environ, 'BORG_BASE_DIR': str(fixtures / 'base1')},
    )
    crash_passed = (
        crash_result.code == 1 and crash_result.crashed and crash_result.terminal_restored
    )
    failures += not crash_passed
    print(f'{"ok  " if crash_passed else "FAIL"} A crash exits with an error status')

    if not crash_passed:
        print(f'     code={crash_result.code} crashed={crash_result.crashed}')

    late_repository = fixtures / 'late.borg'
    stashed_repository = fixtures / 'late.stash'

    def restore_repository():
        '''
        Move the stashed repository into place, like plugging in a disk, and return the key to go
        back.
        '''
        stashed_repository.rename(late_repository)

        return 'h'

    try:
        check(
            'Selecting again after a missing repository appears retries',
            'late-repo',
            [
                ('laterepo', '\r'),
                ('does not exist', restore_repository),
                (r'📦 repositories', '\r'),
                (r'late.*\(latest\)', 'q'),
            ],
            f'{host}-late',
        )
    finally:
        late_repository.rename(stashed_repository)

    log_path = fixtures / 'log-borg.log'
    log_path.unlink(missing_ok=True)
    check(
        'Selecting again after a successful load reuses it',
        'log',
        [
            ('logrepo', '\r'),
            (r'\(latest\)', 'h'),
            (r'📦 repositories', '\r'),
            (r'\(latest\)', 'q'),
        ],
        '(latest)',
    )
    run_count = len(log_path.read_text().splitlines())

    if run_count != 1:
        failures += 1
        print(f'FAIL Borg ran {run_count} times rather than once when reusing a panel')

    print(f'{failures} failed')

    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
