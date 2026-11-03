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


# Issue #10: toggling word wrap.


def test_file_preview_has_visible_wrap_binding():
    bindings = [
        binding
        for binding in module.File_preview.BINDINGS
        if isinstance(binding, textual.binding.Binding) and binding.key == 'w'
    ]

    assert len(bindings) == 1
    assert bindings[0].action == 'toggle_wrap'
    assert bindings[0].description == 'wrap'
    assert bindings[0].show is True


@pytest.mark.parametrize('width', (120, 60))
async def test_file_preview_wrap_key_wraps_contents_to_fit_panel(width):
    async with running_preview(LONG_LINE + '\nsecond', size=(width, 30)) as (_app, pilot, preview):
        line_count = len(preview.lines)
        assert 'word0' in rendered_words(preview)

        await pilot.press('w')
        await pilot.pause()

        assert 'word0' in rendered_words(preview)
        assert 'word59' in rendered_words(preview)
        assert 'ENDMARK' in rendered_words(preview)
        assert 'second' in rendered_words(preview)
        assert len(preview.lines) > line_count
        assert preview.virtual_size.width <= preview.scrollable_content_region.width
        assert preview.max_scroll_x == 0


@pytest.mark.parametrize('width', (120, 60))
async def test_file_preview_wrap_key_twice_restores_unwrapped_rendering(width):
    async with running_preview(LONG_LINE + '\nsecond', size=(width, 30)) as (_app, pilot, preview):
        line_count = len(preview.lines)
        virtual_width = preview.virtual_size.width
        assert 'word0' in rendered_words(preview)

        await pilot.press('w')
        await pilot.pause()
        assert len(preview.lines) > line_count

        await pilot.press('w')
        await pilot.pause()

        assert 'ENDMARK' in rendered_words(preview)
        assert len(preview.lines) == line_count
        assert preview.virtual_size.width == virtual_width
        assert preview.max_scroll_x > 0


async def test_file_preview_toggling_wrap_does_not_duplicate_contents():
    async with running_preview(LONG_LINE) as (_app, pilot, preview):
        assert rendered_words(preview).count('word0') == 1

        for _ in range(3):
            await pilot.press('w')
            await pilot.pause()

            assert rendered_words(preview).count('word0') == 1


@pytest.mark.parametrize('start_width,new_width', ((120, 60), (60, 120)))
async def test_file_preview_with_wrap_on_rewraps_when_terminal_is_resized(start_width, new_width):
    async with running_preview(LONG_LINE, size=(start_width, 30)) as (_app, pilot, preview):
        await pilot.press('w')
        await pilot.pause()
        assert 'word0' in rendered_words(preview)
        old_line_count = len(preview.lines)

        await pilot.resize_terminal(new_width, 30)
        await pilot.pause()

        assert 'word0' in rendered_words(preview)
        assert 'ENDMARK' in rendered_words(preview)
        assert rendered_words(preview).count('word0') == 1
        assert preview.virtual_size.width <= preview.scrollable_content_region.width
        assert preview.max_scroll_x == 0
        assert (len(preview.lines) < old_line_count) == (new_width > start_width)


async def test_file_preview_does_not_notify_again_on_toggle_or_resize():
    async with running_preview(OVER_CAP_LINE) as (app, pilot, _preview):
        assert len(notification_messages(app)) == 1

        await pilot.press('w')
        await pilot.pause()
        await pilot.resize_terminal(60, 30)
        await pilot.pause()
        await pilot.press('w')
        await pilot.pause()
        await pilot.resize_terminal(100, 30)
        await pilot.pause()

        assert len(notification_messages(app)) == 1


async def test_file_preview_with_wrap_on_does_not_cut_off_lines_over_the_maximum():
    async with running_preview(OVER_CAP_LINE) as (_app, pilot, preview):
        assert 'word0' in rendered_words(preview)
        assert 'ENDMARK' not in rendered_words(preview)

        await pilot.press('w')
        await pilot.pause()

        assert 'word0' in rendered_words(preview)
        assert 'ENDMARK' in rendered_words(preview)


