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

    def check(name, config, steps, wanted, *flags, base='base1', code=0):
        '''
        Given a check's name, a configuration name, steps for the driver, a string that the last
        screen must contain, any flags for the app, the name of a Borg base directory, and the
        expected exit status, run the app and report whether the check passed.
        '''
        nonlocal failures
        environment = {**os.environ, 'BORG_BASE_DIR': str(fixtures / base)}
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

    print(f'{failures} failed')

    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
