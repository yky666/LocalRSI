# Development image only. Deploy separately for every member; never mount a Docker socket.
FROM node:22-bookworm-slim AS node
FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && apt-get update \
 && apt-get install -y --no-install-recommends bash git ca-certificates build-essential chromium \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip install --no-cache-dir playwright==1.65.2 \
 && useradd --create-home --uid 10001 agent \
 && mkdir -p /workspace \
 && chown agent:agent /workspace
ENV HOME=/workspace/.home PYTHONUSERBASE=/workspace/.python NPM_CONFIG_CACHE=/workspace/.npm
ENV PATH=/workspace/.python/bin:/usr/local/bin:/usr/bin:/bin
USER 10001:10001
WORKDIR /workspace
CMD ["sleep", "infinity"]
