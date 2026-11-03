# borgmatic-browse

[![test](https://github.com/lingfish/borgmatic-browse/actions/workflows/test.yaml/badge.svg)](https://github.com/lingfish/borgmatic-browse/actions/workflows/test.yaml)
[![PyPI](https://img.shields.io/pypi/v/borgmatic-browse)](https://pypi.org/project/borgmatic-browse/)

A [Textual](https://textual.textualize.io/) terminal UI for browsing the Borg archives of the
repositories in your [borgmatic](https://torsion.org/borgmatic/) configuration: drill down from
configuration file to repository, archive, directory, and file preview.

![A directory in an archive, sorted by size](https://raw.githubusercontent.com/lingfish/borgmatic-browse/main/docs/screenshots/directory-listing.png)

## Features

* Browse every repository in your borgmatic configuration, with no mounting, extracting or extra setup.
* See the size and modification time of every path, with each directory's size added up from the files
  beneath it.
* Sort archives and paths by name, size or time with `s`, and reverse the order with `r`.
* Preview files with syntax highlighting, and toggle word wrap with `w`.
* Pipe any file to a command like `jq .` or `wc -l` with `|`, and see its output in a window.
* Open a shell with `b` and come back to where you were.
* See what Borg is doing in the logs panel with `v`, and find any command in the palette with `c`.
* Works with Borg 1 and Borg 2.

See [the screenshots](#screenshots) for more.

## Not an official project

borgmatic-browse is **derived from borgmatic, but it is not part of borgmatic, and it is not an
official or endorsed project**. Please report problems with borgmatic-browse in [this project's
issue tracker](https://github.com/lingfish/borgmatic-browse/issues), not to the borgmatic project.
Conversely, problems with borgmatic itself belong in [borgmatic's issue
tracker](https://projects.torsion.org/borgmatic-collective/borgmatic/issues).

Unlike borgmatic, which doesn't accept AI-written code, this project's code may be written by AI.
For that reason, **nothing from this project should be submitted upstream to borgmatic**.

## Origin and licence

The code began as the experimental `browse` action in borgmatic
(`borgmatic/actions/browse/` and its tests) at commit
[`bb8ff56c`](https://projects.torsion.org/borgmatic-collective/borgmatic/commit/bb8ff56ca6efb5757a051ce7098a4d6cffec0888),
written by Dan Helfman and borgmatic's other contributors. The git history of those paths is
retained here, including the original authors' attribution, so `git log` and `git blame` show who
wrote what.

This is a modified version of that code. Modified from October 2026: the code moved to the
`borgmatic_browse` package and gained a standalone command-line entry point, and any later changes
are recorded in the git history.

Like borgmatic, borgmatic-browse is licensed under the GNU General Public License version 3 or any
later version (GPL-3.0-or-later). See
[LICENSE](https://github.com/lingfish/borgmatic-browse/blob/main/LICENSE). Copyright in the original code remains
with its authors.

## Installation

Install with [pipx](https://pipx.pypa.io/) so that the app gets its own isolated environment:

```bash
pipx install borgmatic-browse
```

`uv tool install borgmatic-browse` works too.

Either way, this installs a compatible version of the borgmatic Python package as a dependency,
rather than using any borgmatic you already have installed. The compatible range is deliberately
narrow, because borgmatic's Python modules aren't a stable API. Borg itself isn't installed: `borg`
must be on your `PATH` or set with `local_path` in your configuration.

## Usage

```bash
borgmatic-browse [-c PATH] [-v VERBOSITY] [-a PATTERN] [--override OPTION.SUBOPTION=VALUE]
```

* `-c`, `--config`: A configuration file or directory. Repeatable. Defaults to the same paths as
  borgmatic.
* `-v`, `--verbosity`: Verbosity of the logs panel, from -2 to 2 as in borgmatic. Defaults to the
  `verbosity` configuration option.
* `-a`, `--match-archives`: Only list archives matching this pattern. Use `-a '*'` to list all
  archives. Defaults to the `match_archives` configuration option.
* `--override`: Override a configuration option. Repeatable.

Press `v` in the UI to see the logs panel and `q` to quit. In a list of archives or paths, press `s`
to change what it's sorted by and `r` to reverse the order, or use the command palette with `c`.
Directories stay above files however a list is sorted. In a file preview, press `w` to toggle word
wrap. Without it, long lines scroll sideways with `→` and `←`, and are cut off at 2,000 columns.

Press `b` to open your shell (`$SHELL`, or `/bin/sh` if that isn't set), and type `exit` to return. It
starts in the directory you launched the app from, since the archive you're browsing isn't on disk.
Anything your configuration provides to Borg, like a passphrase, isn't available in the shell. The shell
has `BORGMATIC_BROWSE_SHELL=1` in its environment, so you can show it in your prompt by adding this to
your `~/.bashrc` or `~/.zshrc`, after your prompt is set:

```bash
PS1="${BORGMATIC_BROWSE_SHELL:+(browse) }$PS1"
```

Press `|` on a file in a list of paths, or in a file preview, to pipe the whole file to a command, like
`jq .` or `wc -l`. The command runs with `/bin/sh`, so pipelines like `jq . | head` work too. Its output
and errors show in a window along with its exit status, and ANSI colours are shown, as from `jq -C .`.
Output over 1,000,000 bytes is cut off and the command stopped. Press `Escape` or `q` to close the
window, which also stops a command that's still running. The prompt starts with the last command you
used, and `↑` and `↓` go through earlier ones, but they're forgotten when you quit.

The exit status is 0 after quitting normally, even if a Borg error was shown along the way, and
non-zero if the configuration can't be loaded or the app crashes.

See [CHANGELOG.md](https://github.com/lingfish/borgmatic-browse/blob/main/CHANGELOG.md) for what's
changed in each version.

## Screenshots

The archives in a repository, newest first:

![The archives in a repository](https://raw.githubusercontent.com/lingfish/borgmatic-browse/main/docs/screenshots/archives.png)

A file preview with syntax highlighting:

![A preview of a borgmatic configuration file](https://raw.githubusercontent.com/lingfish/borgmatic-browse/main/docs/screenshots/file-preview.png)

A file piped to `jq -C .`, which keeps jq's colours:

![The output of piping package.json to jq](https://raw.githubusercontent.com/lingfish/borgmatic-browse/main/docs/screenshots/pipe.png)

## Why some directories show `<no dir entry>`

`<no dir entry>` in the time column means the archive has no entry for that directory, even though
it contains files beneath it. Borg only stores a directory if it matches your patterns, so the app
has no time to show.

This commonly comes from a trailing slash in a `patterns` rule. To Borg, a trailing slash means "the
contents of this directory, but not the directory itself":

```yaml
patterns:
    - R /mnt/data
    - + /mnt/data/photos/    # Stores the contents, but not photos itself.
    - + /mnt/data/music      # Stores music and its contents.
    - '- **'
```

It affects more than this app. A directory that isn't stored also loses its user, group, permissions
and times, so restoring it gives you default values for them. Removing the trailing slash fixes this
for new archives, but not existing ones. Any parents above a matching rule (`/mnt/data` here) still
aren't stored.

To see whether an archive has an entry for a directory, look for it in Borg's listing:

```bash
borg list --format '{type} {mtime} {path}{NL}' REPOSITORY::ARCHIVE | grep -E ' mnt/data/photos$'
```

## Known issues

* Only archives matching `{hostname}-*` are listed by default, because that's borgmatic's default
  archive name format. Use `-a '*'` to list them all, or set `match_archives` or
  `archive_name_format` in your configuration.
* The app can't prompt for a passphrase. If a repository needs one and none is configured, selecting
  it shows an error. Set `encryption_passphrase` or `encryption_passcommand` in your configuration,
  or the `BORG_PASSPHRASE` environment variable.
* If SSH needs a password or a host key confirmation for a remote repository, it may prompt on the
  terminal underneath the UI, and the app may get stuck and not respond to `q`. Use key-based
  authentication with a known host.
* Commands that need a terminal, like `less` or `vim`, don't work with `|`, because a command's
  output goes to a window rather than the terminal.
* If `SHELL` is set to a program that isn't an interactive shell, pressing Ctrl-C in it quits the app
  too, because only interactive shells take the terminal's Ctrl-C for themselves.
* If the app is killed from outside, such as with a SIGTERM, it doesn't restore the terminal or
  stop a running Borg command. Quitting with `q` handles both.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
```

Tests must keep 100% coverage. They don't need Borg, because they mock it out.

To remake the screenshots in `docs/screenshots/` from made-up demo data, give the script a Borg 1
binary, such as the one the smoke fixtures install, and a work directory that it replaces. It needs
`jq` and Google Chrome.

```bash
uv run python docs/screenshots/make_screenshots.py /tmp/smoke/borg1/bin/borg /tmp/screenshots
```

To try the app from the source tree:

```bash
uv run borgmatic-browse -c /path/to/config.yaml -v 1
```

### Releasing

Versions follow [semantic versioning](https://semver.org/): MAJOR.MINOR.PATCH, with no `v`
prefix. While the major version is 0, a minor version bump may include breaking changes, such as a
new borgmatic version requirement.

The package version comes from git tags, via hatch-vcs. To release, rename the `Unreleased` section
of `CHANGELOG.md` to the new version and date, add a new empty `Unreleased` section above it, and
commit that. Then tag the commit on `main` and push the tag:

```bash
git tag 0.1.0
git push origin 0.1.0
```

The release workflow in GitHub Actions then checks that the changelog has notes for that version,
builds the sdist and wheel, and publishes them to PyPI using trusted publishing, so no API tokens
are involved. It then creates a GitHub release from those notes. Running the same workflow by hand from
the Actions tab publishes a development version to TestPyPI instead, which is a way to exercise
the pipeline without releasing.
