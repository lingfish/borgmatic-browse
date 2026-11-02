import rich.text
import textual.widgets

import borgmatic_browse.bindings
import borgmatic_browse.loading
import borgmatic_browse.sorting
import borgmatic_browse.workers

NO_ARCHIVES_OPTION_ID = 'no-archives'
MATCH_ALL_ARCHIVES_PATTERNS = {'*', 're:.*', 'sh:*'}


def make_no_archives_message(config):
    '''
    Given a configuration dict, return a message explaining why a list of archives is empty.
    '''
    pattern = config.get('match_archives')

    if pattern in MATCH_ALL_ARCHIVES_PATTERNS:
        return 'This repository has no archives.'

    if pattern:
        return f'''No archives match "{pattern}". Use -a '*' to list them all.'''

    return "No archives match the configured archive name format. Use -a '*' to list them all."


class Archives_list(borgmatic_browse.sorting.Sortable, textual.widgets.OptionList):
    '''
    A widget for selecting a single Borg archive from among the archives in a repository. The item
    selection event is handled in a Carousel instance, the parent widget of an Archives_list.
    '''

    BINDINGS = (
        *borgmatic_browse.bindings.OPTION_LIST_BINDINGS,
        *borgmatic_browse.bindings.SORTABLE_BINDINGS,
    )
    SORT_MODES = ('time', 'name')
    DEFAULT_SORT_MODE = 'time'
    DEFAULT_REVERSED = {'time': True, 'name': False}  # noqa: RUF012

    def __init__(self, config, repository):
        '''
        Given a configuration dict and a repository dict, prepare to load the archives from the
        repository for eventual display in this widget. Actual loading kicks off in on_mount()
        below.
        '''
        self.config = config
        self.repository = repository

        super().__init__(classes='panel')
        self.border_title = '📚 archives'
        self.highlighted_option_changed = False
        self.archive_names = {}
        self.init_sort()
        self.archive_loaded = borgmatic_browse.workers.Archive_loaded(self, 'archive loaded')

        self.loading_timer = borgmatic_browse.loading.add_inline_loading_indicator(self)

    @property
    def load_failed(self):
        '''
        Return whether loading archives into this panel failed.
        '''
        return self.archive_loaded.failed

    def on_mount(self):
        '''
        When this widget gets mounted in the DOM, subscribe to archive loaded events so that we can
        find out about archives as they load. Also start loading archives from the repository.

        Loading is started *after* subscribing to the archive loaded signal so that there's not a
        gap where we might miss out on signal publishes.
        '''
        self.archive_loaded.subscribe(self, self.on_archive_loaded)

        borgmatic_browse.workers.add_repository_archives(
            self.app,
            archive_loaded=self.archive_loaded,
            config=self.config,
            repository=self.repository,
        )

    def on_archive_loaded(self, archive):
        '''
        When an archive loads, add it as an option to this archives list, showing its time beside
        its name. Make the prompt a rich.text.Text rather than a markup string, because a name might
        look like markup. But if we get a signal that all path loading is complete, stop and remove
        our loading indicator.
        '''
        if archive is borgmatic_browse.workers.LOADING_DONE:
            self.loading_timer.stop()
            self.remove_option('loading-indicator')

            # If loading failed, then the error is already showing as the explanation.
            if not self.archive_names and not self.archive_loaded.failed:
                self.add_option(
                    textual.widgets.option_list.Option(
                        rich.text.Text(make_no_archives_message(self.config), style='dim'),
                        id=NO_ARCHIVES_OPTION_ID,
                        disabled=True,
                    )
                )

            self.apply_sort()
            return

        latest_pieces = ((' ', ''), ('(latest)', 'dim')) if len(self.options) == 1 else ()
        self.archive_names[archive.selector] = archive.name

        # Textual 6.0.0+ has self.highlighted_option, but we want to support older versions.
        highlighted_option = (
            self.options[self.highlighted] if self.highlighted is not None else None
        )

        option = textual.widgets.option_list.Option(
            rich.text.Text.assemble((archive.time, 'dim'), '  ', archive.name, *latest_pieces),
            id=archive.selector,
        )
        option.load_index = len(self.archive_names) - 1

        loading_indicator = self.get_option('loading-indicator')
        self.remove_option('loading-indicator')
        self.add_options((option, loading_indicator))

        # Retain the highlighted option position even as other options load around it.
        self.highlighted = (
            self.get_option_index(highlighted_option.id)
            if highlighted_option and self.highlighted_option_changed
            else 0
        )
        self.apply_sort()

    def sort_options(self, options):
        '''
        Given options, return them in display order for the current sort mode and direction, with
        any options that aren't archives last, like the loading indicator.

        Order by time using the order the archives loaded in, newest first, rather than their times,
        because the times have only minute resolution and archives can share a minute. So
        "reversed" means load order, as newest first is what it means for the other time sorts.
        '''
        archive_options = [option for option in options if option.id in self.archive_names]
        other_options = [option for option in options if option.id not in self.archive_names]

        if self.sort_mode == 'name':
            sorted_options = sorted(
                archive_options,
                key=lambda option: (self.archive_names[option.id], option.load_index),
                reverse=self.sort_reversed,
            )
        else:
            sorted_options = sorted(
                archive_options,
                key=lambda option: option.load_index,
                reverse=not self.sort_reversed,
            )

        return [*sorted_options, *other_options]

    def on_option_list_option_highlighted(self, event):
        '''
        When the highlighted option changes, record that fact. This flag is consumed in
        borgmatic_browse.workers.add_repository_archives() in order to retain the
        highlighted option even as other options load around it.
        '''
        if self.highlighted not in {None, 0}:
            self.highlighted_option_changed = True
