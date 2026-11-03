import subprocess

import pytest
import textual.widgets._header
import textual.widgets.option_list
from flexmock import flexmock

import borgmatic_browse.app
import borgmatic_browse.archive
import borgmatic_browse.carousel
import borgmatic_browse.loading
import borgmatic_browse.logs
import borgmatic_browse.workers
from borgmatic_browse import carousel as module

# The separator between the parts of a location, written as an escape to keep ruff's ambiguous
# character check quiet.
SEP = ' \u203a '


def test_make_next_panel_with_configuration_files_list_returns_repositories_list():
    configs = {'test.yaml': {'repositories': [{'path': 'test.borg'}]}}

    repositories_list = module.make_next_panel(
        focused_panel=borgmatic_browse.configuration_files_list.Configuration_files_list(configs),
        option_id='test.yaml',
    )

    assert isinstance(repositories_list, borgmatic_browse.repositories_list.Repositories_list)
    assert repositories_list.config == configs['test.yaml']


def test_make_next_panel_with_repositories_list_returns_archives_list():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')
    flexmock(borgmatic_browse.archives_list.Archives_list).should_receive('app').and_return(
        flexmock()
    )

    archives_list = module.make_next_panel(
        focused_panel=borgmatic_browse.repositories_list.Repositories_list(config),
        option_id=0,
    )

    assert isinstance(archives_list, borgmatic_browse.archives_list.Archives_list)
    assert archives_list.config == config
    assert archives_list.repository == config['repositories'][0]


def test_make_next_panel_with_archives_list_returns_directory_list():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.archives_list.Archives_list).should_receive('app').and_return(
        flexmock()
    )
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )

    archives_list = borgmatic_browse.archives_list.Archives_list(config, config['repositories'][0])
    archives_list.archive_names['abc123'] = 'archive'

    directory_list = module.make_next_panel(focused_panel=archives_list, option_id='abc123')

    assert isinstance(directory_list, borgmatic_browse.directory_list.Directory_list)
    assert directory_list.config == config
    assert directory_list.repository == config['repositories'][0]
    assert directory_list.archive_name == 'abc123'
    assert directory_list.archive_label == 'archive'


def test_make_next_panel_with_root_directory_list_and_selected_directory_option_returns_new_directory_list():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.workers).should_receive('Archive_path_loaded').replace_with(
        flexmock(
            path_hierarchy={
                'etc': borgmatic_browse.workers.Directory(),
            },
            complete=False,
        ),
    )
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config, config['repositories'][0], 'archive'
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type='d'))

    directory_list = module.make_next_panel(focused_panel=focused_panel, option_id='etc')

    assert isinstance(directory_list, borgmatic_browse.directory_list.Directory_list)
    assert directory_list.config == config
    assert directory_list.repository == config['repositories'][0]
    assert directory_list.archive_name == 'archive'
    assert directory_list.path_components == ('etc',)


def test_make_next_panel_with_non_root_directory_list_and_selected_directory_option_returns_new_directory_list():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.workers).should_receive('Archive_path_loaded').replace_with(
        flexmock(
            path_hierarchy={
                'etc': borgmatic_browse.workers.Directory(
                    {
                        'borgmatic': borgmatic_browse.workers.Directory(),
                    },
                ),
            },
            complete=False,
        ),
    )
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config,
        config['repositories'][0],
        'archive',
        path_components=('etc',),
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type='d'))

    directory_list = module.make_next_panel(focused_panel=focused_panel, option_id='borgmatic')

    assert isinstance(directory_list, borgmatic_browse.directory_list.Directory_list)
    assert directory_list.config == config
    assert directory_list.repository == config['repositories'][0]
    assert directory_list.archive_name == 'archive'
    assert directory_list.path_components == ('etc', 'borgmatic')


def test_make_next_panel_with_root_directory_list_and_selected_file_option_returns_new_file_preview():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.workers).should_receive('load_file_preview')
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    flexmock(borgmatic_browse.file_preview.File_preview).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config, config['repositories'][0], 'archive'
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type='-'))

    directory_list = module.make_next_panel(focused_panel=focused_panel, option_id='config.yaml')

    assert isinstance(directory_list, borgmatic_browse.file_preview.File_preview)
    assert directory_list.config == config
    assert directory_list.repository == config['repositories'][0]
    assert directory_list.archive_name == 'archive'
    assert directory_list.file_path == 'config.yaml'


