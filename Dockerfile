# Laboratory image. The wheels come from the CI wheelhouse, not from an index.
# The base is Debian bookworm. This is not Astra Linux and not RED OS.
# The wheelhouse stays in the build stage. The final image copies the install.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /opt/repairflow
COPY requirements-lock.txt pyproject.toml ./
COPY src/repairflow/versions.py src/repairflow/versions.py
COPY tools/verify_lock.py tools/verify_lock.py
COPY wheelhouse /tmp/wheelhouse

RUN python tools/verify_lock.py --hashed-out /tmp/hashed.txt --git-out /tmp/git.txt \
 && python -m pip install --no-index --find-links /tmp/wheelhouse --no-cache-dir --require-hashes -r /tmp/hashed.txt \
 && python -m pip install --no-index --no-cache-dir --no-deps /tmp/wheelhouse/synaps-*.whl \
 && python -m pip install --no-index --no-cache-dir --no-deps /tmp/wheelhouse/synaps_repairflow-*.whl

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=build /usr/local /usr/local

WORKDIR /tmp
USER nobody
ENTRYPOINT ["repairflow"]