@pytest.mark.parametrize('toggles', (1, 2))
async def test_file_preview_toggling_wrap_keeps_approximate_scroll_position(toggles):
    contents = '\n'.join(f'row{i:03d} {LONG_LINE}' for i in range(150))

    async with running_preview(contents) as (_app, pilot, preview):
        assert 'row000' in rendered_words(preview)
        assert preview.max_scroll_y > 0

        preview.scroll_to(y=preview.max_scroll_y // 2, animate=False)
        await pilot.pause()
        before = preview.scroll_y / preview.max_scroll_y
        assert before > 0.4

        for _ in range(toggles):
            await pilot.press('w')
            await pilot.pause()

        assert preview.max_scroll_y > 0
        assert preview.scroll_y / preview.max_scroll_y == pytest.approx(before, abs=0.1)


async def test_file_preview_toggling_wrap_at_top_stays_at_top():
    contents = '\n'.join(f'row{i:03d} {LONG_LINE}' for i in range(150))

    async with running_preview(contents) as (_app, pilot, preview):
        assert 'row000' in rendered_words(preview)

        await pilot.press('w')
        await pilot.pause()

        assert preview.scroll_y == 0
        assert 'row000' in rendered_words(preview)


@pytest.mark.parametrize(
    'contents',
    (
        NOT_LOADED,
        module.borgmatic_browse.workers.LOADING_FAILED,
        None,
    ),
)
async def test_file_preview_wrap_key_without_loaded_contents_leaves_message_unchanged(contents):
    async with running_preview(contents) as (_app, pilot, preview):
        before = rendered_text(preview)
        assert before.strip()

        await pilot.press('w')
        await pilot.pause()

        assert rendered_text(preview) == before


async def test_file_preview_wrap_state_is_per_preview():
    async with running_preview(LONG_LINE) as (_app, pilot, preview):
        await pilot.press('w')
        await pilot.pause()
        assert preview.max_scroll_x == 0

    async with running_preview(LONG_LINE) as (_app, _pilot, new_preview):
        assert 'word0' in rendered_words(new_preview)
        assert new_preview.max_scroll_x > 0


async def test_file_preview_with_wrap_on_rewraps_when_resized_while_hidden():
    async with running_preview(LONG_LINE, size=(120, 30)) as (app, pilot, preview):
        await pilot.press('w')
        await pilot.pause()
        assert 'word0' in rendered_words(preview)

        preview.styles.display = 'none'
        await pilot.pause()
        await pilot.resize_terminal(60, 30)
        await pilot.pause()
        preview.styles.display = 'block'
        await pilot.pause()

        assert 'word0' in rendered_words(preview)
        assert 'ENDMARK' in rendered_words(preview)
        assert preview.virtual_size.width <= preview.scrollable_content_region.width
        assert preview.max_scroll_x == 0
        assert app._exception is None


async def test_file_preview_toggling_wrap_on_while_scrolled_right_resets_horizontal_scroll():
    async with running_preview(LONG_LINE) as (_app, pilot, preview):
        preview.scroll_to(x=30, animate=False)
        await pilot.pause()
        assert preview.scroll_x > 0

        await pilot.press('w')
        await pilot.pause()

        assert 'word0' in rendered_words(preview)
        assert preview.scroll_x == 0


# Issue #11: piping a file to a command.


def test_file_preview_has_visible_pipe_binding():
    bindings = [
        binding
        for binding in module.File_preview.BINDINGS
        if isinstance(binding, textual.binding.Binding) and binding.key == 'vertical_line'
    ]

    assert len(bindings) == 1
    assert bindings[0].action == 'pipe'
    assert bindings[0].description == 'pipe'
    assert bindings[0].key_display == '|'
    assert bindings[0].show is True


@pytest.mark.parametrize('contents', ('some text', None, NOT_LOADED))
async def test_file_preview_action_pipe_pipes_file_whether_or_not_preview_loaded(contents):
    async with running_preview(contents) as (app, _pilot, preview):
        flexmock(module.borgmatic_browse.pipe).should_receive('pipe_file').with_args(
            app, preview.config, preview.repository, 'archive', 'foo.txt'
        ).once()

        preview.action_pipe()


async def test_file_preview_pressing_vertical_line_pipes_file():
    async with running_preview('some text') as (app, pilot, preview):
        flexmock(module.borgmatic_browse.pipe).should_receive('pipe_file').with_args(
            app, preview.config, preview.repository, 'archive', 'foo.txt'
        ).once()

        await pilot.press('vertical_line')
        await pilot.pause()
