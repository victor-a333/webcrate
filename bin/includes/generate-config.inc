SCRIPT=`realpath $0`
SCRIPTPATH=`dirname $SCRIPT`
cd $SCRIPTPATH/..
source .env
source ./bin/includes/init.inc
uid=$(id -u);
gid=$(id -u);

if [ "$WEBCRATE_EXTERNAL_DNS_IP" != "" ]; then
  writeLog "Generate resolv.conf for dnsmasq"
  rm -f ./var/dnsmasq/resolv.conf
  touch ./var/dnsmasq/resolv.conf
  for IP_ADDR in ${WEBCRATE_SECONDARY_INSTANCES[@]}
  do
    echo "nameserver $IP_ADDR" >> ./var/dnsmasq/resolv.conf
  done
  echo "nameserver $WEBCRATE_EXTERNAL_DNS_IP" >> ./var/dnsmasq/resolv.conf
fi

# Detect once on the host; generation containers do not need Docker access.
NGINX_VERSION=unknown
if ! NGINX_VERSION_OUTPUT=$(docker exec "${WEBCRATE_NGINX_CONTAINER:-webcrate-nginx}" nginx -v 2>&1); then
  NGINX_IMAGE=$(docker inspect --format '{{.Image}}' "${WEBCRATE_NGINX_CONTAINER:-webcrate-nginx}" 2>/dev/null) \
    || NGINX_IMAGE=ace5040/webcrate-nginx:stable
  NGINX_VERSION_OUTPUT=$(docker run --rm --network none --entrypoint nginx "$NGINX_IMAGE" -v 2>&1) \
    || NGINX_VERSION_OUTPUT=''
fi
if [[ "$NGINX_VERSION_OUTPUT" =~ nginx/([0-9]+\.[0-9]+\.[0-9]+) ]]; then
  NGINX_VERSION="${BASH_REMATCH[1]}"
  writeLog "Nginx version for config generation: $NGINX_VERSION"
else
  writeLog "Cannot detect Nginx version; using compatible HTTP/2 syntax"
fi

writeLog "Parse projects started"
docker run --rm --env-file=$(pwd)/.env --entrypoint /parse-projects.py --name webcrate-docker-parse-projects \
  -e WEBCRATE_UID=$uid \
  -e WEBCRATE_GID=$gid \
  $PROJECTS_VOLUMES \
  -e WEBCRATE_PROJECTS_FOLDERS=$( IFS=:; printf '%s' "${WEBCRATE_PROJECTS_FOLDERS[*]}" ) \
  -e WEBCRATE_PWD=$(pwd) \
  -e WEBCRATE_NGINX_VERSION="$NGINX_VERSION" \
  -v $(pwd)/projects.yml:/webcrate/projects.yml:ro \
  -v $(pwd)/var/log:/webcrate/log \
  -v $(pwd)/var/meta:/webcrate/meta \
  -v $(pwd)/var/crontabs:/webcrate/crontabs \
  -v $(pwd)/config/nginx-templates:/webcrate/nginx-templates:ro \
  -v $(pwd)/config/php-pool-templates:/webcrate/custom_templates:ro \
  -v $(pwd)/var/letsencrypt:/webcrate/letsencrypt:ro \
  -v $(pwd)/var/openssl:/webcrate/openssl:ro \
  -v $(pwd)/var/dnsmasq:/webcrate/dnsmasq \
  -v $(pwd)/var/nginx:/webcrate/nginx \
  -v $(pwd)/var/php_pools:/webcrate/php_pools \
  ace5040/webcrate-utils-docker:stable
writeLog "Parse projects ended"

writeLog "Parse redirects started"
docker run --rm --env-file=$(pwd)/.env --entrypoint /parse-redirects.py --name webcrate-docker-parse-redirects \
  -e WEBCRATE_UID=$uid \
  -e WEBCRATE_GID=$gid \
  -e WEBCRATE_PWD=$(pwd) \
  -e WEBCRATE_NGINX_VERSION="$NGINX_VERSION" \
  -v $(pwd)/redirects.yml:/webcrate/redirects.yml:ro \
  -v $(pwd)/var/log:/webcrate/log \
  -v $(pwd)/var/meta:/webcrate/meta \
  -v $(pwd)/config/nginx-templates:/webcrate/nginx-templates:ro \
  -v $(pwd)/var/letsencrypt:/webcrate/letsencrypt:ro \
  -v $(pwd)/var/openssl:/webcrate/openssl:ro \
  -v $(pwd)/var/dnsmasq:/webcrate/dnsmasq \
  -v $(pwd)/var/nginx:/webcrate/nginx \
  ace5040/webcrate-utils-docker:stable
writeLog "Parse redirects ended"

writeLog "Parse services started"
docker run --rm --env-file=$(pwd)/.env --entrypoint /parse-services.py --name webcrate-docker-parse-services \
  -e WEBCRATE_PWD=$(pwd) \
  -e WEBCRATE_NGINX_VERSION="$NGINX_VERSION" \
  -v $(pwd)/services.yml:/webcrate/services.yml:ro \
  -v $(pwd)/config/nginx-templates:/webcrate/nginx-templates:ro \
  -v $(pwd)/var/letsencrypt:/webcrate/letsencrypt:ro \
  -v $(pwd)/var/openssl:/webcrate/openssl:ro \
  -v $(pwd)/var/dnsmasq:/webcrate/dnsmasq \
  -v $(pwd)/var/nginx:/webcrate/nginx \
  ace5040/webcrate-utils-docker:stable

writeLog "Parse services ended"