def test_make_next_panel_with_non_root_directory_list_and_selected_file_option_returns_new_file_preview():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.workers).should_receive('load_file_preview')
    flexmock(borgmatic_browse.workers).should_receive('Archive_path_loaded').replace_with(
        flexmock(
            path_hierarchy={
                'etc': borgmatic_browse.workers.Directory(
                    {
                        'borgmatic': borgmatic_browse.workers.Directory(
                            {
                                'config.yaml': borgmatic_browse.archive.Archive_path(
                                    '-', 'config.yaml', ''
                                ),
                            },
                        ),
                    },
                ),
            },
            complete=False,
        ),
    )
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    flexmock(borgmatic_browse.file_preview.File_preview).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config,
        config['repositories'][0],
        'archive',
        path_components=('etc', 'borgmatic'),
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type='-'))

    directory_list = module.make_next_panel(focused_panel=focused_panel, option_id='config.yaml')

    assert isinstance(directory_list, borgmatic_browse.file_preview.File_preview)
    assert directory_list.config == config
    assert directory_list.repository == config['repositories'][0]
    assert directory_list.archive_name == 'archive'
    assert directory_list.file_path == 'etc/borgmatic/config.yaml'


def test_make_next_panel_with_unsupported_focused_panel_returns_none():
    assert module.make_next_panel(focused_panel=flexmock(), option_id='hmmm') is None


@pytest.mark.parametrize('path_type', ('l', 'p', 'wtf', None))
def test_make_next_panel_with_directory_list_and_unsupported_selected_option_returns_none(
    path_type,
):
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config, config['repositories'][0], 'archive'
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type=path_type))

    assert module.make_next_panel(focused_panel=focused_panel, option_id='config.yaml') is None


async def test_carousel_previous_action_with_multiple_configs_does_not_raise():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('left')


async def test_carousel_previous_action_with_one_config_does_not_raise():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('left')


