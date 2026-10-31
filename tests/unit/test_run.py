from flexmock import flexmock

import borgmatic_browse.app
from borgmatic_browse import run as module


def test_run_browse_without_configs_bails():
    app = flexmock()
    app.should_receive('run').never()

    flexmock(borgmatic_browse.app).should_receive('Browse_app').and_return(app)

    module.run_browse(
        diff_arguments=flexmock(),
        global_arguments=flexmock(),
        configs=(),
    )


def test_run_browse_with_configs_does_not_raise():
    flexmock(borgmatic_browse.app).should_receive('Browse_app').and_return(
        flexmock(run=lambda: None)
    )

    module.run_browse(
        diff_arguments=flexmock(),
        global_arguments=flexmock(),
        configs=(flexmock(), flexmock()),
    )
