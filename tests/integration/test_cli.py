import os

import borgmatic.borg.environment
import borgmatic.borg.flags
import pytest
from flexmock import flexmock

from borgmatic_browse import cli as module


def test_parse_arguments_with_no_arguments_uses_defaults():
    arguments = module.parse_arguments()

    assert arguments.config_paths is None
    assert arguments.verbosity is None
    assert arguments.overrides is None
    assert arguments.match_archives is None


def test_parse_arguments_with_multiple_config_flags_collects_them():
    arguments = module.parse_arguments('--config', 'one.yaml', '-c', 'two.d')

    assert arguments.config_paths == ['one.yaml', 'two.d']


def test_parse_arguments_with_multiple_override_flags_collects_them():
    arguments = module.parse_arguments('--override', 'foo=1', '--override', 'bar=2')

    assert arguments.overrides == ['foo=1', 'bar=2']


@pytest.mark.parametrize('verbosity', (-2, -1, 0, 1, 2))
def test_parse_arguments_accepts_borgmatic_verbosity_values(verbosity):
    assert module.parse_arguments('--verbosity', str(verbosity)).verbosity == verbosity


def test_parse_arguments_with_out_of_range_verbosity_exits():
    with pytest.raises(SystemExit):
        module.parse_arguments('-v', '3')


@pytest.mark.parametrize('flag', ('-a', '--match-archives'))
def test_parse_arguments_with_match_archives_flag_stores_the_pattern_verbatim(flag):
    assert module.parse_arguments(flag, 'sh:foo-*').match_archives == 'sh:foo-*'


@pytest.mark.parametrize(
    'local_borg_version,pattern,expected_flags',
    (
        ('1.4.5', 'sh:foo-*', ('--glob-archives', 'foo-*')),
        ('2.0.0b25', 'sh:foo-*', ('--match-archives', 'sh:foo-*')),
        ('1.4.5', '*', ()),
        ('2.0.0b25', '*', ()),
    ),
)
def test_main_match_archives_flag_produces_borg_flags_for_each_borg_version(
    local_borg_version, pattern, expected_flags
):
    captured = {}
    flexmock(module.sys, argv=['borgmatic-browse', '-c', 'test.yaml', '-a', pattern])
    flexmock(module.borgmatic.config.collect).should_receive('collect_config_filenames').and_return(
        ['test.yaml']
    )
    flexmock(module.borgmatic.commands.borgmatic).should_receive('load_configurations').and_return(
        {'test.yaml': {'match_archives': 'configured-*'}}, set(), []
    )
    flexmock(module.borgmatic.logger).should_receive('should_do_markup').and_return(False)
    flexmock(module.borgmatic.logger).should_receive('configure_logging')
    flexmock(module.borgmatic_browse.run).should_receive('run_browse').replace_with(
        lambda **kwargs: captured.update(kwargs)
    )

    module.main()

    config = captured['configs']['test.yaml']
    assert (
        borgmatic.borg.flags.make_match_archives_flags(
            config.get('match_archives'), config.get('archive_name_format'), local_borg_version
        )
        == expected_flags
    )


def clear_passphrase_environment(monkeypatch):
    for name in ('BORG_PASSPHRASE', 'BORG_PASSCOMMAND', 'BORG_PASSPHRASE_FD'):
        monkeypatch.delenv(name, raising=False)


def test_prevent_passphrase_prompts_makes_borgmatic_pass_a_passphrase_file_descriptor(monkeypatch):
    clear_passphrase_environment(monkeypatch)
    config = {}
    module.prevent_passphrase_prompts({'test.yaml': config})

    environment = borgmatic.borg.environment.make_environment(config)

    try:
        assert 'BORG_PASSPHRASE_FD' in environment
    finally:
        if 'BORG_PASSPHRASE_FD' in environment:
            os.close(int(environment['BORG_PASSPHRASE_FD']))


def test_prevent_passphrase_prompts_with_passphrase_in_environment_keeps_it_in_borgmatic_environment(
    monkeypatch,
):
    clear_passphrase_environment(monkeypatch)
    monkeypatch.setenv('BORG_PASSPHRASE', 'from-environment')
    config = {}
    module.prevent_passphrase_prompts({'test.yaml': config})

    environment = borgmatic.borg.environment.make_environment(config)

    try:
        assert environment['BORG_PASSPHRASE'] == 'from-environment'
        assert 'BORG_PASSPHRASE_FD' not in environment
    finally:
        if 'BORG_PASSPHRASE_FD' in environment:
            os.close(int(environment['BORG_PASSPHRASE_FD']))
