import logging

import pytest
from flexmock import flexmock

from borgmatic_browse import cli as module

PASSPHRASE_ENVIRONMENT_VARIABLES = ('BORG_PASSPHRASE', 'BORG_PASSCOMMAND', 'BORG_PASSPHRASE_FD')


@pytest.fixture(autouse=True)
def passphrase_in_environment(monkeypatch):
    '''
    Set a Borg passphrase in the environment so that main() leaves configurations alone, keeping
    tests that compare whole configurations independent of the passphrase default. Tests of that
    default clear the environment variables themselves.
    '''
    for name in PASSPHRASE_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv('BORG_PASSPHRASE', 'from-environment')


def clear_passphrase_environment(monkeypatch):
    '''
    Given a monkeypatch fixture, remove all the Borg passphrase environment variables.
    '''
    for name in PASSPHRASE_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


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


def test_main_with_match_archives_flag_sets_it_on_the_configuration():
    configs = {'test.yaml': {'repositories': [{'path': 'test.borg'}]}}
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml', '--match-archives', '*'])
    insert_load_mocks(configs, expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').with_args(
        diff_arguments=None,
        global_arguments=None,
        configs={'test.yaml': {'repositories': [{'path': 'test.borg'}], 'match_archives': '*'}},
    ).once()

    module.main()


def test_main_with_match_archives_flag_overrides_configured_value():
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml', '-a', 'sh:foo-*'])
    insert_load_mocks(
        {'test.yaml': {'match_archives': 'bar-*'}}, expected_config_paths=['test.yaml']
    )
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').with_args(
        diff_arguments=None,
        global_arguments=None,
        configs={'test.yaml': {'match_archives': 'sh:foo-*'}},
    ).once()

    module.main()


def test_main_with_match_archives_flag_sets_it_on_every_configuration():
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml', '-a', '*'])
    insert_load_mocks(
        {'test.yaml': {}, 'other.yaml': {'match_archives': 'bar-*'}},
        expected_config_paths=['test.yaml'],
    )
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').with_args(
        diff_arguments=None,
        global_arguments=None,
        configs={'test.yaml': {'match_archives': '*'}, 'other.yaml': {'match_archives': '*'}},
    ).once()

    module.main()


def test_main_with_match_archives_flag_passes_only_overrides_to_load_configurations():
    flexmock(
        module.sys,
        argv=['borgmatic-browse', '-c', 'test.yaml', '-a', 'sh:foo-*', '--override', 'foo=1'],
    )
    insert_load_mocks(expected_config_paths=['test.yaml'], overrides=['foo=1'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').once()

    module.main()


def test_main_without_match_archives_flag_leaves_configurations_untouched():
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks(
        {'test.yaml': {}, 'other.yaml': {'match_archives': 'bar-*'}},
        expected_config_paths=['test.yaml'],
    )
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').with_args(
        diff_arguments=None,
        global_arguments=None,
        configs={'test.yaml': {}, 'other.yaml': {'match_archives': 'bar-*'}},
    ).once()

    module.main()


def test_prevent_passphrase_prompts_sets_empty_passphrase_without_any_passphrase_source(
    monkeypatch,
):
    clear_passphrase_environment(monkeypatch)
    configs = {'test.yaml': {'repositories': [{'path': 'test.borg'}]}}

    module.prevent_passphrase_prompts(configs)

    assert configs == {
        'test.yaml': {'repositories': [{'path': 'test.borg'}], 'encryption_passphrase': ''}
    }


def test_prevent_passphrase_prompts_keeps_configured_passphrase(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    configs = {'test.yaml': {'encryption_passphrase': 'secret'}}

    module.prevent_passphrase_prompts(configs)

    assert configs == {'test.yaml': {'encryption_passphrase': 'secret'}}


def test_prevent_passphrase_prompts_keeps_configured_empty_passphrase(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    configs = {'test.yaml': {'encryption_passphrase': ''}}

    module.prevent_passphrase_prompts(configs)

    assert configs == {'test.yaml': {'encryption_passphrase': ''}}


def test_prevent_passphrase_prompts_leaves_configuration_with_passcommand_alone(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    configs = {'test.yaml': {'encryption_passcommand': 'pass borg'}}

    module.prevent_passphrase_prompts(configs)

    assert configs == {'test.yaml': {'encryption_passcommand': 'pass borg'}}


def test_prevent_passphrase_prompts_handles_each_configuration_separately(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    configs = {
        'one.yaml': {},
        'two.yaml': {'encryption_passphrase': 'secret'},
        'three.yaml': {'encryption_passcommand': 'pass borg'},
        'four.yaml': {'encryption_passphrase': ''},
    }

    module.prevent_passphrase_prompts(configs)

    assert configs == {
        'one.yaml': {'encryption_passphrase': ''},
        'two.yaml': {'encryption_passphrase': 'secret'},
        'three.yaml': {'encryption_passcommand': 'pass borg'},
        'four.yaml': {'encryption_passphrase': ''},
    }


def test_prevent_passphrase_prompts_with_no_configurations_does_nothing(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    configs = {}

    module.prevent_passphrase_prompts(configs)

    assert configs == {}


@pytest.mark.parametrize('name', PASSPHRASE_ENVIRONMENT_VARIABLES)
@pytest.mark.parametrize('value', ('something', ''))
def test_prevent_passphrase_prompts_with_passphrase_in_environment_leaves_configurations_alone(
    monkeypatch, name, value
):
    clear_passphrase_environment(monkeypatch)
    monkeypatch.setenv(name, value)
    configs = {'test.yaml': {}, 'other.yaml': {'encryption_passphrase': 'secret'}}

    module.prevent_passphrase_prompts(configs)

    assert configs == {'test.yaml': {}, 'other.yaml': {'encryption_passphrase': 'secret'}}


def test_main_prevents_passphrase_prompts_before_running_browse(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks(
        {'test.yaml': {}, 'other.yaml': {'encryption_passphrase': 'secret'}},
        expected_config_paths=['test.yaml'],
    )
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').with_args(
        diff_arguments=None,
        global_arguments=None,
        configs={
            'test.yaml': {'encryption_passphrase': ''},
            'other.yaml': {'encryption_passphrase': 'secret'},
        },
    ).once()

    module.main()


def test_main_with_configuration_error_exits_without_preventing_passphrase_prompts(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    error = logging.makeLogRecord(dict(levelno=logging.CRITICAL, levelname='CRITICAL', msg='oh no'))
    configs = {'test.yaml': {}}
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks(configs, parse_logs=[error], expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.logger).should_receive('handle')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').never()

    with pytest.raises(SystemExit):
        module.main()

    assert configs == {'test.yaml': {}}


def test_main_without_any_configuration_files_exits_without_preventing_passphrase_prompts(
    monkeypatch,
):
    clear_passphrase_environment(monkeypatch)
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml'])
    insert_load_mocks({}, expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.logger).should_receive('critical')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').never()
    flexmock(module).should_receive('prevent_passphrase_prompts').never()

    with pytest.raises(SystemExit):
        module.main()


def test_main_with_match_archives_flag_and_configuration_error_exits_without_running_browse():
    error = logging.makeLogRecord(dict(levelno=logging.CRITICAL, levelname='CRITICAL', msg='oh no'))
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml', '-a', '*'])
    insert_load_mocks(parse_logs=[error], expected_config_paths=['test.yaml'])
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.logger).should_receive('handle').with_args(error).once()
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').never()

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == module.EXIT_CODE_ERROR
