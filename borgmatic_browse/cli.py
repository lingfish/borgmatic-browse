import argparse
import logging
import os
import sys

import borgmatic.commands.borgmatic
import borgmatic.config.collect
import borgmatic.logger
import borgmatic.verbosity

import borgmatic_browse.run

logger = logging.getLogger(__name__)

EXIT_CODE_ERROR = 1
MINIMUM_VERBOSITY = -2
MAXIMUM_VERBOSITY = 2
PASSPHRASE_ENVIRONMENT_VARIABLES = ('BORG_PASSPHRASE', 'BORG_PASSCOMMAND', 'BORG_PASSPHRASE_FD')


def parse_arguments(*unparsed_arguments):
    '''
    Given command-line arguments with which this script was invoked, parse the arguments and return
    them as an argparse.Namespace instance.
    '''
    parser = argparse.ArgumentParser(
        prog='borgmatic-browse',
        description='Browse the Borg archives of the repositories in borgmatic configuration files.',
    )
    parser.add_argument(
        '-c',
        '--config',
        dest='config_paths',
        metavar='PATH',
        action='append',
        help='Configuration filename or directory, can specify flag multiple times, defaults to the same paths as borgmatic',
    )
    parser.add_argument(
        '-v',
        '--verbosity',
        type=int,
        choices=range(MINIMUM_VERBOSITY, MAXIMUM_VERBOSITY + 1),
        help='Verbosity of the logs panel: -2 (disabled), -1 (errors), 0 (answers), 1 (some), or 2 (lots), defaults to the "verbosity" configuration option',
    )
    parser.add_argument(
        '-a',
        '--match-archives',
        metavar='PATTERN',
        help='Only list archives with names, hashes, or series matching this pattern, e.g. "*" for all archives, defaults to the "match_archives" configuration option and then to archives matching the "archive_name_format" option',
    )
    parser.add_argument(
        '--override',
        dest='overrides',
        metavar='OPTION.SUBOPTION=VALUE',
        action='append',
        help='Configuration file option to override with specified value, can specify flag multiple times',
    )

    return parser.parse_args(unparsed_arguments)


def prevent_passphrase_prompts(configs):
    '''
    Given a dict from configuration filename to configuration dict, set an empty passphrase on each
    configuration that has no other source for one, so that Borg doesn't prompt for it. A prompt
    would appear underneath the UI and take over the terminal, leaving the app stuck.

    Given a passphrase from anywhere, Borg uses it rather than prompting. So a repository that needs
    a real passphrase instead fails with an error, while a repository with an empty passphrase or no
    encryption keeps working.

    Leave the configurations alone if a passphrase environment variable is set, as setting a
    passphrase in a configuration would override it.
    '''
    if any(variable in os.environ for variable in PASSPHRASE_ENVIRONMENT_VARIABLES):
        return

    for config in configs.values():
        if 'encryption_passphrase' not in config and 'encryption_passcommand' not in config:
            config['encryption_passphrase'] = ''


def main():
    '''
    Load borgmatic configuration according to the command-line arguments and launch the browse UI.
    Log any configuration errors and exit with an error code instead if the configuration can't be
    loaded.

    Set any match archives flag directly on each configuration rather than treating it as an
    override, because overrides get parsed as YAML and a pattern should be taken verbatim.

    Configure logging before launching, because log_to_widget() relies on borgmatic's handlers
    being in place.
    '''
    arguments = parse_arguments(*sys.argv[1:])
    config_filenames = tuple(
        borgmatic.config.collect.collect_config_filenames(
            arguments.config_paths or borgmatic.config.collect.get_default_config_paths()
        )
    )
    configs, _, parse_logs = borgmatic.commands.borgmatic.load_configurations(
        config_filenames, {}, arguments.overrides
    )

    borgmatic.logger.configure_logging(
        borgmatic.verbosity.verbosity_to_log_level(
            arguments.verbosity
            if arguments.verbosity is not None
            else borgmatic.verbosity.get_verbosity(configs, 'verbosity')
        ),
        color_enabled=borgmatic.logger.should_do_markup(configs, json_enabled=False),
    )

    for log_record in parse_logs:
        logger.handle(log_record)

    if any(log_record.levelno >= logging.CRITICAL for log_record in parse_logs):
        sys.exit(EXIT_CODE_ERROR)

    if not configs:
        logger.critical('No borgmatic configuration files found')
        sys.exit(EXIT_CODE_ERROR)

    if arguments.match_archives:
        for config in configs.values():
            config['match_archives'] = arguments.match_archives

    prevent_passphrase_prompts(configs)

    borgmatic_browse.run.run_browse(diff_arguments=None, global_arguments=None, configs=configs)