async def test_carousel_next_action_with_multiple_configs_advances_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('enter')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 2

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'none'

        assert isinstance(carousel.panels[1], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[1].styles.display == 'block'
        assert carousel.panels[1].highlighted == 0
        assert app.focused == carousel.panels[1]


async def test_carousel_next_action_with_one_config_advances_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')

    async with app.run_test() as pilot:
        await pilot.press('enter')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 2

        assert isinstance(carousel.panels[0], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[0].styles.display == 'none'

        assert isinstance(carousel.panels[1], borgmatic_browse.archives_list.Archives_list)
        assert carousel.panels[1].styles.display == 'block'
        assert carousel.panels[1].highlighted == 0
        assert app.focused == carousel.panels[1]


async def test_carousel_next_action_with_no_next_panel_does_not_advance():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')
    flexmock(module).should_receive('make_next_panel')

    async with app.run_test() as pilot:
        await pilot.press('enter')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1

        assert isinstance(carousel.panels[0], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[0].styles.display == 'block'
        assert app.focused == carousel.panels[0]


async def test_carousel_next_action_and_previous_action_returns_to_original_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await pilot.press('left')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 2

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'block'
        assert carousel.panels[0].highlighted == 0

        assert isinstance(carousel.panels[1], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[1].styles.display == 'none'
        assert app.focused == carousel.panels[0]


async def test_carousel_next_action_and_previous_action_and_next_action_reuses_next_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.carousel).should_call('make_next_panel').once()

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await pilot.press('left')
        await pilot.press('enter')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 2

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'none'

        assert isinstance(carousel.panels[1], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[1].styles.display == 'block'
        assert carousel.panels[1].highlighted == 0
        assert app.focused == carousel.panels[1]


async def test_carousel_next_action_with_multiple_configs_and_no_next_panel_does_not_advance():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(module).should_receive('make_next_panel').and_return(None)

    async with app.run_test() as pilot:
        await pilot.press('enter')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'block'
        assert carousel.panels[0].highlighted == 0
        assert app.focused == carousel.panels[0]


async def test_carousel_next_action_and_previous_action_and_down_truncates_next_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await pilot.press('left')
        await pilot.press('down')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'block'
        assert carousel.panels[0].highlighted == 1
        assert app.focused == carousel.panels[0]


async def test_carousel_down_does_not_raise():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('down')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'block'
        assert carousel.panels[0].highlighted == 1
        assert app.focused == carousel.panels[0]


async def test_carousel_up_does_not_raise():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('down')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'block'
        assert carousel.panels[0].highlighted == 1
        assert app.focused == carousel.panels[0]


async def test_carousel_next_action_and_select_dot_dot_returns_to_original_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        await pilot.press('enter')

        carousel = app.query_one(selector='Carousel')
        carousel.panels[1].options[0] = textual.widgets.option_list.Option('..', id='..')

        await pilot.press('enter')

        assert len(carousel.panels) == 2

        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].styles.display == 'block'
        assert carousel.panels[0].highlighted == 0

        assert isinstance(carousel.panels[1], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[1].styles.display == 'none'
        assert app.focused == carousel.panels[0]


def make_directory_list(path_components=None):
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    return borgmatic_browse.directory_list.Directory_list(
        {'repositories': [{'path': 'test.borg', 'label': 'mine'}]},
        {'path': 'test.borg', 'label': 'mine'},
        'abc123',
        path_components=path_components,
        archive_label='nightly',
    )


@pytest.mark.parametrize(
    'panel_class,argument',
    (
        (
            borgmatic_browse.configuration_files_list.Configuration_files_list,
            {'test.yaml': {'repositories': [{'path': 'test.borg'}]}},
        ),
        (
            borgmatic_browse.repositories_list.Repositories_list,
            {'repositories': [{'path': 'test.borg'}]},
        ),
    ),
)
def test_get_panel_location_with_configuration_files_or_repositories_list_returns_empty(
    panel_class, argument
):
    assert module.get_panel_location(panel_class(argument)) == ''


@pytest.mark.parametrize(
    'repository,expected_location',
    (
        ({'path': 'test.borg', 'label': 'mine'}, 'mine'),
        ({'path': 'test.borg'}, 'test.borg'),
    ),
)
def test_get_panel_location_with_archives_list_returns_repository_label_or_path(
    repository, expected_location
):
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    archives_list = borgmatic_browse.archives_list.Archives_list(
        {'repositories': [repository]}, repository
    )

    assert module.get_panel_location(archives_list) == expected_location


def test_get_panel_location_with_root_directory_list_returns_repository_and_archive_label():
    assert module.get_panel_location(make_directory_list()) == SEP.join(('mine', 'nightly'))


def test_get_panel_location_with_non_root_directory_list_returns_repository_archive_and_path():
    directory_list = make_directory_list(path_components=('foo', 'bar'))

    assert module.get_panel_location(directory_list) == SEP.join(('mine', 'nightly', 'foo/bar'))


def test_get_panel_location_with_file_preview_returns_repository_archive_and_file_path():
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    file_preview = borgmatic_browse.file_preview.File_preview(
        {'repositories': [{'path': 'test.borg', 'label': 'mine'}]},
        {'path': 'test.borg', 'label': 'mine'},
        'abc123',
        file_path='foo/bar.txt',
        archive_label='nightly',
    )

    assert module.get_panel_location(file_preview) == SEP.join(('mine', 'nightly', 'foo/bar.txt'))


def test_get_panel_location_with_file_preview_without_archive_label_uses_archive_name():
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    file_preview = borgmatic_browse.file_preview.File_preview(
        {'repositories': [{'path': 'test.borg'}]},
        {'path': 'test.borg'},
        'archive',
        file_path='foo.txt',
    )

    assert file_preview.archive_label == 'archive'
    assert module.get_panel_location(file_preview) == SEP.join(('test.borg', 'archive', 'foo.txt'))


def test_make_next_panel_with_directory_list_carries_archive_label_to_new_directory_list():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config, config['repositories'][0], 'abc123', archive_label='nightly'
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type='d'))

    directory_list = module.make_next_panel(focused_panel=focused_panel, option_id='etc')

    assert directory_list.archive_name == 'abc123'
    assert directory_list.archive_label == 'nightly'


def test_make_next_panel_with_directory_list_carries_archive_label_to_new_file_preview():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.workers).should_receive('load_file_preview')
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    flexmock(borgmatic_browse.file_preview.File_preview).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config, config['repositories'][0], 'abc123', archive_label='nightly'
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type='-'))

    file_preview = module.make_next_panel(focused_panel=focused_panel, option_id='config.yaml')

    assert file_preview.archive_name == 'abc123'
    assert file_preview.archive_label == 'nightly'


