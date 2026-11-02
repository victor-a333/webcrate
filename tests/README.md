Certificate checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
docker build -t webcrate-certificates-check:local src/utils-docker
python3 tests/docker_certificates.py
```

The Docker test uses a temporary network and volume, the utilities image, and
`ace5040/webcrate-nginx:stable`. It starts an isolated fixture application,
executes service initialization and project/redirect certificate entry points,
verifies trusted HTTPS and redirect destinations through non-root Nginx, and
checks scheduled replacement of a near-expiry local certificate. It removes its
containers, network, and volume afterward. It does not start the full admin or
Grafana applications or request public ACME certificates.

Unit tests cover ACME command failures, redirect-only renewal, webroot repair,
account email updates without certificate deletion, and Nginx include rollback.

Certificate creation and scheduled renewal share `certificates.py`. Nginx TLS
rendering and deployment share `nginx_tls.py`. Existing certificate names and
paths are preserved. Renewal runs every twelve hours. Existing saved ACME
lineages are renewed regardless of which YAML file originally defined them.

`./bin/webcrate start --services-only` generates service configuration and runs
service initialization/startup, skipping project and redirect configuration
and startup scripts. Existing project/redirect configuration is retained.
Shared initialization, Nginx, databases, utilities, and certificate storage
remain shared; service TLS changes may reload the Nginx serving existing sites.
This flag does not recreate existing service containers or apply to `restart`.
