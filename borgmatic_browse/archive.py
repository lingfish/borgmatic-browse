import argparse
import collections
import contextlib
import enum
import json
import logging
import os
import signal
import subprocess
import threading

import binaryornot.helpers
import borgmatic.borg.extract
import borgmatic.borg.feature
import borgmatic.borg.list
import borgmatic.borg.repo_list
import borgmatic.borg.version
import borgmatic.execute

import borgmatic_browse.times

logger = logging.getLogger(__name__)


class Path_type(enum.Enum):
    DIRECTORY = 'd'
    LINK = 'l'
    PIPE = 'p'
    FILE = '-'


# A data structure capturing an archive in a repository. The selector is what to give Borg to select
# this archive, the name is what to show the user, and the time is already formatted for display.
Archive = collections.namedtuple('Archive', ('selector', 'name', 'time'))

# A data structure capturing a path stored in a Borg archive.
Archive_path = collections.namedtuple(
    'Archive_path',
    ('path_type', 'file_path', 'link_target', 'size', 'mtime'),
    defaults=(0, None),
)


def get_repository_archives(config, repository):
    '''
    Given a configuration dict and a repository dict, return a tuple of the repository's archives,
    oldest first, each as an Archive instance.

    Select archives by ID with Borg versions in which identically named archives form a series,
    since a name doesn't identify a single archive there. borgmatic recognizes the ID when it's
    later given as an archive. Select by name with other versions, which can't select by ID.

    Raise ValueError if an archive's time can't be parsed.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info('Listing repository')
        repo_list_arguments = argparse.Namespace(
            repository=repository['path'],
            short=None,
            format=None,
            json=True,
            prefix=None,
            match_archives=None,
            sort_by=None,
            first=None,
            last=None,
        )
        global_arguments = argparse.Namespace()
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')
        local_borg_version = borgmatic.borg.version.local_borg_version(config, local_path)

        repository_data = json.loads(
            borgmatic.borg.repo_list.list_repository(
                repository['path'],
                config,
                local_borg_version,
                repo_list_arguments,
                global_arguments,
                local_path,
                remote_path,
            )
        )
        select_by_id = borgmatic.borg.feature.available(
            borgmatic.borg.feature.Feature.ARCHIVE_SERIES, local_borg_version
        )

        return tuple(
            Archive(
                archive['id'] if select_by_id else archive['archive'],
                archive['archive'],
                borgmatic_browse.times.format_time(archive['time']),
            )
            for archive in repository_data['archives']
        )


def get_archive_paths(config, repository, archive_name):
    '''
    Given a configuration dict, a repository dict, and an archive name in that repository, get a
    generator of files, directories, symlinks, etc. found in the archive, each as an Archive_path
    instance.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info(f'Listing archive {archive_name}')

        global_arguments = argparse.Namespace()
        local_path = config.get('local_path', 'borg')
        remote_path = config.get('remote_path')
        local_borg_version = borgmatic.borg.version.local_borg_version(config, local_path)

        return (
            Archive_path(
                path_data['type'],
                path_data['path'],
                # Borg 2 calls this key "target".
                path_data.get('linktarget', path_data.get('target')),
                path_data.get('size', 0),
                path_data.get('mtime'),
            )
            for path_data in borgmatic.borg.list.capture_archive_listing(
                repository['path'],
                archive_name,
                config,
                local_borg_version,
                global_arguments,
                # Explicitly include the size and modification time keys even if a custom
                # file_list_format is configured, since they're always shown in the browse UI.
                path_format='{size}{mtime}',
                local_path=local_path,
                remote_path=remote_path,
            )
        )


MAXIMUM_TOTAL_READ_SIZE = 100000
TRUNCATION_MESSAGE = '[... truncated for display ...]'


def extract_file_to_stdout(config, repository, archive_name, file_path):
    '''
    Given a configuration dict, a repository dict, an archive name in that repository, and a file
    path in that archive, start extracting the file to standard output, and return the Borg process.
    The caller is responsible for reading both its stdout and stderr.
    '''
    local_path = config.get('local_path', 'borg')

    return borgmatic.borg.extract.extract_archive(
        dry_run=False,
        repository=repository['path'],
        archive=archive_name,
        paths=(file_path,),
        config=config,
        local_borg_version=borgmatic.borg.version.local_borg_version(config, local_path),
        global_arguments=argparse.Namespace(),
        local_path=local_path,
        remote_path=config.get('remote_path'),
        destination_path=None,
        strip_components=None,
        extract_to_stdout=True,
    )


