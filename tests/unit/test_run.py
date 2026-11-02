import pytest
from flexmock import flexmock

import borgmatic_browse.app
from borgmatic_browse import run as module


def test_run_browse_without_configs_bails_with_success_status():
    flexmock(borgmatic_browse.app).should_receive('Browse_app').never()

    assert (
        module.run_browse(
            diff_arguments=flexmock(),
            global_arguments=flexmock(),
            configs=(),
        )
        == 0
    )


def test_run_browse_with_configs_does_not_raise():
    flexmock(borgmatic_browse.app).should_receive('Browse_app').and_return(
        flexmock(run=lambda: None, return_code=0)
    )

    module.run_browse(
        diff_arguments=flexmock(),
        global_arguments=flexmock(),
        configs=(flexmock(), flexmock()),
    )


@pytest.mark.parametrize('return_code', (0, 1, 2))
def test_run_browse_returns_the_apps_return_code(return_code):
    flexmock(borgmatic_browse.app).should_receive('Browse_app').and_return(
        flexmock(run=lambda: None, return_code=return_code)
    )

    assert (
        module.run_browse(
            diff_arguments=flexmock(),
            global_arguments=flexmock(),
            configs=(flexmock(), flexmock()),
        )
        == return_code
    )


def test_run_browse_with_no_app_return_code_returns_success_status():
    flexmock(borgmatic_browse.app).should_receive('Browse_app').and_return(
        flexmock(run=lambda: None, return_code=None)
    )

    assert (
        module.run_browse(
            diff_arguments=flexmock(),
            global_arguments=flexmock(),
            configs=(flexmock(), flexmock()),
        )
        == 0
    )
