# FTP and FTPS

The image uses Debian Trixie slim, distribution security updates, and only the
ProFTPD listing, transfer, and TLS modules. Copy, execution, SFTP, and directory
`.ftpaccess` overrides are disabled. All logins use `/etc/ftp.passwd`; system
accounts cannot authenticate. Startup and synchronization never invoke a shell
with configuration values or recursively change existing file ownership.

Both plain FTP and explicit FTPS use port 21; passive transfers use ports
50000–60000. FTPS supports TLS 1.2 and 1.3 and requires session reuse on data
connections. Plain FTP remains available as requested and sends credentials
and data without encryption. Implicit FTPS on port 990 is not configured.

## Certificates

The launcher mounts `var/ftp-tls` at `/webcrate/tls`. Supply `server.crt` (PEM
certificate/chain) and an unencrypted `server.key` (PEM private key, mode 0600).
Restart FTP after certificate replacement. If neither file exists, startup
creates a persistent self-signed certificate valid for 365 days. Clients must
trust that certificate explicitly, or use a certificate issued for the server's
hostname. An incomplete/invalid pair causes startup to fail; it is not replaced.

## Accounts and updates

The project roots are mounted at `/projects`, `/projects2`, `/projects3`, etc.
A project's zero-based `volume` selects its root (omitted/null means 0).
Its primary account uses `<root>/<project>`. Additional `ftps` accounts have
homes relative to that project directory. `DefaultRoot ~` confines sessions.
Account names must be unique across all projects and accounts.

Every configured project retains its FTP accounts regardless of its `active`
status. Disabling a website does not disable file access. Additional FTP accounts
have no enabled/disabled field or checkbox. Removing an account or project removes
its login from the next complete account set. Password changes use the same path.
Existing project files are preserved.

Saving in admin publishes `projects.yml`; pressing
Apply runs `project-config.py <name> reload` inside docker-utils. Only that reload
mode synchronizes FTP. During `webcrate start`, `parse-projects.py` configures
projects without the reload argument, then synchronizes FTP once after the loop.
There is no FTP cron job. If accounts changed, utilities restarts FTP to terminate
existing sessions, including sessions whose access was revoked. Unchanged accounts
do not restart FTP.

Synchronization reads the complete account set in `projects.yml`. Project deletion
publishes the updated YAML and invokes utilities synchronization immediately using
`updateprojects.py --sync-ftp`; no Apply or cron is needed to revoke that project.
Ordinary saves continue to wait for Apply.

The FTP container has no Docker socket, shared metadata/log mounts, or full
`.env` access. Docker orchestration remains in utilities. Invalid names, hashes,
volumes, traversal, and symlink home components fail synchronization without
replacing the account file. Errors are reported by the utilities sync command.

CLI project configuration generation also synchronizes FTP. After manually
editing `projects.yml`, run:

```sh
docker exec webcrate-utils-docker /ftp-sync.py
```

New projects within mounted roots need no new mounts. Changing the root folder
list still requires recreating FTP. Sync skips an absent FTP container during
initial installation; its entrypoint loads accounts when it starts. A stopped
FTP container produces an error rather than silently reporting synchronization.

## Deployment

Rebuild FTP, docker-utils, and admin and recreate those containers to apply these
changes. Preserve existing data volumes. No database migration is required. These repository changes do not
replace running containers automatically.

## Validation

From the repository root in Windows PowerShell:

```powershell
docker.exe build -t webcrate-ftp:trixie-check ./src/ftp
docker.exe build -t webcrate-utils-docker:ftp-check ./src/utils-docker
docker.exe run --rm -v /projects -v /projects2 `
  --mount "type=bind,source=$($PWD.Path)\tests,target=/fixture-tests,readonly" `
  --entrypoint python3 webcrate-ftp:trixie-check /fixture-tests/docker_ftp.py
docker.exe run --rm -v /var/run/docker.sock:/var/run/docker.sock `
  --mount "type=bind,source=$($PWD.Path),target=/repository,readonly" `
  --entrypoint python3 webcrate-utils-docker:ftp-check /repository/tests/docker_ftp_control.py
```

The control fixture requires `ace5040/webcrate-admin:stable` locally. It uses
uniquely named containers and disposable volumes, invokes the admin deletion publisher
and the utilities Apply hook, checks account lifecycle and existing-session
revocation, and removes its fixtures. It does not exercise the browser UI.
The transfer fixture checks FTP/FTPS, home isolation, unsafe configuration,
symlinks, disabled features, and Unix-auth exclusion. Neither fixture tests
external networking, firewall rules, or host bind-mount permissions.
