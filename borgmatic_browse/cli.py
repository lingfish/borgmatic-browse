import argparse
import logging
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
        '--override',
        dest='overrides',
        metavar='OPTION.SUBOPTION=VALUE',
        action='append',
        help='Configuration file option to override with specified value, can specify flag multiple times',
    )

    return parser.parse_args(unparsed_arguments)


def main():
    '''
    Load borgmatic configuration according to the command-line arguments and launch the browse UI.
    Log any configuration errors and exit with an error code instead if the configuration can't be
    loaded.

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

    borgmatic_browse.run.run_browse(diff_arguments=None, global_arguments=None, configs=configs)