async def test_carousel_sub_title_starts_empty():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg', 'label': 'mine'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test():
        assert app.sub_title == ''


async def test_carousel_next_action_sets_sub_title_to_new_panel_location():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg', 'label': 'mine'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')

    async with app.run_test() as pilot:
        await pilot.press('enter')

        assert app.sub_title == 'mine'


async def test_carousel_previous_action_sets_sub_title_to_previous_panel_location():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg', 'label': 'mine'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')

    async with app.run_test() as pilot:
        await pilot.press('enter')
        assert app.sub_title == 'mine'

        await pilot.press('left')

        assert app.sub_title == ''


async def test_carousel_previous_action_at_first_panel_leaves_sub_title_unchanged():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg', 'label': 'mine'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        app.sub_title = 'sentinel'
        await pilot.press('left')

        assert app.sub_title == 'sentinel'


async def test_carousel_next_action_with_no_next_panel_leaves_sub_title_unchanged():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg', 'label': 'mine'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(module).should_receive('make_next_panel').and_return(None)

    async with app.run_test() as pilot:
        app.sub_title = 'sentinel'
        await pilot.press('enter')

        assert app.sub_title == 'sentinel'


async def test_carousel_next_action_reusing_existing_panel_sets_sub_title():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg', 'label': 'mine'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await pilot.press('left')
        await pilot.press('enter')

        assert app.sub_title == 'mine'


async def test_header_with_markup_like_archive_name_in_sub_title_shows_it_literally():
    app = borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg', 'label': 'mine'}]}}
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        app.sub_title = SEP.join(('mine', 'bad[/name]', 'foo'))
        await pilot.pause()

        header_title = app.query_one(textual.widgets._header.HeaderTitle)

        assert app._exception is None
        assert SEP.join(('mine', 'bad[/name]', 'foo')) in str(header_title.visual)


def make_focused_directory_list(**kwargs):
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.workers).should_receive('Archive_path_loaded').replace_with(
        flexmock(path_hierarchy={'etc': borgmatic_browse.workers.Directory()}, complete=False),
    )
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    focused_panel = borgmatic_browse.directory_list.Directory_list(
        config, config['repositories'][0], 'archive', **kwargs
    )
    flexmock(focused_panel).should_receive('get_option').and_return(flexmock(path_type='d'))

    return focused_panel


@pytest.mark.parametrize(
    'sort_mode,sort_reversed',
    (('size', False), ('size', True), ('time', False), ('name', True)),
)
def test_make_next_panel_with_directory_list_passes_sort_to_child_directory_list(
    sort_mode, sort_reversed
):
    focused_panel = make_focused_directory_list(sort_mode=sort_mode, sort_reversed=sort_reversed)

    directory_list = module.make_next_panel(focused_panel=focused_panel, option_id='etc')

    assert directory_list.sort_mode == sort_mode
    assert directory_list.sort_reversed is sort_reversed


def test_make_next_panel_with_directory_list_passes_changed_sort_to_child_directory_list():
    focused_panel = make_focused_directory_list()
    focused_panel.set_sort_mode('size')
    focused_panel.action_reverse_sort()

    directory_list = module.make_next_panel(focused_panel=focused_panel, option_id='etc')

    assert directory_list.sort_mode == 'size'
    assert directory_list.sort_reversed is False
    assert directory_list.border_subtitle == 'sort: size ↑'


