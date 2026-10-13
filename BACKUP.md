# Webcrate backup and restore

Webcrate can store backups with Duplicity or Borg. The backend is selected in
`.env`:

```dotenv
WEBCRATE_BACKUP_BACKEND=duplicity
```

or:

```dotenv
WEBCRATE_BACKUP_BACKEND=borg
```

The default is `duplicity`. Supported values are `duplicity` and `borg`.

`WEBCRATE_BACKUP_URIS` contains one or more backup destinations. Local backups
normally use the directory mounted at `/webcrate/backup`:

```dotenv
WEBCRATE_BACKUP_ABSOLUTE_PATH=/home/web/webcrate/var/backup
WEBCRATE_BACKUP_URIS=( file:///webcrate/backup )
```

Duplicity supports the configured `ftp://` destinations. Borg skips `ftp://`
destinations because Borg does not support FTP repositories. Borg local and SSH
repositories can be used, for example:

```dotenv
WEBCRATE_BACKUP_URIS=( file:///webcrate/backup ssh://backup@example.org/./webcrate )
```

> Borg repositories are currently initialized with `--encryption=none`. Use a
> transport and storage location appropriate for the sensitivity of the data.

## Hetzner Storage Box with Borg

In the Hetzner Console, enable **SSH Support** for the Storage Box. Also enable
**External Reachability** when Webcrate runs outside the Hetzner network. Borg
uses Hetzner's extended SSH service on port 23.

Create a dedicated SSH key on the Webcrate host:

```bash
mkdir -p var/ssh
ssh-keygen -t ed25519 -f var/ssh/private-key -N ""
```

Install the public key on the Storage Box, replacing `uXXXXX` with the Storage
Box account name:

```bash
cat var/ssh/private-key.pub \
  | ssh -p 23 uXXXXX@uXXXXX.your-storagebox.de install-ssh-key
```

Configure `.env` to use the local destination and the Storage Box together:

```dotenv
WEBCRATE_BACKUP_BACKEND=borg
WEBCRATE_BACKUP_URIS=( file:///webcrate/backup ssh://uXXXXX@uXXXXX.your-storagebox.de:23/./webcrate )
WEBCRATE_BORG_SSH_KEY=private-key
```

`WEBCRATE_BORG_SSH_KEY` is only the private key filename from `var/ssh`, not a
path or an SSH command. The utilities image sets `BORG_RSH=/borg-ssh.sh`; this
wrapper selects the configured key and enables batch mode and host-key
acceptance. The image also selects Hetzner's `borg-1.4` remote executable.

To store backups only on the Storage Box, omit the local URI:

```dotenv
WEBCRATE_BACKUP_URIS=( ssh://uXXXXX@uXXXXX.your-storagebox.de:23/./webcrate )
```

Recreate the utilities container so that it receives the new environment:

```bash
./bin/webcrate restart
```

Test SSH access from the utilities container:

```bash
docker exec webcrate-utils-docker \
  ssh \
  -i /webcrate-readonly/var/ssh/private-key \
  -p 23 \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=accept-new \
  uXXXXX@uXXXXX.your-storagebox.de \
  pwd
```

Run a backup after the connection succeeds:

```bash
./bin/webcrate backup all all
```

Webcrate appends its backend and logical backup paths to each base URI. For
example, the configuration backup above is stored in
`./webcrate/borg/webcrate/files` on the Storage Box.

> `var/ssh` is included in the Webcrate configuration backup, and Borg
> repositories are currently unencrypted. Use a dedicated Storage Box key and
> do not reuse it for access to other systems.

## Running backups

Run every configured backup:

```bash
./bin/webcrate backup all all
```

Back up one project:

```bash
./bin/webcrate backup example all
```

Back up only a particular data type:

```bash
./bin/webcrate backup example files
./bin/webcrate backup example mysql
./bin/webcrate backup example mysql5
./bin/webcrate backup example postgresql
```

The automatic backup job runs daily at 03:00 from the utilities container.

## Backup layout

Each backend has its own top-level directory under every configured backup URI.
Each logical backup then has its own Duplicity destination or Borg repository:

```text
<backend>/webcrate/files
<backend>/services/<service>/mysql
<backend>/projects/<project>/files
<backend>/projects/<project>/solr-cores
<backend>/projects/<project>/project-mysql
<backend>/projects/<project>/project-mysql5
<backend>/projects/<project>/project-postgresql
```

For example, project files are stored in `borg/projects/example/files` when
using Borg and `duplicity/projects/example/files` when using Duplicity. This
allows both backends to use the same base URI without reading or overwriting
each other's backup data.

Backups created before backend namespacing remain in the legacy paths without
the `<backend>/` prefix. They are not moved or deleted automatically. Use the
legacy path explicitly when restoring one of those backups.

`WEBCRATE_MAX_FULL_BACKUPS` controls the number of retained full Duplicity
backup chains. `WEBCRATE_FULL_BACKUP_DAYS` controls how often Duplicity starts
a new full chain. Borg creates an archive on every run and retains
`WEBCRATE_FULL_BACKUP_DAYS * WEBCRATE_MAX_FULL_BACKUPS` archives. With the
default daily schedule and values `7` and `20`, Borg retains approximately 140
days.

## Before restoring

1. Stop applications that can write to the files or databases being restored.
2. Confirm the backup destination and archive date before changing live data.
3. Restore files into a new staging directory first.
4. Keep the current files and database until the restored data has been
   verified.

The commands below use the running `webcrate-utils-docker` container. Its
`/webcrate/backup` and `/webcrate/backup-tmp` directories are mounted from the
host. Replace `example` and archive names with real values.

Create staging directories when needed:

