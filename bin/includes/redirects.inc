if [[ -d ./var/meta/redirects && -n "$(ls -A ./var/meta/redirects)" ]]; then
  for redirectDump in ./var/meta/redirects/*.jsonDump
  do
    redirect_name=$(basename "$redirectDump" .jsonDump)
    redirect_name=${redirect_name#redirect-}
    writeLog "Starting redirect $redirect_name"
    docker run --rm --env-file=$(pwd)/.env \
      --name webcrate-utils-docker-$redirect_name \
      -e WEBCRATE_UID=$uid \
      -e WEBCRATE_GID=$gid \
      -e WEBCRATE_PWD=$(pwd) \
      -v $DOCKER_SOCKET:/var/run/docker.sock \
      -v $(pwd):/webcrate-readonly:ro \
      -v $(pwd)/redirects.yml:/webcrate/redirects.yml:ro \
      -v $(pwd)/var/log:/webcrate/log \
      -v $(pwd)/var/meta:/webcrate/meta \
      -v $(pwd)/var/nginx:/webcrate/nginx \
      -v $(pwd)/var/secrets:/webcrate/secrets \
      -v $(pwd)/var/letsencrypt:/webcrate/letsencrypt \
      -v $(pwd)/var/letsencrypt-meta:/webcrate/letsencrypt-meta \
      -v $(pwd)/var/openssl:/webcrate/openssl \
      ace5040/webcrate-utils-docker:stable /redirect-start.py $redirect_name
    writeLog "Redirect $redirect_name started"
  done
fi
