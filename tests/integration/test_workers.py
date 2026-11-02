import pytest
from flexmock import flexmock

from borgmatic_browse import workers as module


def test_archive_path_loaded_publish_records_complete():
    signal = module.Archive_path_loaded(owner=flexmock(), name='Bob')
    signal.publish(module.LOADING_DONE)

    assert signal.complete


def test_archive_path_loaded_publish_records_published_paths():
    archive_path = module.borgmatic_browse.archive.Archive_path('-', 'foo/bar.txt', '', 5)
    signal = module.Archive_path_loaded(owner=flexmock(), name='Bob')
    signal.publish((archive_path,))

    assert signal.path_hierarchy == {'foo': {'bar.txt': archive_path}}
    assert signal.path_hierarchy['foo'].size == 5
    assert not signal.complete


@pytest.mark.parametrize(
    'signal_class', (module.Archive_loaded, module.Archive_path_loaded, module.File_preview_loaded)
)
def test_signal_defaults_to_not_failed(signal_class):
    assert signal_class.failed is False
    assert signal_class(owner=flexmock(), name='Bob').failed is False


@pytest.mark.parametrize(
    'signal_class', (module.Archive_loaded, module.Archive_path_loaded, module.File_preview_loaded)
)
def test_signal_failed_is_independent_per_instance(signal_class):
    signal = signal_class(owner=flexmock(), name='Bob')
    other_signal = signal_class(owner=flexmock(), name='Alice')

    signal.failed = True

    assert other_signal.failed is False
    assert signal_class.failed is False
