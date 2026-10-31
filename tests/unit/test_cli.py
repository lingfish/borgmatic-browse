import logging

import pytest
from flexmock import flexmock

from borgmatic_browse import cli as module


def insert_load_mocks(configs=None, parse_logs=(), expected_config_paths=None, overrides=None):
    flexmock(module.borgmatic.config.collect).should_receive('collect_config_filenames').with_args(
        expected_config_paths
    ).and_return(['test.yaml'])
    flexmock(module.borgmatic.commands.borgmatic).should_receive('load_configurations').with_args(
        ('test.yaml',), {}, overrides
    ).and_return(configs if configs is not None else {'test.yaml': {}}, set(), parse_logs)
    flexmock(module.borgmatic.logger).should_receive('should_do_markup').and_return(False)


def test_main_with_arguments_loads_configuration_and_runs_browse():
    configs = {'test.yaml': {'repositories': [{'path': 'test.borg'}]}}
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml', '--override', 'foo.bar=baz'])
    insert_load_mocks(configs, expected_config_paths=['test.yaml'], overrides=['foo.bar=baz'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging').once()
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').with_args(
        diff_arguments=None, global_arguments=None, configs=configs
    ).once()

    module.main()


def test_main_without_config_paths_uses_default_config_paths():
    flexmock(module.sys, argv=['borgmatic-browse'])
    flexmock(module.borgmatic.config.collect).should_receive('get_default_config_paths').and_return(
        ['default.yaml']
    )
    insert_load_mocks(expected_config_paths=['default.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').once()

    module.main()


def test_main_configures_logging_before_running_browse():
    calls = []
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    flexmock(module.borgmatic.config.collect).should_receive('collect_config_filenames').and_return(
        ['test.yaml']
    )
    flexmock(module.borgmatic.commands.borgmatic).should_receive('load_configurations').and_return(
        {'test.yaml': {}}, set(), []
    )
    flexmock(module.borgmatic.logger).should_receive('should_do_markup').and_return(False)
    flexmock(module.borgmatic.logger).should_receive('configure_logging').replace_with(
        lambda *args, **kwargs: calls.append('logging')
    )
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').replace_with(
        lambda **kwargs: calls.append('browse')
    )

    module.main()

    assert calls == ['logging', 'browse']


def test_main_prefers_verbosity_flag_over_configured_verbosity():
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml', '--verbosity', '2'])
    insert_load_mocks({'test.yaml': {'verbosity': -1}}, expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging').with_args(
        logging.DEBUG, color_enabled=False
    ).once()
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').once()

    module.main()


def test_main_without_verbosity_flag_uses_configured_verbosity():
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks({'test.yaml': {'verbosity': 1}}, expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging').with_args(
        logging.INFO, color_enabled=False
    ).once()
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').once()

    module.main()


def test_main_logs_parse_warnings_and_still_runs_browse():
    warning = logging.makeLogRecord(dict(levelno=logging.WARNING, levelname='WARNING', msg='hmm'))
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks(parse_logs=[warning], expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.logger).should_receive('handle').with_args(warning).once()
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').once()

    module.main()


def test_main_with_configuration_error_logs_it_and_exits_with_error_code():
    error = logging.makeLogRecord(dict(levelno=logging.CRITICAL, levelname='CRITICAL', msg='oh no'))
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks(
        {'test.yaml': {}, 'other.yaml': {}},
        parse_logs=[error],
        expected_config_paths=['test.yaml'],
    )
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.logger).should_receive('handle').with_args(error).once()
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').never()

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == module.EXIT_CODE_ERROR


def test_main_without_any_configuration_files_logs_error_and_exits_with_error_code():
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks({}, expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.logger).should_receive('critical').once()
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').never()

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == module.EXIT_CODE_ERROR
