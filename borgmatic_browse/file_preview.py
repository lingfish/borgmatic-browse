import logging

import rich.cells
import rich.syntax
import textual.binding
import textual.widgets

import borgmatic_browse.loading
import borgmatic_browse.workers

logger = logging.getLogger('__name__')

# The widest that unwrapped file contents get rendered. RichLog pads every rendered line to the render
# width, so with a file's longest line as the only limit, one very long line makes all the others
# expensive. A 100 kB file with a 50,000 column line and many short lines took seconds and gigabytes.
MAXIMUM_PREVIEW_WIDTH = 2000
TAB_SIZE = 4


def get_longest_line_width(file_contents):
    '''
    Given a file's contents as a string, return the width in terminal cells of its longest line, with
    tabs expanded the same way as when they're rendered.
    '''
    return max(
        (rich.cells.cell_len(line.expandtabs(TAB_SIZE)) for line in file_contents.splitlines()),
        default=0,
    )


class File_preview(textual.widgets.RichLog):
    '''
    A widget for extracting and previewing the contents of a file stored in a Borg archive.
    '''

    BINDINGS = (
        *textual.widgets.RichLog.BINDINGS,
        textual.binding.Binding(
            key='up,k', action='scroll_up', description='scroll up', show=True, priority=True
        ),
        textual.binding.Binding(
            key='down,j', action='scroll_down', description='scroll down', show=True, priority=True
        ),
        textual.binding.Binding(
            key='pageup', action='page_up', description='page up', show=True, priority=True
        ),
        textual.binding.Binding(
            key='pagedown', action='page_down', description='page down', show=True, priority=True
        ),
        textual.binding.Binding(key='w', action='toggle_wrap', description='wrap', show=True),
    )

    def __init__(self, config, repository, archive_name, file_path, archive_label=None):
        '''
        Given a configuration dict, a repository dict, an archive name or ID to give Borg, the path
        of a file in the archive, and an optional archive name to display (if the archive is
        otherwise selected by ID), prepare to load the file's contents for eventual display in this
        widget. Actual loading kicks off in on_mount() below.
        '''
        self.config = config
        self.repository = repository
        self.archive_name = archive_name
        self.archive_label = archive_label or archive_name
        self.file_path = file_path

        super().__init__(classes='panel')
        self.border_title = f'📄 {self.file_path} preview'
        self.auto_scroll = False
        self.file_contents = None
        self.rendered_panel_width = None
        self.file_preview_loaded = borgmatic_browse.workers.File_preview_loaded(
            self, 'file preview loaded'
        )

        self.loading_timer = borgmatic_browse.loading.add_inline_loading_indicator(self)

    @property
    def load_failed(self):
        '''
        Return whether loading the file into this panel failed.
        '''
        return self.file_preview_loaded.failed

    def on_mount(self):
        '''
        When this widget gets mounted in the DOM, subscribe to archive loaded events so that we can
        find out about archives as they load. Also start loading file contents from the archive.

        Loading is started *after* subscribing to the file preview loaded signal so that there's not
        a gap where we might miss out on signal publishes.
        '''
        self.file_preview_loaded.subscribe(self, self.on_file_preview_loaded)

        borgmatic_browse.workers.load_file_preview(
            self.app,
            file_preview_loaded=self.file_preview_loaded,
            config=self.config,
            repository=self.repository,
            archive_name=self.archive_name,
            file_path=self.file_path,
        )

    def on_file_preview_loaded(self, file_contents):
        '''
        When a file loads, write its contents (syntax highlighted) to this file preview widget. But
        if loading failed, say so instead.
        '''
        self.loading_timer.stop()
        self.clear()

        if file_contents is borgmatic_browse.workers.LOADING_FAILED:
            self.write('Error loading this file. Press v to view the logs.')
        elif file_contents is None:
            self.write('Cannot display a preview for this file')
        else:
            self.file_contents = file_contents
            self.render_file_contents()

            if get_longest_line_width(file_contents) > MAXIMUM_PREVIEW_WIDTH:
                self.notify(
                    f'Lines over {MAXIMUM_PREVIEW_WIDTH} columns are cut off. Press w to wrap them.',
                    severity='warning',
                )

    def render_file_contents(self):
        '''
        Render the loaded file contents (syntax highlighted) into this widget, wrapped to the width
        of the panel if wrapping is on. Otherwise, make them wide enough for the longest line, up to
        a maximum, so that they scroll horizontally. Stay at about the same relative position in the
        file, since the number of rendered lines may have changed.

        Pass the width explicitly, because otherwise RichLog limits the content to the width of the
        console and imposes a minimum width that's wider than a narrow panel.
        '''
        panel_width = self.scrollable_content_region.width
        scroll_fraction = self.scroll_y / self.max_scroll_y if self.max_scroll_y else 0
        self.rendered_panel_width = panel_width

        self.clear()

        # Only pass the file path and not its contents to guess_lexer(). Passing the contents is
        # more accurate, but also much slower.
        self.write(
            rich.syntax.Syntax(
                self.file_contents,
                rich.syntax.Syntax.guess_lexer(self.file_path),
                tab_size=TAB_SIZE,
                word_wrap=self.wrap,
            ),
            width=panel_width
            if self.wrap
            else max(
                min(get_longest_line_width(self.file_contents), MAXIMUM_PREVIEW_WIDTH),
                panel_width,
                1,
            ),
        )

        if scroll_fraction:
            self.scroll_to(y=scroll_fraction * self.max_scroll_y, animate=False)

    def action_toggle_wrap(self):
        '''
        Toggle word wrapping of the file contents, if any have loaded.
        '''
        if self.file_contents is None:
            return

        self.wrap = not self.wrap
        self.render_file_contents()

    def on_resize(self, event):
        '''
        When the panel changes width, render the file contents again to fit it, since rendered lines
        have a fixed width. Do so after RichLog has handled the same event, as that's when it starts
        rendering content rather than deferring it.

        Ignore a zero width, which means that the panel is hidden, and any resize that doesn't change
        the width, as rendering changes this widget's virtual size and that counts as a resize too.
        '''
        if (
            self.file_contents is not None
            and event.size.width
            and self.scrollable_content_region.width != self.rendered_panel_width
        ):
            self.call_later(self.render_file_contents)
