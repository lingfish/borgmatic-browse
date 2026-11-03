import pathlib
import re
import subprocess

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = REPOSITORY_ROOT / '.github' / 'scripts' / 'get_changelog_section.sh'
REAL_CHANGELOG = REPOSITORY_ROOT / 'CHANGELOG.md'
VERSION_HEADING_PATTERN = re.compile(r'^## (\d+)\.(\d+)\.(\d+) - \d{4}-\d{2}-\d{2}$')

SAMPLE_CHANGELOG = '''# Changelog

## Unreleased

### Added

* Something new.

## 0.4.0 - 2026-11-02

### Fixed

* Something else.

## 0.3.0 - 2026-10-01

### Added

* Older thing.
'''


def run_script(*arguments, cwd=None):
    # The script is invoked directly rather than via a shell, so that a missing script raises
    # FileNotFoundError instead of passing tests that only expect a non-zero status.
    return subprocess.run(  # noqa: S603
        [str(SCRIPT), *arguments], check=False, capture_output=True, text=True, cwd=cwd
    )


def write_changelog(tmp_path, text):
    path = tmp_path / 'CHANGELOG.md'
    path.write_text(text)

    return path


def test_get_changelog_section_prints_only_the_middle_section_body(tmp_path):
    path = write_changelog(tmp_path, SAMPLE_CHANGELOG)

    result = run_script('0.4.0', str(path))

    assert result.returncode == 0
    assert result.stdout.strip() == '### Fixed\n\n* Something else.'
    assert '0.3.0' not in result.stdout
    assert 'Unreleased' not in result.stdout


def test_get_changelog_section_omits_the_heading_line(tmp_path):
    path = write_changelog(tmp_path, SAMPLE_CHANGELOG)

    result = run_script('0.4.0', str(path))

    assert '## 0.4.0' not in result.stdout


def test_get_changelog_section_prints_last_section_to_end_of_file(tmp_path):
    path = write_changelog(tmp_path, SAMPLE_CHANGELOG)

    result = run_script('0.3.0', str(path))

    assert result.returncode == 0
    assert result.stdout.strip() == '### Added\n\n* Older thing.'


def test_get_changelog_section_prints_last_section_without_trailing_newline(tmp_path):
    path = write_changelog(tmp_path, '## 0.1.0 - 2026-01-01\n\n* Only line.')

    result = run_script('0.1.0', str(path))

    assert result.returncode == 0
    assert result.stdout.strip() == '* Only line.'


def test_get_changelog_section_keeps_subheadings_and_inner_blank_lines(tmp_path):
    path = write_changelog(
        tmp_path,
        '''# Changelog

## 1.0.0 - 2026-05-05

### Added

* One.

* Two.

### Fixed

* Three.

## 0.9.0 - 2026-04-04

* Old.
''',
    )

    result = run_script('1.0.0', str(path))

    assert result.returncode == 0
    assert result.stdout == '### Added\n\n* One.\n\n* Two.\n\n### Fixed\n\n* Three.\n'


def test_get_changelog_section_strips_leading_and_trailing_blank_lines(tmp_path):
    path = write_changelog(
        tmp_path,
        '## 1.0.0 - 2026-05-05\n\n\n* Body.\n\n\n## 0.9.0 - 2026-04-04\n\n* Old.\n',
    )

    result = run_script('1.0.0', str(path))

    assert result.returncode == 0
    assert result.stdout == '* Body.\n'


@pytest.mark.parametrize('other_heading', ('## 10.1.0 - 2026-01-01', '## 0.1.01 - 2026-01-01'))
def test_get_changelog_section_matches_version_exactly(tmp_path, other_heading):
    path = write_changelog(tmp_path, f'# Changelog\n\n{other_heading}\n\n* Not this one.\n')

    result = run_script('0.1.0', str(path))

    assert result.returncode != 0
    assert result.stdout == ''
    assert '0.1.0' in result.stderr


def test_get_changelog_section_treats_dots_in_version_literally(tmp_path):
    path = write_changelog(tmp_path, '# Changelog\n\n## 0x1x0 - 2026-01-01\n\n* Not this one.\n')

    result = run_script('0.1.0', str(path))

    assert result.returncode != 0
    assert result.stdout == ''
    assert '0.1.0' in result.stderr


