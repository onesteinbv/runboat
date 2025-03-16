set -ex
unset DOCKER_HOST

# Install tools
apk add curl tar

# Login into ghcr.io
echo $DOCKER_PASSWORD | docker login ghcr.io --username $DOCKER_USER --password-stdin

# Get stuff
curl -sSL https://github.com/${RUNBOAT_GIT_REPO}/tarball/${RUNBOAT_GIT_REF} | tar zxf - --strip-components=1

# Start docker daemon
dockerd --host=unix:///var/run/docker.sock &

until docker info > /dev/null 2>&1; do
  echo "Waiting for Docker daemon to start..."
  sleep 1
done

# Build & push
docker build . --tag $IMAGE_TAG
docker push $IMAGE_TAG