```bash
mkdir -p var/backup-tmp/restore-webcrate
mkdir -p var/backup-tmp/restore-example
```

## Restore with Borg

### Inspect available archives

List Webcrate configuration archives:

```bash
docker exec webcrate-utils-docker \
  borg list /webcrate/backup/borg/webcrate/files
```

List one project's file and database archives:

```bash
docker exec webcrate-utils-docker \
  borg list /webcrate/backup/borg/projects/example/files

docker exec webcrate-utils-docker \
  borg list /webcrate/backup/borg/projects/example/project-mysql
```

Use the desired archive name from the first column, such as
`files-2026-10-07T03-00-00` or `database-2026-10-07T03-00-00`.

### Restore Webcrate configuration

The Webcrate archive stores paths below `webcrate-readonly`. Extract it into a
staging directory and inspect it:

```bash
docker exec -w /webcrate/backup-tmp/restore-webcrate \
  webcrate-utils-docker \
  borg extract \
  /webcrate/backup/borg/webcrate/files::files-2026-10-07T03-00-00

ls -la var/backup-tmp/restore-webcrate/webcrate-readonly
```

After verification, stop Webcrate and copy the contents of
`var/backup-tmp/restore-webcrate/webcrate-readonly/` into the Webcrate
installation directory. This restores `.env`, configuration, YAML definitions,
certificates, secrets, SSH data, and cron configuration. It does not restore the
Webcrate application source; check out or install the required Webcrate version
separately.

### Restore project files

```bash
docker exec -w /webcrate/backup-tmp/restore-example \
  webcrate-utils-docker \
  borg extract \
  /webcrate/backup/borg/projects/example/files::files-2026-10-07T03-00-00
```

Borg preserves the container path without its leading slash. For a project on
the default volume, restored files will therefore be under:

```text
var/backup-tmp/restore-example/projects/example/<data-folder>/
```

Inspect that directory, stop the project, and copy the restored data folder to
the project's host directory.

### Restore a MySQL database

The SQL dump is stored directly in the Borg archive. It can be streamed into
MySQL without creating a dump file:

```bash
docker exec webcrate-utils-docker \
  borg extract --stdout \
  /webcrate/backup/borg/projects/example/project-mysql::database-2026-10-07T03-00-00 \
  example.sql \
| docker exec -i webcrate-example-mysql \
  sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" example'
```

To restore a MySQL 5 database, use the `project-mysql5` repository and the
corresponding MySQL 5 container.

### Restore a PostgreSQL database

```bash
docker exec webcrate-utils-docker \
  borg extract --stdout \
  /webcrate/backup/borg/projects/example/project-postgresql::database-2026-10-07T03-00-00 \
  example.pgsql \
| docker exec -i webcrate-example-postgresql \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres example'
```

## Restore with Duplicity

Use `collection-status` to inspect available backup chains:

```bash
docker exec webcrate-utils-docker \
  duplicity collection-status \
  file:///webcrate/backup/duplicity/projects/example/files
```

Add `--time` to restore an earlier state. For example:

```bash
--time 2026-10-07T03:00:00
```

### Restore Webcrate configuration

```bash
docker exec webcrate-utils-docker \
  duplicity restore \
  file:///webcrate/backup/duplicity/webcrate/files \
  /webcrate/backup-tmp/restore-webcrate
```

Inspect `var/backup-tmp/restore-webcrate`, stop Webcrate, and then copy the
verified contents into the Webcrate installation directory.

### Restore project files

```bash
docker exec webcrate-utils-docker \
  duplicity restore \
  file:///webcrate/backup/duplicity/projects/example/files \
  /webcrate/backup-tmp/restore-example
```

Inspect the staging directory before copying it to the project's host directory.

### Restore a MySQL database

```bash
mkdir -p var/backup-tmp/restore-example-mysql

docker exec webcrate-utils-docker \
  duplicity restore \
  file:///webcrate/backup/duplicity/projects/example/project-mysql \
  /webcrate/backup-tmp/restore-example-mysql

docker exec webcrate-utils-docker \
  sh -c 'cat /webcrate/backup-tmp/restore-example-mysql/example.sql' \
| docker exec -i webcrate-example-mysql \
  sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" example'
```

### Restore a PostgreSQL database

```bash
mkdir -p var/backup-tmp/restore-example-postgresql

docker exec webcrate-utils-docker \
  duplicity restore \
  file:///webcrate/backup/duplicity/projects/example/project-postgresql \
  /webcrate/backup-tmp/restore-example-postgresql

docker exec webcrate-utils-docker \
  sh -c 'cat /webcrate/backup-tmp/restore-example-postgresql/example.pgsql' \
| docker exec -i webcrate-example-postgresql \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres example'
```

For an FTP Duplicity destination, replace the `file:///webcrate/backup` prefix
with its configured `ftp://...` URI.

## Restore a complete Webcrate system

A complete recovery consists of several logical restores:

1. Check out or install the Webcrate application version used by the backup.
2. Restore `<backend>/webcrate/files` into the installation directory.
3. Review `.env`, especially host paths, volumes, passwords, and backup settings.
4. Start Webcrate so its containers and project directories are recreated.
5. Stop application traffic and database writers.
6. Restore `<backend>/projects/<project>/files` for every project.
7. Restore each configured MySQL, MySQL 5, and PostgreSQL database.
8. Restore `<backend>/projects/<project>/solr-cores` where applicable. Solr index data is
   intentionally excluded and should be rebuilt.
9. Restore `<backend>/services/<service>/mysql` for configured services.
10. Start the system and verify projects, certificates, scheduled jobs, and
    database migrations before returning it to service.

There is intentionally no single destructive “restore everything” command.
Staged restoration makes it possible to verify paths and backup dates before
replacing live files or databases.
