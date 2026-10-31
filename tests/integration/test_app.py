from flexmock import flexmock

import borgmatic_browse.app
import borgmatic_browse.configuration_files_list
import borgmatic_browse.logs
import borgmatic_browse.repositories_list


async def test_browse_app_with_multiple_configs_uses_configuration_files_list():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
            'test2.yaml': {'repositories': [{'path': 'test2.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test():
        app.query_one(selector='Header')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1
        assert isinstance(
            carousel.panels[0],
            borgmatic_browse.configuration_files_list.Configuration_files_list,
        )
        assert carousel.panels[0].configs == app.configs

        app.query_one(selector='Logs')
        app.query_one(selector='Footer')


async def test_browse_app_with_one_config_uses_repositories_list():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test():
        app.query_one(selector='Header')

        carousel = app.query_one(selector='Carousel')
        assert len(carousel.panels) == 1
        assert isinstance(carousel.panels[0], borgmatic_browse.repositories_list.Repositories_list)
        assert carousel.panels[0].config == app.configs['test1.yaml']

        app.query_one(selector='Logs')
        app.query_one(selector='Footer')


async def test_browse_app_quit_key_terminates_child_processes_and_exits():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')
    flexmock(borgmatic_browse.app).should_receive('terminate_child_processes').once()

    async with app.run_test() as pilot:
        await pilot.press('q')
        await pilot.pause()

    assert app.return_code == 0


async def test_browse_app_key_toggles_logs_panel():
    app = borgmatic_browse.app.Browse_app(
        configs={
            'test1.yaml': {'repositories': [{'path': 'test1.borg'}]},
        }
    )
    flexmock(borgmatic_browse.logs).should_receive('log_to_widget')

    async with app.run_test() as pilot:
        logs_panel = app.query_one('#logs')

        await pilot.press('v')
        await pilot.pause()
        assert logs_panel.styles.display == 'block'
