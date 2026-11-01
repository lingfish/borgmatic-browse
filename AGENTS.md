# borgmatic-browse

A Textual TUI for browsing Borg archives, derived from borgmatic's browse action at commit
`bb8ff56c`. It's independent of upstream, and depends on the `borgmatic` package rather than vendoring
it. See `README.md` for what it does and its known issues.

## Rules

* **Nothing from this project goes upstream.** AI may write code here, and borgmatic doesn't accept
  AI-written code. Don't modify `~/PycharmProjects/borgmatic`.
* **Don't commit, push, tag or release until the user says so.** Approval covers that one action, not
  later ones. Going public, publishing and filing issues are visible to others, so confirm them too.
* **Use TDD through the `test-engineer` subagent with the model `claude-agent/sonnet`.** It writes the
  failing tests and doesn't touch `borgmatic_browse/`. Check that they fail because the behaviour is
  missing, then implement the fix. Give it the full context, since it starts fresh.
* **File a GitHub issue before fixing a bug** if there isn't one, and use `Fixes #N` in the commit.
* **Check behaviour against real Borg, not only mocks.** Mocked tests have missed real bugs here. Use
  the smoke harness below, and say plainly what you didn't test.
* **Don't use `sudo`.** The user's Borg is in `/root/.local/bin` and their configuration files in
  `/etc/borgmatic*` aren't readable by this user, so test with throwaway copies. Ask the user to run
  anything that needs root.

## Commands

```bash
uv sync
uv run pytest                  # Must keep 100% coverage.
uv run ruff check
uv run ruff format --check
```

Run the tests under another time zone too when touching times: `TZ=Pacific/Apia uv run pytest --no-cov`.

## Smoke tests against real Borg

```bash
tests/smoke/make_fixtures.sh /tmp/opencode/smoke      # Slow the first time. Installs Borg 1 and 2.
uv run python tests/smoke/check_basics.py /tmp/opencode/smoke
```

`tests/smoke/driver.py` runs the app in a pseudo-terminal and reads the screen. A wait in a script can
match before the screen has finished repainting, so wait on the exact text you're checking, and treat
empty results with suspicion. The fixtures are throwaway, and contain `elara-implicit`-style archives
with directories that have no entry of their own.

Run real Borg commands with the fixtures' `BORG_BASE_DIR` rather than changing `HOME`, since a
different `HOME` logs `gh` out.

## Code style

Match the surrounding code, which comes from borgmatic: single quotes, `Title_case` classes, fully
qualified imports like `borgmatic_browse.workers.LOADING_DONE`, and docstrings that start with "Given
...". Prefer `rich.text.Text` to markup strings for anything containing archive names or paths, because
Rich's escaping doesn't match how Textual parses markup.

## Compatibility

* borgmatic's Python modules aren't a stable API, so `pyproject.toml` pins a narrow version range.
* Borg 1 and Borg 2 differ: Borg 2 calls a link target `target` rather than `linktarget`, includes UTC
  offsets in times, and allows identically named archives, which are selected by ID from `2.0.0b11`.

## Releasing

Follow semantic versioning, with tags like `0.3.0` and no `v` prefix. The version comes from the tag.
Wait for CI to pass on the commit, then push the tag. The release workflow publishes to PyPI. Afterwards
check a fresh `pipx install`, which can briefly get the old version straight after publishing, and
create a GitHub release.
