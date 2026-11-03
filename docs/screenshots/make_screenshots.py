'''
Make the README's screenshots: build a throwaway Borg repository of made-up demo data, run the app
headless against it with real Borg, save each screen as an SVG, and turn the SVGs into PNGs with
headless Chrome, which renders emoji properly and gives images that PyPI shows.

Usage: uv run python docs/screenshots/make_screenshots.py BORG WORK_DIRECTORY

BORG is a Borg 1 binary, such as the one tests/smoke/make_fixtures.sh installs. WORK_DIRECTORY is
replaced.
'''

import asyncio
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

import borgmatic.logger

import borgmatic_browse.app
import borgmatic_browse.carousel
import borgmatic_browse.pipe

SCREENSHOTS_DIRECTORY = pathlib.Path(__file__).resolve().parent
SCREEN_SIZE = (120, 26)
PASSPHRASE = 'demo'
CHROME = 'google-chrome'
CONFIG_PATH = '/etc/borgmatic/config.yaml'
ARCHIVE_TIMES = tuple(f'2026-10-{day}T02:00:00' for day in range(25, 32))
WAIT_SECONDS = 30

BORGMATIC_CONFIG = '''\
source_directories:
    - /etc
    - /home

repositories:
    - path: ssh://borg@nas.local/./laptop.borg
      label: nas

keep_daily: 7
keep_weekly: 4
keep_monthly: 6

checks:
    - name: repository
    - name: archives
      frequency: 2 weeks
'''

PACKAGE_JSON = {
    'name': 'weather-dashboard',
    'version': '1.4.2',
    'private': True,
    'scripts': {'dev': 'vite', 'build': 'vite build', 'test': 'vitest run'},
    'dependencies': {'chart.js': '^4.4.0', 'date-fns': '^3.6.0', 'vue': '^3.4.21'},
    'devDependencies': {'vite': '^5.2.0', 'vitest': '^1.5.0'},
}

MAIN_PY = '''\
import json
import urllib.request

FORECAST_URL = 'https://api.example.com/forecast?city={city}'


def fetch_forecast(city):
    with urllib.request.urlopen(FORECAST_URL.format(city=city)) as response:
        return json.load(response)


if __name__ == '__main__':
    print(fetch_forecast('Melbourne'))
'''


def write_demo_files(source):
    '''
    Given a directory, fill it with made-up files that look like a small laptop's /etc and /home,
    with varied sizes and times.
    '''
    files = {
        'etc/borgmatic/config.yaml': BORGMATIC_CONFIG,
        'etc/hosts': '127.0.0.1\tlocalhost\n192.168.1.20\tnas.local\n',
        'etc/hostname': 'laptop\n',
        'home/alex/.bashrc': 'export EDITOR=vim\nalias ll="ls -l"\n',
        'home/alex/notes.md': '# Notes\n\n* Renew the domain in December\n',
        'home/alex/projects/weather/package.json': json.dumps(PACKAGE_JSON, indent=2) + '\n',
        'home/alex/projects/weather/main.py': MAIN_PY,
        'home/alex/projects/weather/README.md': '# Weather dashboard\n',
        'home/alex/Documents/tax-return-2025.pdf': os.urandom(412_000),
        'home/alex/Documents/lease.pdf': os.urandom(187_000),
        'home/alex/Music/playlist.m3u': 'track01.flac\ntrack02.flac\n',
        'home/alex/Music/track01.flac': os.urandom(3_100_000),
        'home/alex/Music/track02.flac': os.urandom(2_700_000),
        'home/alex/Pictures/beach.jpg': os.urandom(2_400_000),
        'home/alex/Pictures/hike.jpg': os.urandom(3_900_000),
        'home/alex/Pictures/cat.jpg': os.urandom(1_200_000),
        'home/alex/backup.log': 'Backup finished\n' * 400,
    }
    times = {source / 'home/alex/current-project': 1_761_000_000}

    (source / 'home/alex').mkdir(parents=True)
    (source / 'home/alex/current-project').symlink_to('projects/weather')

    for index, (path, content) in enumerate(files.items()):
        file_path = source / path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            file_path.write_bytes(content)
        else:
            file_path.write_text(content)

        times[file_path] = 1_760_000_000 + index * 360_000

    for directory in sorted(source.rglob('*'), key=lambda path: -len(path.parts)):
        if directory.is_dir() and not directory.is_symlink():
            times[directory] = max(
                (times.get(child, 1_760_000_000) for child in directory.iterdir()),
                default=1_760_000_000,
            )

    for path, timestamp in times.items():
        os.utime(path, (timestamp, timestamp), follow_symlinks=False)


def make_repository(borg, work):
    '''
    Given a Borg 1 binary and an empty work directory, make demo data and a repository with a few
    archives of it in the work directory, and return the repository path.
    '''
    source = work / 'source'
    repository = work / 'laptop.borg'
    write_demo_files(source)
    subprocess.run(
        (borg, 'init', '--encryption=repokey', str(repository)), check=True, capture_output=True
    )

    for archive_time in ARCHIVE_TIMES:
        subprocess.run(
            (
                borg,
                'create',
                '--timestamp',
                archive_time,
                f'{repository}::laptop-{archive_time}',
                'etc',
                'home',
            ),
            check=True,
            cwd=source,
        )

    return repository


async def wait_for(pilot, predicate):
    '''
    Given a Textual pilot and a function returning whether the app is ready, wait until it is, and
    raise if that takes too long.
    '''
    end_time = time.monotonic() + WAIT_SECONDS

    while not predicate():
        if time.monotonic() > end_time:
            raise TimeoutError(f'Timed out waiting for {predicate.__doc__}')

        await pilot.pause(0.1)

    await pilot.pause(0.5)