def test_get_changelog_section_does_not_match_unreleased_by_version(tmp_path):
    path = write_changelog(tmp_path, SAMPLE_CHANGELOG)

    result = run_script('Unreleased', str(path))

    assert result.returncode != 0
    assert result.stdout == ''


def test_get_changelog_section_ignores_version_mentioned_in_body_text(tmp_path):
    path = write_changelog(
        tmp_path,
        '''# Changelog

## 0.5.0 - 2026-12-01

* Fixes a bug introduced in
  ## 0.4.0 - 2026-11-02 which is quoted here.
* See also ## 0.4.0 in the notes.
''',
    )

    result = run_script('0.4.0', str(path))

    assert result.returncode != 0
    assert result.stdout == ''
    assert '0.4.0' in result.stderr


def test_get_changelog_section_with_missing_version_fails_naming_the_version(tmp_path):
    path = write_changelog(tmp_path, SAMPLE_CHANGELOG)

    result = run_script('9.9.9', str(path))

    assert result.returncode != 0
    assert result.stdout == ''
    assert '9.9.9' in result.stderr


def test_get_changelog_section_with_empty_section_fails(tmp_path):
    path = write_changelog(
        tmp_path, '## 0.2.0 - 2026-02-02\n## 0.1.0 - 2026-01-01\n\n* Something.\n'
    )

    result = run_script('0.2.0', str(path))

    assert result.returncode != 0
    assert result.stdout == ''
    assert '0.2.0' in result.stderr


def test_get_changelog_section_with_blank_only_section_fails(tmp_path):
    path = write_changelog(
        tmp_path, '## 0.2.0 - 2026-02-02\n\n\n\n## 0.1.0 - 2026-01-01\n\n* Something.\n'
    )

    result = run_script('0.2.0', str(path))

    assert result.returncode != 0
    assert result.stdout == ''
    assert '0.2.0' in result.stderr


def test_get_changelog_section_with_empty_final_section_fails(tmp_path):
    path = write_changelog(tmp_path, '## 0.1.0 - 2026-01-01\n\n')

    result = run_script('0.1.0', str(path))

    assert result.returncode != 0
    assert result.stdout == ''


def test_get_changelog_section_with_no_arguments_fails():
    result = run_script()

    assert result.returncode != 0
    assert result.stdout == ''


def test_get_changelog_section_with_missing_changelog_file_fails(tmp_path):
    result = run_script('0.4.0', str(tmp_path / 'nonexistent.md'))

    assert result.returncode != 0
    assert result.stdout == ''


def test_get_changelog_section_defaults_to_changelog_in_current_directory(tmp_path):
    write_changelog(tmp_path, SAMPLE_CHANGELOG)

    result = run_script('0.4.0', cwd=tmp_path)

    assert result.returncode == 0
    assert result.stdout.strip() == '### Fixed\n\n* Something else.'


def real_changelog_headings():
    return [line for line in REAL_CHANGELOG.read_text().splitlines() if line.startswith('## ')]


def real_changelog_versions():
    return [
        heading[len('## ') :].split(' ')[0]
        for heading in real_changelog_headings()
        if VERSION_HEADING_PATTERN.match(heading)
    ]


def test_real_changelog_starts_with_unreleased_heading():
    assert real_changelog_headings()[0] == '## Unreleased'


def test_real_changelog_version_headings_have_expected_format():
    for heading in real_changelog_headings()[1:]:
        assert VERSION_HEADING_PATTERN.match(heading), heading


def test_real_changelog_versions_run_newest_first():
    versions = [
        tuple(int(part) for part in VERSION_HEADING_PATTERN.match(heading).groups())
        for heading in real_changelog_headings()[1:]
    ]

    assert versions == sorted(versions, reverse=True)


def test_real_changelog_script_succeeds_for_every_version_heading():
    # Reading the changelog fails first if it is missing, which is the desired failure.
    versions = real_changelog_versions()

    assert versions

    for version in versions:
        result = run_script(version, str(REAL_CHANGELOG))

        assert result.returncode == 0, (version, result.stderr)
        assert result.stdout.strip(), version