def test_make_next_panel_with_archives_list_starts_directory_list_at_default_sort():
    config = {'repositories': [{'path': 'test.borg'}]}
    flexmock(borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(borgmatic_browse.workers).should_receive('add_repository_archives')
    flexmock(borgmatic_browse.workers).should_receive('load_archive_paths')
    flexmock(borgmatic_browse.archives_list.Archives_list).should_receive('app').and_return(
        flexmock()
    )
    flexmock(borgmatic_browse.directory_list.Directory_list).should_receive('app').and_return(
        flexmock()
    )
    archives_list = borgmatic_browse.archives_list.Archives_list(
        config=config, repository=config['repositories'][0]
    )
    archives_list.archive_names['abc123'] = 'archive'
    archives_list.set_sort_mode('name')
    archives_list.action_reverse_sort()

    directory_list = module.make_next_panel(focused_panel=archives_list, option_id='abc123')

    assert directory_list.sort_mode == 'name'
    assert directory_list.sort_reversed is False
    assert directory_list.border_subtitle == 'sort: name ↑'


BORG_ERROR = subprocess.CalledProcessError(13, 'borg', output='Repository /x does not exist.')
ARCHIVES = (
    borgmatic_browse.archive.Archive('id1', 'name1', '2026-10-31 17:40'),
    borgmatic_browse.archive.Archive('id2', 'name2', '2026-10-31 18:50'),
)


def make_retry_app():
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    return borgmatic_browse.app.Browse_app(
        configs={'test1.yaml': {'repositories': [{'path': 'test1.borg'}]}}
    )


async def wait_for_loading(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()


def option_ids(panel):
    return {option.id for option in panel.options}


def rendered_lines(panel):
    return '\n'.join(strip.text for strip in panel.lines)


async def test_carousel_next_action_after_failed_archives_load_runs_borg_again():
    app = make_retry_app()
    calls = []

    def get_repository_archives(config, repository):
        calls.append(1)

        if len(calls) == 1:
            raise BORG_ERROR

        return (ARCHIVES[0],)

    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').replace_with(
        get_repository_archives
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        failed_panel = app.focused

        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        carousel = app.query_one(selector='Carousel')
        assert len(calls) == 2
        assert isinstance(app.focused, borgmatic_browse.archives_list.Archives_list)
        assert app.focused is not failed_panel
        assert 'id1' in option_ids(app.focused)
        assert 'loading-indicator' not in option_ids(app.focused)
        assert len(carousel.panels) == 2
        assert carousel.panels[1] is app.focused
        assert len(app.query('Archives_list')) == 1
        assert app._exception is None


async def test_carousel_next_action_after_failed_archives_load_removes_failed_panel_from_dom():
    app = make_retry_app()
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_raise(
        BORG_ERROR
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        failed_panel = app.focused

        await pilot.press('left')
        await pilot.press('enter')
        await pilot.pause()

        assert not failed_panel.is_attached
        assert app.focused is not failed_panel


async def test_carousel_next_action_after_successful_archives_load_does_not_run_borg_again():
    app = make_retry_app()
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (ARCHIVES[0],)
    ).once()

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        first_panel = app.focused

        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        assert app.focused is first_panel
        assert len(app.query_one(selector='Carousel').panels) == 2
        assert app._exception is None


async def test_carousel_next_action_after_failed_archive_listing_runs_borg_again_with_fresh_paths():
    app = make_retry_app()
    calls = []

    def get_archive_paths(config, repository, archive_name):
        calls.append(archive_name)

        if len(calls) == 1:
            yield borgmatic_browse.archive.Archive_path('-', 'stale.txt', '', 1)
            raise BORG_ERROR

        yield borgmatic_browse.archive.Archive_path('-', 'fresh.txt', '', 2)

    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        ARCHIVES
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').replace_with(
        get_archive_paths
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        await pilot.press('down')  # Archives load newest first, so id1 is the second option.
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        failed_panel = app.focused
        assert isinstance(failed_panel, borgmatic_browse.directory_list.Directory_list)
        assert 'stale.txt' in option_ids(failed_panel)

        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        carousel = app.query_one(selector='Carousel')
        assert calls == ['id1', 'id1']
        assert isinstance(app.focused, borgmatic_browse.directory_list.Directory_list)
        assert app.focused is not failed_panel
        assert 'fresh.txt' in option_ids(app.focused)
        assert 'stale.txt' not in option_ids(app.focused)
        assert 'loading-indicator' not in option_ids(app.focused)
        assert 'stale.txt' not in app.focused.path_loaded.path_hierarchy
        assert len(carousel.panels) == 3
        assert len(app.query('Directory_list')) == 1
        assert app._exception is None


async def test_carousel_next_action_after_failed_file_preview_runs_borg_again():
    app = make_retry_app()
    calls = []

    def get_archive_file_content(config, repository, archive_name, file_path):
        calls.append(file_path)

        if len(calls) == 1:
            raise BORG_ERROR

        return 'second run contents'

    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (ARCHIVES[0],)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').and_yield(
        borgmatic_browse.archive.Archive_path('-', 'notes.txt', '', 3)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_file_content').replace_with(
        get_archive_file_content
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        failed_panel = app.focused
        assert isinstance(failed_panel, borgmatic_browse.file_preview.File_preview)
        assert 'Error loading' in rendered_lines(failed_panel)

        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        carousel = app.query_one(selector='Carousel')
        assert calls == ['notes.txt', 'notes.txt']
        assert isinstance(app.focused, borgmatic_browse.file_preview.File_preview)
        assert app.focused is not failed_panel
        assert 'second run contents' in rendered_lines(app.focused)
        assert 'Error loading' not in rendered_lines(app.focused)
        assert len(carousel.panels) == 4
        assert len(app.query('File_preview')) == 1
        assert app._exception is None


async def test_carousel_next_action_after_successful_file_preview_does_not_run_borg_again():
    app = make_retry_app()
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (ARCHIVES[0],)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').and_yield(
        borgmatic_browse.archive.Archive_path('-', 'notes.txt', '', 3)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_file_content').and_return(
        'contents'
    ).once()

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        first_panel = app.focused

        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        assert app.focused is first_panel
        assert app._exception is None


async def test_carousel_next_action_after_repeated_archives_load_failure_keeps_app_running():
    app = make_retry_app()
    calls = []

    def get_repository_archives(config, repository):
        calls.append(1)
        raise BORG_ERROR

    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').replace_with(
        get_repository_archives
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        carousel = app.query_one(selector='Carousel')
        assert len(calls) == 2
        assert app.is_running
        assert app._exception is None
        assert isinstance(app.focused, borgmatic_browse.archives_list.Archives_list)
        assert 'loading-indicator' not in option_ids(app.focused)
        assert len(carousel.panels) == 2
        assert len(app.query('Archives_list')) == 1

        # A third attempt still works, and still only leaves one archives list.
        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        assert len(calls) == 3
        assert len(app.query('Archives_list')) == 1
        assert app._exception is None


async def test_carousel_next_action_removes_failed_next_panel_and_every_panel_after_it():
    app = make_retry_app()
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (ARCHIVES[0],)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').and_yield(
        borgmatic_browse.archive.Archive_path('-', 'notes.txt', '', 3)
    )

    async with app.run_test() as pilot:
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        archives_list = app.focused
        await pilot.press('enter')
        await wait_for_loading(app, pilot)
        directory_list = app.focused

        # Pretend that the archives list failed, with its directory list still hanging off it.
        carousel = app.query_one(selector='Carousel')
        archives_list.archive_loaded.failed = True
        await pilot.press('left')
        await pilot.press('left')
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

        assert app.focused is not archives_list
        assert not archives_list.is_attached
        assert not directory_list.is_attached
        assert directory_list not in carousel.panels
        assert len(carousel.panels) == 2
        assert app._exception is None