def get_archive_file_content(config, repository, archive_name, file_path):
    '''
    Given a configuration dict, a repository dict, an archive name in that repository, and a file
    path in that archive, return the file's contents or None if the file can't be loaded, e.g.
    because it's binary or can't be decoded.

    If the file is too large, then truncate the returned content.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info(f'Getting archive content of file {file_path}')
        local_path = config.get('local_path', 'borg')
        extract_process = extract_file_to_stdout(config, repository, archive_name, file_path)

        chunks = []
        read_bytes_count = 0
        terminated = False

        # Capture stdout while logging stderr.
        with borgmatic.logger.Log_prefix(None):  # Log command output without any prefix.
            for chunk in borgmatic.execute.log_outputs(
                processes=(extract_process,),
                exclude_stdouts=(),
                output_log_level=None,
                borg_local_path=local_path,
                borg_exit_codes=config.get('borg_exit_codes'),
                output_raw_bytes=True,
            ):
                read_bytes_count += len(chunk)
                chunks.append(chunk)

                # If we've read our fill of bytes, kill the extract process so we don't have to
                # drain and read the entire file from it.
                if not terminated and read_bytes_count >= MAXIMUM_TOTAL_READ_SIZE:
                    logger.debug(
                        "Terminating Borg extract process, since we've read our fill of file preview data"
                    )
                    extract_process.terminate()
                    terminated = True

        content = b''.join(chunks)

        if binaryornot.helpers.is_binary_string(content):
            return None

        try:
            return (
                content.decode()
                if len(content) < MAXIMUM_TOTAL_READ_SIZE
                else f'{content.decode()}\n{TRUNCATION_MESSAGE}'
            )
        except UnicodeDecodeError:
            return None


# How much of a command's output to keep, and the shell to run the command with.
MAXIMUM_COMMAND_OUTPUT_SIZE = 1000000
COMMAND_OUTPUT_CHUNK_SIZE = 65536
PIPE_SHELL = '/bin/sh'

# What Borg's error says when the command that its output is piped to stops reading early, as "head"
# does. Borg 1 and 2 both fail with a traceback containing this.
BROKEN_PIPE_TEXT = 'BrokenPipeError'

# The result of piping a file to a command: its combined stdout and stderr as bytes, its exit code
# (negative if a signal stopped it), and whether its output was cut off.
Command_result = collections.namedtuple('Command_result', ('output', 'exit_code', 'truncated'))


def stop_processes(extract_process, command_process):
    '''
    Given a Borg extract process and the process of a command reading from it, stop both. Signal the
    command's whole process group, so that every command in a pipeline like "jq . | head" stops too.
    Ignore an error signalling it, e.g. because it has already exited.
    '''
    if extract_process.poll() is None:
        extract_process.terminate()

    with contextlib.suppress(OSError):
        os.killpg(command_process.pid, signal.SIGTERM)


def pipe_archive_file(config, repository, archive_name, file_path, command, on_start=None):
    '''
    Given a configuration dict, a repository dict, an archive name in that repository, a file path
    in that archive, a shell command, and an optional function to call with the extract and command
    processes once they've started, stream the whole file into the command, and return its output
    as a Command_result.

    Run the command in a new session, so that it can't take over the terminal that the app runs in
    and can be stopped along with any commands it starts. Read its output in a separate thread,
    so that Borg's stderr can be logged at the same time. If there's too much output, cut it off
    and stop both processes.

    Ignore Borg failing because the command stopped reading, or because it was stopped here.
    Otherwise raise subprocess.CalledProcessError if Borg fails, or OSError if the command can't
    be started.
    '''
    with borgmatic.logger.Log_prefix(repository.get('label', repository['path'])):
        logger.info(f'Piping file {file_path} to command: {command}')
        local_path = config.get('local_path', 'borg')
        extract_process = extract_file_to_stdout(config, repository, archive_name, file_path)

        try:
            command_process = subprocess.Popen(  # noqa: S603
                (PIPE_SHELL, '-c', command),
                stdin=extract_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError:
            extract_process.terminate()
            raise

        # Only the command should hold the read end of the pipe, so Borg finds out if it exits.
        extract_process.stdout.close()

        if on_start:
            on_start(extract_process, command_process)

        chunks = []
        truncated = False

        def read_output():
            nonlocal truncated
            read_bytes_count = 0

            while chunk := command_process.stdout.read(COMMAND_OUTPUT_CHUNK_SIZE):
                chunks.append(chunk)
                read_bytes_count += len(chunk)

                if read_bytes_count > MAXIMUM_COMMAND_OUTPUT_SIZE:
                    truncated = True
                    stop_processes(extract_process, command_process)
                    break

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()

        try:
            for _ in borgmatic.execute.log_outputs(
                processes=(extract_process,),
                exclude_stdouts=(extract_process.stdout,),
                output_log_level=None,
                borg_local_path=local_path,
                borg_exit_codes=config.get('borg_exit_codes'),
            ):
                pass
        except subprocess.CalledProcessError as error:
            # Cutting off the output flags it before stopping Borg, so there's no need to wait for
            # the reader here. That could take forever with a command that doesn't read its input.
            if not truncated and BROKEN_PIPE_TEXT not in (error.output or ''):
                stop_processes(extract_process, command_process)
                reader.join()
                raise

            logger.debug(f'Ignoring Borg failing after the command stopped reading: {error}')

        reader.join()
        command_process.wait()

        return Command_result(
            b''.join(chunks)[:MAXIMUM_COMMAND_OUTPUT_SIZE], command_process.returncode, truncated
        )
