#!/bin/bash
#
# Make throwaway Borg installations, repositories and borgmatic configurations for smoke testing
# borgmatic-browse against real Borg. Given a directory that's either new or was made by this script,
# replace its repositories and configurations, and keep its Borg installations to save time.

set -euo pipefail

BORG_1_VERSION=1.4.5
BORG_2_VERSION=2.0.0b25
PASSPHRASE=smoke

if [ $# -ne 1 ]; then
    echo "Usage: $0 DIRECTORY" >&2
    exit 2
fi

target=$(realpath -m "$1")

if [ -e "$target" ] && [ ! -e "$target/.borgmatic-browse-smoke" ]; then
    echo "$target already exists and wasn't made by this script, so leaving it alone" >&2
    exit 1
fi

mkdir -p "$target"
touch "$target/.borgmatic-browse-smoke"
cd "$target"

install_borg() {
    if [ ! -x "$1/bin/borg" ]; then
        uv venv -q --python 3.13 "$1"
        VIRTUAL_ENV="$PWD/$1" uv pip install -q "borgbackup==$2"
    fi
}

install_borg borg1 "$BORG_1_VERSION"
install_borg borg2 "$BORG_2_VERSION"

rm -rf base1 base2 repo1.borg repo2.borg empty.borg late.borg late.stash source scripts configs \
    log-borg.log
mkdir -p base1 base2 scripts configs

# A tree with varied sizes, times and types, for sorting and display.
mkdir -p source/tree/zdir/deep source/tree/adir source/implicit/a/b
head -c 5000 /dev/zero > source/tree/zdir/big.bin
head -c 900 /dev/zero > source/tree/zdir/deep/mid.bin
head -c 10 /dev/zero > source/tree/adir/small.bin
head -c 300 /dev/zero > source/tree/old.txt
head -c 3000 /dev/zero > source/tree/Newer.txt
printf 'print("hello smoke")\n' > source/tree/hello.py
head -c 2000 /dev/urandom > source/tree/blob.bin
python3 -c "print('LONGSTART ' + 'word ' * 100 + 'LONGEND')" > source/tree/long.txt
python3 -c "print('HUGESTART ' + 'word ' * 1000 + 'HUGEEND')" > source/tree/huge.txt
ln -s hello.py source/tree/lnk
echo x > source/implicit/a/b/c.txt
touch -d '2020-01-01 10:00' source/tree/old.txt source/tree/adir/small.bin source/tree/adir
touch -d '2026-03-03 03:03' source/tree/Newer.txt source/tree/zdir/big.bin
touch -h -d '2022-02-02 02:02' source/tree/lnk
touch -d '2025-05-05 05:05' source/tree/zdir/deep/mid.bin source/tree/zdir/deep source/tree/zdir

hostname=$(hostname)

# Borg 1: One archive that matches borgmatic's default archive filter, one that doesn't, and one that
# names a nested file directly, so that the file's parent directories have no entries of their own.
export BORG_PASSPHRASE=$PASSPHRASE
export BORG_BASE_DIR="$target/base1"
borg1/bin/borg init --encryption=repokey repo1.borg 2> /dev/null
(
    cd source
    "$target/borg1/bin/borg" create "$target/repo1.borg::other-1" tree
    sleep 1
    "$target/borg1/bin/borg" create "$target/repo1.borg::$hostname-1" tree
    sleep 1
    "$target/borg1/bin/borg" create "$target/repo1.borg::$hostname-implicit" implicit/a/b/c.txt
)

# A repository with no archives at all.
borg1/bin/borg init --encryption=repokey empty.borg 2> /dev/null

# A repository moved out of place, so that a test can move it back while the app is running, like
# plugging in a disk.
borg1/bin/borg init --encryption=repokey late.borg 2> /dev/null
(
    cd source
    "$target/borg1/bin/borg" create "$target/late.borg::$hostname-late" tree
)
mv late.borg late.stash

# Borg 2: Two identically named archives with different contents.
export BORG_BASE_DIR="$target/base2"
export BORG_REPO="$target/repo2.borg"
borg2/bin/borg repo-create --encryption=aes256-ocb 2> /dev/null
(
    cd source
    "$target/borg2/bin/borg" create dup tree
    sleep 1
    echo more >> tree/hello.py
    "$target/borg2/bin/borg" create dup tree
)
unset BORG_PASSPHRASE BORG_BASE_DIR BORG_REPO

# Fake Borg commands for simulating failures and slowness.
cat > scripts/slow-borg <<EOF
#!/bin/sh
case " \$* " in *" --version "*) exec "$target/borg1/bin/borg" "\$@";; esac
sleep 60
exec "$target/borg1/bin/borg" "\$@"
EOF
cat > scripts/fail-extract-borg <<EOF
#!/bin/sh
case " \$* " in *" extract "*) echo "simulated extract failure" >&2; exit 2;; esac
exec "$target/borg1/bin/borg" "\$@"
EOF
cat > scripts/fail-list-borg <<EOF
#!/bin/sh
case " \$* " in *"::"*) echo "simulated listing failure" >&2; exit 2;; esac
exec "$target/borg1/bin/borg" "\$@"
EOF
cat > scripts/log-borg <<EOF
#!/bin/sh
case " \$* " in *" --version "*) ;; *) echo "\$*" >> "$target/log-borg.log";; esac
exec "$target/borg1/bin/borg" "\$@"
EOF
chmod +x scripts/*

# Given a configuration name and a label, then a repository and any further lines, write a
# configuration.
write_config() {
    {
        printf 'repositories:\n  - path: %s\n    label: %s\n' "$3" "$2"
        shift 3
        printf '%s\n' "$@"
    } > "configs/$name.yaml"
}

name=borg1 write_config borg1 borg1 "$target/repo1.borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/borg1/bin/borg"
name=borg1-all write_config borg1-all borg1all "$target/repo1.borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/borg1/bin/borg" "match_archives: '*'"
name=borg2 write_config borg2 borg2 "$target/repo2.borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/borg2/bin/borg" "match_archives: '*'"
name=markup-path write_config markup-path markuppath "$target/x[\$var].borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/borg1/bin/borg"
name=empty-repo write_config empty-repo emptyrepo "$target/empty.borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/borg1/bin/borg"
name=late-repo write_config late-repo laterepo "$target/late.borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/borg1/bin/borg"
name=log write_config log logrepo "$target/repo1.borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/scripts/log-borg"
name=missing-repo write_config missing-repo missingrepo "$target/nope.borg" \
    "encryption_passphrase: $PASSPHRASE" "local_path: $target/borg1/bin/borg"
name=wrong-passphrase write_config wrong-passphrase wrongpass "$target/repo1.borg" \
    "encryption_passphrase: wrong" "local_path: $target/borg1/bin/borg"
name=no-passphrase write_config no-passphrase nopass "$target/repo1.borg" \
    "local_path: $target/borg1/bin/borg"
name=no-borg write_config no-borg noborg "$target/repo1.borg" "local_path: $target/does-not-exist"
for script in slow fail-extract fail-list; do
    name=$script write_config "$script" "$script" "$target/repo1.borg" \
        "encryption_passphrase: $PASSPHRASE" "local_path: $target/scripts/$script-borg" \
        "match_archives: '*'"
done

cat > environment.sh <<EOF
# Source this before running Borg by hand: BORG_BASE_DIR picks the fixtures' Borg 1 security and cache
# data. Use base2 for the Borg 2 repository.
export BORG_BASE_DIR="$target/base1"
export BORG_PASSPHRASE=$PASSPHRASE
EOF

echo "Made smoke test fixtures in $target"
