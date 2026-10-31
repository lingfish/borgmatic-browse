import pytest

from borgmatic_browse import cli as module


def test_parse_arguments_with_no_arguments_uses_defaults():
    arguments = module.parse_arguments()

    assert arguments.config_paths is None
    assert arguments.verbosity is None
    assert arguments.overrides is None


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
