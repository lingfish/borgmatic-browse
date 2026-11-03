# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/), and versions follow [semantic
versioning](https://semver.org/).

## Unreleased

## 0.7.0 - 2026-11-03

### Added

* #11: Press `|` on a file, or in a file preview, to pipe the whole file to a command like `jq .` and see
  its output and exit status in a window. The prompt remembers the commands you've used until you quit.

## 0.6.0 - 2026-11-03

### Added

* #9: Press `b` to open a shell, and type `exit` to return to where you were. The shell has
  `BORGMATIC_BROWSE_SHELL=1` in its environment, which you can use to show it in your prompt.

## 0.5.0 - 2026-11-03

### Added

* #10: Press `w` in a file preview to toggle word wrap.

### Changed

* In a file preview that's scrolled sideways, `←` and `h` now scroll left, and only go to the previous
  panel from the start of the line.

### Fixed

* #12: Show long lines in file previews rather than cutting them off at the width of the console. They
  now scroll sideways with `→` and `←`, and are cut off at 2,000 columns, with a notification saying so.

## 0.4.0 - 2026-11-02

### Changed

* The minimum Textual version is now 8.0.

### Fixed

* #4: Show an error when a repository needs a passphrase and none is configured, instead of letting Borg
  prompt underneath the UI, which left the app stuck with no way to quit.
* #5: Selecting an item that failed to load now tries again, so you don't have to restart after plugging
  in a disk.
* #3: Exit with an error status when the app crashes.
* #6: Explain why an archives list is empty, rather than showing nothing.
* #7: Show error notifications literally, as text resembling markup could display wrongly.

## 0.3.0 - 2026-11-01

### Added

* Add a README section explaining why a directory can have no entry in an archive. It commonly comes from
  a trailing slash in a `patterns` rule, which also means the directory's ownership and permissions aren't
  kept in the archive.

### Changed

* Show `<no dir entry>` in the time column for a directory that has no entry of its own in the archive,
  instead of a blank that looked like a bug.

## 0.2.0 - 2026-11-01

### Added

* Sort directory lists by name, size or time, and archive lists by time or name. Press `s` to change the
  sort and `r` to reverse it, or use the command palette with `c`. Directories stay above files in every
  order.
* Show modification times on files and directories, and the time of each archive.
* Show the current repository, archive and path in the header.
* Add a `-a` / `--match-archives` flag for choosing which archives to list. Use `-a '*'` to list them all.

### Changed

* Files and symlinks now mix by name in directory lists, rather than being grouped by icon.
* The page up and page down keys no longer appear in the footer of lists, to make room for the new keys.
  They still work.

### Fixed

* #1: Show Borg errors, such as a missing repository, in the UI instead of crashing the app.
* #2: Show symlink targets on Borg 2.
* Support identically named archives on Borg 2, which crashed the app.

## 0.1.0 - 2026-11-01

First release of borgmatic-browse: borgmatic's experimental browse action as a standalone Textual TUI,
extracted at borgmatic commit `bb8ff56c` with its history and authorship preserved.

### Added

* A `borgmatic-browse` command with `--config`, `--verbosity` and `--override` flags.

### Fixed

* Quitting terminates Borg child processes directly instead of signalling the process group, which exited
  with status 143 and misbehaved under wrappers such as `uv run`.
