import os

import textual.binding
import textual.containers

import borgmatic_browse.archive
import borgmatic_browse.archives_list
import borgmatic_browse.configuration_files_list
import borgmatic_browse.directory_list
import borgmatic_browse.file_preview
import borgmatic_browse.repositories_list


def make_next_panel(focused_panel, option_id):
    '''
    Given a focused panel widget and the selected option ID, return the next panel corresponding to
    that selection. This is the mechanism by which the user can successively drill down from
    configuration file to repository to archive to root directory to non-root directory or file.

    If the particular option ID on the focused panel doesn't have a supported next panel, then
    return None.
    '''
    if isinstance(
        focused_panel, borgmatic_browse.configuration_files_list.Configuration_files_list
    ):
        return borgmatic_browse.repositories_list.Repositories_list(
            config=focused_panel.configs[option_id]
        )

    if isinstance(focused_panel, borgmatic_browse.repositories_list.Repositories_list):
        return borgmatic_browse.archives_list.Archives_list(
            config=focused_panel.config, repository=focused_panel.repositories[option_id]
        )

    if isinstance(focused_panel, borgmatic_browse.archives_list.Archives_list):
        return borgmatic_browse.directory_list.Directory_list(
            config=focused_panel.config,
            repository=focused_panel.repository,
            archive_name=option_id,
            archive_label=focused_panel.archive_names[option_id],
        )

    if isinstance(focused_panel, borgmatic_browse.directory_list.Directory_list):
        option = focused_panel.get_option(option_id)
        path_type = getattr(option, 'path_type', None)

        if path_type == borgmatic_browse.archive.Path_type.DIRECTORY.value:
            return borgmatic_browse.directory_list.Directory_list(
                focused_panel.config,
                focused_panel.repository,
                focused_panel.archive_name,
                path_loaded=focused_panel.path_loaded,
                path_components=(*focused_panel.path_components, option_id),
                archive_label=focused_panel.archive_label,
            )

        if path_type == borgmatic_browse.archive.Path_type.FILE.value:
            return borgmatic_browse.file_preview.File_preview(
                focused_panel.config,
                focused_panel.repository,
                focused_panel.archive_name,
                file_path=os.path.sep.join((*focused_panel.path_components, option_id)),
                archive_label=focused_panel.archive_label,
            )

    return None


LOCATION_SEPARATOR = ' \u203a '


def get_panel_location(panel):
    '''
    Given a panel widget, return a string describing where it is in the drill-down, for display in
    the app's header, with its pieces joined by LOCATION_SEPARATOR: repository, archive, and path. A
    panel that's not within any repository has an empty location.
    '''
    if not isinstance(
        panel,
        (
            borgmatic_browse.archives_list.Archives_list,
            borgmatic_browse.directory_list.Directory_list,
            borgmatic_browse.file_preview.File_preview,
        ),
    ):
        return ''

    repository_label = panel.repository.get('label', panel.repository.get('path'))

    if isinstance(panel, borgmatic_browse.archives_list.Archives_list):
        return repository_label

    path = (
        panel.file_path
        if isinstance(panel, borgmatic_browse.file_preview.File_preview)
        else os.path.sep.join(panel.path_components)
    )

    return LOCATION_SEPARATOR.join(
        piece for piece in (repository_label, panel.archive_label, path) if piece
    )


class Carousel(textual.containers.Horizontal):
    BINDINGS = (
        textual.binding.Binding(
            key='left,h', action='previous', description='previous', priority=True
        ),
    )

    def __init__(self, panels):
        self.panels = panels
        self.focused_panel = panels[0]

        super().__init__()

    def compose(self):
        '''
        Compose with each of the contained panels and focus the first one.
        '''
        yield from self.panels

        self.focused_panel.focus()

    def action_previous(self):
        '''
        Make the previous panel into the focused panel.
        '''
        previous_panel_index = self.panels.index(self.focused_panel) - 1

        if previous_panel_index < 0:
            return

        self.focused_panel.styles.display = 'none'

        self.focused_panel = self.panels[previous_panel_index]
        self.focused_panel.styles.display = 'block'
        self.focused_panel.focus()
        self.app.sub_title = get_panel_location(self.focused_panel)

    def action_next(self, option_id):
        '''
        Hide the current focused panel and create the next one.
        '''
        next_panel_index = self.panels.index(self.focused_panel) + 1

        if next_panel_index < len(self.panels):
            next_panel = self.panels[next_panel_index]
            next_panel.styles.display = 'block'
        else:
            next_panel = make_next_panel(self.focused_panel, option_id)

            if next_panel is None:
                self.notify('Cannot display this content', severity='warning')
                return

            self.panels.append(next_panel)
            next_panel.highlighted = 0

        self.focused_panel.styles.display = 'none'
        self.focused_panel = next_panel
        self.focused_panel.focus()
        self.mount(self.focused_panel)
        self.app.sub_title = get_panel_location(self.focused_panel)

    def on_option_list_option_highlighted(self, event):
        '''
        The highlighted option has changed, so truncate any next panels.
        '''
        next_panel_index = self.panels.index(self.focused_panel) + 1

        del self.panels[next_panel_index:]

    def on_option_list_option_selected(self, event):
        '''
        An option has been selected, so advance to the next panel—unless the option selected is
        "..", in which case go to the previous panel.
        '''
        if (
            event.option_list != self.focused_panel or event.option_id == 'loading-indicator'
        ):  # pragma: no cover
            return

        if event.option_id == '..':
            self.action_previous()
        else:
            self.action_next(event.option_id)
