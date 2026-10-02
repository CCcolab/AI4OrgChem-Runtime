FROM --platform=linux/amd64 docker.io/library/python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS build
WORKDIR /opt/runtime
COPY locks locks
COPY scripts/fetch-source.py scripts/fetch-source.py
RUN python scripts/fetch-source.py /opt/ai4orgchem
RUN python -m pip download --only-binary=:all: --require-hashes -r locks/requirements-linux-amd64.txt --dest /wheels

FROM --platform=linux/amd64 docker.io/library/python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
ARG RUNTIME_COMMIT=UNKNOWN
ARG DEPENDENCY_LOCK_SHA256=UNKNOWN
LABEL org.opencontainers.image.title="AI4OrgChem Reproducible Runtime" \
      org.opencontainers.image.revision=$RUNTIME_COMMIT \
      org.opencontainers.image.licenses="Apache-2.0" \
      ai4orgchem.source.commit="28511f3d84fa65707a107cde1e8121a7b4334ecb" \
      ai4orgchem.source.tag="v0.3.2" \
      ai4orgchem.dependency-lock.sha256=$DEPENDENCY_LOCK_SHA256 \
      ai4orgchem.build.platform="linux/amd64"
ENV PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
    AI4ORGCHEM_RUNTIME_COMMIT=$RUNTIME_COMMIT
WORKDIR /opt/runtime
COPY --from=build /opt/ai4orgchem /opt/ai4orgchem
COPY --from=build /wheels /wheels
COPY locks locks
RUN python -m venv /opt/venv \
 && /opt/venv/bin/python -m pip install --no-index --find-links /wheels --require-hashes -r locks/requirements-linux-amd64.txt \
 && /opt/venv/bin/python -m pip check
COPY runtime runtime
COPY container/entrypoint.sh /opt/runtime/entrypoint.sh
COPY LICENSE NOTICE /opt/runtime/
RUN useradd --uid 10001 --create-home runner \
 && mkdir -p /work /locks \
 && chown runner:runner /work /locks \
 && chmod -R a-w /opt/ai4orgchem /opt/runtime /opt/venv \
 && chmod a+rx /opt/runtime/entrypoint.sh
ENV PATH="/opt/venv/bin:$PATH"
USER 10001:10001
ENTRYPOINT ["/opt/runtime/entrypoint.sh"]
CMD ["--help"]
