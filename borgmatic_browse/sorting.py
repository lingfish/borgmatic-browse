class Sortable:
    '''
    A mixin for a textual.widgets.OptionList panel whose options can be sorted in several modes and
    in either direction. A subclass must define:

      * SORT_MODES: a tuple of the available sort mode names
      * DEFAULT_SORT_MODE: the name of the sort mode to start with
      * DEFAULT_REVERSED: a dict from sort mode name to whether that mode starts out reversed
      * sort_options(): a method that, given options, returns them in display order

    A subclass must also call init_sort() from its constructor.
    '''

    SORT_MODES = ()
    DEFAULT_SORT_MODE = None
    DEFAULT_REVERSED = {}  # noqa: RUF012

    def init_sort(self, sort_mode=None, sort_reversed=None):
        '''
        Given an optional sort mode name and an optional sort direction, start sorting that way.
        Default to the default sort mode and that mode's default direction.
        '''
        self.sort_mode = sort_mode or self.DEFAULT_SORT_MODE
        self.sort_reversed = (
            self.DEFAULT_REVERSED[self.sort_mode] if sort_reversed is None else sort_reversed
        )
        self.update_sort_subtitle()

    def update_sort_subtitle(self):
        '''
        Show the current sort mode and direction in this panel's border subtitle.
        '''
        self.border_subtitle = f'sort: {self.sort_mode} {"↓" if self.sort_reversed else "↑"}'

    def set_sort_mode(self, mode):
        '''
        Given a sort mode name, sort by that mode in its default direction.
        '''
        self.sort_mode = mode
        self.sort_reversed = self.DEFAULT_REVERSED[mode]
        self.apply_sort()

    def action_cycle_sort(self):
        '''
        Sort by the next sort mode, wrapping around after the last one.
        '''
        next_index = (self.SORT_MODES.index(self.sort_mode) + 1) % len(self.SORT_MODES)
        self.set_sort_mode(self.SORT_MODES[next_index])

    def action_reverse_sort(self):
        '''
        Flip the direction of the current sort.
        '''
        self.sort_reversed = not self.sort_reversed
        self.apply_sort()

    def apply_sort(self):
        '''
        Put this panel's options in sorted order and keep the highlighted option highlighted. Skip
        rebuilding the options if they're already in order, since that's common while loading and
        rebuilding repaints the whole list.
        '''
        self.update_sort_subtitle()

        options = list(self.options)
        sorted_options = list(self.sort_options(options))

        if [option.id for option in sorted_options] == [option.id for option in options]:
            return

        highlighted_id = options[self.highlighted].id if self.highlighted is not None else None

        self.clear_options()
        self.add_options(sorted_options)

        if highlighted_id is not None:
            self.highlighted = self.get_option_index(highlighted_id)