LONG_FILE_CONTENTS = 'START ' + 'word ' * 100 + 'END'


def make_long_file_app():
    app = make_retry_app()
    flexmock(borgmatic_browse.archive).should_receive('get_repository_archives').and_return(
        (ARCHIVES[0],)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_paths').and_yield(
        borgmatic_browse.archive.Archive_path('-', 'long.txt', '', 3)
    )
    flexmock(borgmatic_browse.archive).should_receive('get_archive_file_content').and_return(
        LONG_FILE_CONTENTS
    )

    return app


async def open_long_file_preview(app, pilot):
    '''
    Given an app and its pilot, select through to the long file's preview, and return the carousel
    and the preview once it has rendered.
    '''
    for _ in range(3):
        await pilot.press('enter')
        await wait_for_loading(app, pilot)

    preview = app.focused
    assert isinstance(preview, borgmatic_browse.file_preview.File_preview)
    assert 'START' in rendered_lines(preview)
    assert preview.max_scroll_x > 0

    return app.query_one(selector='Carousel'), preview


@pytest.mark.parametrize('key', ('left', 'h'))
async def test_carousel_previous_key_with_file_preview_scrolled_right_scrolls_it_left(key):
    app = make_long_file_app()

    async with app.run_test() as pilot:
        carousel, preview = await open_long_file_preview(app, pilot)
        preview.scroll_to(x=24, animate=False)
        await pilot.pause()
        scrolled_x = preview.scroll_x
        assert scrolled_x > 0

        await pilot.press(key)
        await pilot.wait_for_animation()
        await pilot.pause()

        assert carousel.focused_panel is preview
        assert app.focused is preview
        assert 0 <= preview.scroll_x < scrolled_x
        assert app._exception is None