async def select(app, pilot, option_id):
    '''
    Given an app, its pilot, and the ID of an option in the focused panel, highlight that option
    and select it.
    '''
    carousel = app.query_one(borgmatic_browse.carousel.Carousel)
    panel = carousel.focused_panel
    panel.highlighted = panel.get_option_index(option_id)
    await pilot.pause()
    carousel.action_next(option_id)
    await pilot.pause()

    return carousel.focused_panel


async def open_archive(app, pilot):
    '''
    Given an app and its pilot, wait for the archives to list, select the latest archive, and
    return its root directory list once its paths have all loaded.
    '''
    archives_list = await select(app, pilot, 0)

    def archives_loaded():
        '''the archives to load'''
        return archives_list.option_count and not any(
            option.id == 'loading-indicator' for option in archives_list.options
        )

    await wait_for(pilot, archives_loaded)
    directory_list = await select(app, pilot, f'laptop-{ARCHIVE_TIMES[-1]}')

    def paths_loaded():
        '''the archive's paths to load'''
        return directory_list.path_loaded.complete

    await wait_for(pilot, paths_loaded)

    return archives_list, directory_list


async def take_screenshots(config):
    '''
    Given a configuration dict, run the app on each screen to show, and return a dict from
    screenshot name to SVG.
    '''
    screenshots = {}

    async def run(name, drive):
        app = borgmatic_browse.app.Browse_app({CONFIG_PATH: config})

        async with app.run_test(size=SCREEN_SIZE) as pilot:
            await drive(app, pilot)
            screenshots[name] = app.export_screenshot(title='borgmatic-browse')

    async def directory_listing(app, pilot):
        _archives_list, _directory_list = await open_archive(app, pilot)
        await select(app, pilot, 'home')
        panel = await select(app, pilot, 'alex')
        panel.set_sort_mode('size')
        panel.highlighted = panel.get_option_index('Pictures')
        await pilot.pause(0.5)

    async def archives(app, pilot):
        archives_list, _directory_list = await open_archive(app, pilot)
        app.query_one(borgmatic_browse.carousel.Carousel).action_previous()
        archives_list.highlighted = 0
        await pilot.pause(0.5)

    async def file_preview(app, pilot):
        await open_archive(app, pilot)
        await select(app, pilot, 'etc')
        await select(app, pilot, 'borgmatic')
        preview = await select(app, pilot, 'config.yaml')

        def preview_loaded():
            '''the file preview to load'''
            return preview.file_contents is not None

        await wait_for(pilot, preview_loaded)

    async def pipe(app, pilot):
        await open_archive(app, pilot)

        for component in ('home', 'alex', 'projects', 'weather'):
            panel = await select(app, pilot, component)

        panel.highlighted = panel.get_option_index('package.json')
        output = borgmatic_browse.pipe.Command_output(
            config,
            config['repositories'][0],
            f'laptop-{ARCHIVE_TIMES[-1]}',
            'home/alex/projects/weather/package.json',
            'jq -C .',
        )
        app.push_screen(output)

        def output_loaded():
            '''the command's output'''
            return output.result_loaded

        await wait_for(pilot, output_loaded)

    await run('directory-listing', directory_listing)
    await run('archives', archives)
    await run('file-preview', file_preview)
    await run('pipe', pipe)

    return screenshots


def convert_to_png(svg, png_path, work):
    '''
    Given an SVG screenshot, a path for the PNG, and a work directory, render the SVG to a PNG at
    twice its size with headless Chrome. Inline the SVG in a page rather than loading it as an
    image, since an image can't load the web font that the SVG refers to.
    '''
    width, height = (
        float(size) for size in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups()
    )
    page = work / f'{png_path.stem}.html'
    page.write_text(
        '<!DOCTYPE html><html><body style="margin: 0; background: transparent">'
        f'<div style="width: {width}px; height: {height}px">{svg}</div></body></html>'
    )
    subprocess.run(
        (
            CHROME,
            '--headless',
            '--disable-gpu',
            '--hide-scrollbars',
            '--force-device-scale-factor=2',
            '--default-background-color=00000000',
            '--virtual-time-budget=10000',
            f'--window-size={int(width)},{int(height)}',
            f'--screenshot={png_path}',
            page.as_uri(),
        ),
        check=True,
        capture_output=True,
    )


def main():
    '''
    Given a Borg binary and a work directory on the command line, make the screenshots.
    '''
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    borg = str(pathlib.Path(sys.argv[1]).resolve())
    work = pathlib.Path(sys.argv[2]).resolve()
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    # Borg takes archive times as UTC, so show them in UTC too.
    os.environ.update(BORG_BASE_DIR=str(work / 'base'), BORG_PASSPHRASE=PASSPHRASE, TZ='UTC')
    time.tzset()

    repository = make_repository(borg, work)
    config = {
        'repositories': [{'path': str(repository), 'label': 'nas'}],
        'encryption_passphrase': PASSPHRASE,
        'local_path': borg,
        'match_archives': '*',
    }
    borgmatic.logger.configure_logging(logging.WARNING)

    for name, svg in asyncio.run(take_screenshots(config)).items():
        (work / f'{name}.svg').write_text(svg)
        convert_to_png(svg, SCREENSHOTS_DIRECTORY / f'{name}.png', work)
        print(f'Made {name}.png')

    return 0


if __name__ == '__main__':
    sys.exit(main())
