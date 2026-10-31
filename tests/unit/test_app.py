from flexmock import flexmock

from borgmatic_browse import app as module


def test_terminate_child_processes_terminates_each_child():
    children = (flexmock(), flexmock())
    flexmock(module.psutil).should_receive('Process').and_return(
        flexmock(children=lambda recursive: children)
    )

    for child in children:
        child.should_receive('terminate').once()

    module.terminate_child_processes()


def test_terminate_child_processes_ignores_child_that_already_exited():
    exited_child = flexmock()
    exited_child.should_receive('terminate').and_raise(module.psutil.NoSuchProcess(pid=1))
    running_child = flexmock()
    running_child.should_receive('terminate').once()
    flexmock(module.psutil).should_receive('Process').and_return(
        flexmock(children=lambda recursive: (exited_child, running_child))
    )

    module.terminate_child_processes()
