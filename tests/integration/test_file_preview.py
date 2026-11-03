import contextlib
import re

import pytest
import textual.app
import textual.binding
import textual.widgets.option_list
from flexmock import flexmock

from borgmatic_browse import file_preview as module


def test_file_preview_does_not_raise():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')

    module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo/bar.txt'
    )


async def test_file_preview_on_mount_does_not_raise():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    flexmock(module.borgmatic_browse.workers).should_receive('load_file_preview')
    file_preview = module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo.txt'
    )
    flexmock(file_preview.file_preview_loaded).should_receive('subscribe')

    async with textual.app.App().run_test():
        file_preview.on_mount()


def test_file_preview_on_file_preview_loaded_with_none_file_contents_displays_error():
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(flexmock(stop=lambda: None))
    file_preview = module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo.txt'
    )
    flexmock(file_preview).should_receive('write').with_args(
        'Cannot display a preview for this file'
    ).once()

    file_preview.on_file_preview_loaded(None)


def test_file_preview_on_file_preview_loaded_with_file_contents_displays_contents():
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(flexmock(stop=lambda: None))
    file_preview = module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo.txt'
    )
    flexmock(file_preview).should_receive('write').with_args(
        'Cannot display a preview for this file'
    ).never()
    flexmock(file_preview).should_receive('write').once()

    file_preview.on_file_preview_loaded('hi')


def test_file_preview_on_file_preview_loaded_with_loading_failed_displays_error():
    loading_timer = flexmock()
    loading_timer.should_receive('stop').once()
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(loading_timer)
    file_preview = module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo.txt'
    )
    flexmock(file_preview).should_receive('write').with_args(
        'Cannot display a preview for this file'
    ).never()
    flexmock(file_preview).should_receive('write').with_args(
        'Error loading this file. Press v to view the logs.'
    ).once()

    file_preview.on_file_preview_loaded(module.borgmatic_browse.workers.LOADING_FAILED)


@pytest.mark.parametrize('failed', (True, False))
def test_file_preview_load_failed_reflects_file_preview_loaded_signal(failed):
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    file_preview = module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo.txt'
    )
    file_preview.file_preview_loaded.failed = failed

    assert file_preview.load_failed is failed


def test_file_preview_load_failed_is_read_only():
    flexmock(module.borgmatic_browse.loading).should_receive('add_inline_loading_indicator')
    file_preview = module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo.txt'
    )

    with pytest.raises(AttributeError):
        file_preview.load_failed = True


NOT_LOADED = object()
LONG_LINE = ' '.join(f'word{i}' for i in range(60)) + ' ENDMARK'  # About 450 cells wide.
OVER_CAP_LINE = ' '.join(f'word{i}' for i in range(600)) + ' ENDMARK'  # Over 4000 cells wide.


class Preview_app(textual.app.App):
    def __init__(self, preview):
        super().__init__()
        self.preview = preview

    def compose(self):
        yield self.preview


@contextlib.asynccontextmanager
async def running_preview(contents, size=(120, 30)):
    '''
    Given file contents (or NOT_LOADED) and a terminal size, run a real File_preview in a small app
    without loading anything from Borg, give it the given contents, and yield the app, pilot and
    preview once the contents have been rendered.
    '''
    flexmock(module.borgmatic_browse.loading).should_receive(
        'add_inline_loading_indicator'
    ).and_return(flexmock(stop=lambda: None))
    flexmock(module.borgmatic_browse.workers).should_receive('load_file_preview')
    preview = module.File_preview(
        config=flexmock(), repository=flexmock(), archive_name='archive', file_path='foo.txt'
    )
    app = Preview_app(preview)

    async with app.run_test(size=size) as pilot:
        preview.focus()

        if contents is NOT_LOADED:
            preview.write('Still loading')
        else:
            preview.on_file_preview_loaded(contents)

        await pilot.pause()

        yield app, pilot, preview


def rendered_text(preview):
    return '\n'.join(strip.text for strip in preview.lines)


def rendered_words(preview):
    return rendered_text(preview).split()


def notification_messages(app):
    return [notification.message for notification in app._notifications]


# Issue #12: long lines are cut off, with no horizontal scrollbar.


@pytest.mark.parametrize('width', (120, 60))
async def test_file_preview_renders_line_wider_than_panel_in_full(width):
    async with running_preview(LONG_LINE, size=(width, 30)) as (_app, _pilot, preview):
        assert 'word0' in rendered_words(preview)
        assert 'ENDMARK' in rendered_words(preview)


@pytest.mark.parametrize('width', (120, 60))
async def test_file_preview_scrolls_horizontally_for_line_wider_than_panel(width):
    async with running_preview(LONG_LINE, size=(width, 30)) as (_app, pilot, preview):
        assert 'ENDMARK' in rendered_words(preview)
        assert preview.max_scroll_x > 0

        preview.scroll_to(x=100000, animate=False)
        await pilot.pause()

        assert preview.scroll_x > 0


async def test_file_preview_caps_width_of_line_wider_than_maximum():
    async with running_preview(OVER_CAP_LINE) as (_app, _pilot, preview):
        assert 'word0' in rendered_words(preview)
        assert preview.virtual_size.width == module.MAXIMUM_PREVIEW_WIDTH


async def test_file_preview_notifies_once_when_a_line_is_cut_off():
    async with running_preview(OVER_CAP_LINE) as (app, _pilot, preview):
        assert 'word0' in rendered_words(preview)

        messages = notification_messages(app)

        assert len(messages) == 1
        assert 'cut off' in messages[0]
        assert re.search(r'\bw\b', messages[0])


async def test_file_preview_does_not_notify_when_no_line_exceeds_the_maximum():
    async with running_preview(LONG_LINE + '\nshort line') as (app, _pilot, preview):
        assert 'ENDMARK' in rendered_words(preview)
        assert notification_messages(app) == []


async def test_file_preview_renders_wide_characters_in_full():
    contents = '界' * 70 + ' WIDEEND'  # 148 cells, but only 78 characters.

    async with running_preview(contents) as (_app, _pilot, preview):
        assert 'WIDEEND' in rendered_words(preview)
        assert preview.max_scroll_x > 0


async def test_file_preview_renders_tab_expanded_lines_in_full():
    contents = 'x\t' * 40 + 'TABEND'  # 160 cells with tabs expanded, but only 86 characters.

    async with running_preview(contents) as (_app, _pilot, preview):
        assert 'TABEND' in rendered_words(preview)
        assert preview.max_scroll_x > 0


@pytest.mark.parametrize('width', (120, 60))
async def test_file_preview_does_not_scroll_horizontally_when_lines_fit_the_panel(width):
    async with running_preview('short one\nshort two', size=(width, 30)) as (_app, _pilot, preview):
        assert 'two' in rendered_words(preview)
        assert preview.max_scroll_x == 0


async def test_file_preview_with_empty_contents_does_not_raise():
    async with running_preview(''):
        pass