@pytest.mark.parametrize('key', ('left', 'h'))
async def test_carousel_previous_key_after_scrolling_right_with_key_returns_to_start_of_preview(
    key,
):
    app = make_long_file_app()

    async with app.run_test() as pilot:
        carousel, preview = await open_long_file_preview(app, pilot)

        await pilot.press('right')
        await pilot.wait_for_animation()
        await pilot.pause()
        assert preview.scroll_x > 0

        await pilot.press(key)
        await pilot.wait_for_animation()
        await pilot.pause()

        assert preview.scroll_x == 0
        assert carousel.focused_panel is preview
        assert app.focused is preview


@pytest.mark.parametrize('key', ('left', 'h'))
async def test_carousel_previous_key_with_file_preview_at_left_edge_goes_to_previous_panel(key):
    app = make_long_file_app()

    async with app.run_test() as pilot:
        carousel, preview = await open_long_file_preview(app, pilot)
        assert preview.scroll_x == 0

        await pilot.press(key)
        await pilot.pause()

        assert carousel.focused_panel is not preview
        assert carousel.focused_panel is carousel.panels[-2]
        assert isinstance(app.focused, borgmatic_browse.directory_list.Directory_list)
        assert preview.styles.display == 'none'


async def test_carousel_previous_key_after_scrolling_back_to_left_edge_goes_to_previous_panel():
    app = make_long_file_app()

    async with app.run_test() as pilot:
        carousel, preview = await open_long_file_preview(app, pilot)
        preview.scroll_to(x=1, animate=False)
        await pilot.pause()
        assert preview.scroll_x == 1

        await pilot.press('left')
        await pilot.wait_for_animation()
        await pilot.pause()
        assert preview.scroll_x == 0
        assert carousel.focused_panel is preview

        await pilot.press('left')
        await pilot.pause()

        assert carousel.focused_panel is not preview
        assert isinstance(app.focused, borgmatic_browse.directory_list.Directory_list)


@pytest.mark.parametrize('key', ('left', 'h'))
async def test_carousel_previous_key_with_directory_list_goes_to_previous_panel(key):
    app = make_long_file_app()

    async with app.run_test() as pilot:
        for _ in range(2):
            await pilot.press('enter')
            await wait_for_loading(app, pilot)

        carousel = app.query_one(selector='Carousel')
        directory_list = app.focused
        assert isinstance(directory_list, borgmatic_browse.directory_list.Directory_list)

        await pilot.press(key)
        await pilot.pause()

        assert carousel.focused_panel is not directory_list
        assert isinstance(app.focused, borgmatic_browse.archives_list.Archives_list)
        assert app._exception is None
