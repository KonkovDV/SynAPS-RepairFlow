# Laboratory image. The wheels come from the CI wheelhouse, not from an index.
# The base is Debian bookworm. This is not Astra Linux and not RED OS.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /opt/repairflow
COPY requirements-lock.txt pyproject.toml ./
COPY src/repairflow/versions.py src/repairflow/versions.py
COPY tools/verify_lock.py tools/verify_lock.py
COPY wheelhouse wheelhouse

RUN python tools/verify_lock.py --hashed-out /tmp/hashed.txt --git-out /tmp/git.txt \
 && python -m pip install --no-index --find-links wheelhouse --no-cache-dir --require-hashes -r /tmp/hashed.txt \
 && python -m pip install --no-index --no-cache-dir --no-deps wheelhouse/synaps-*.whl \
 && python -m pip install --no-index --no-cache-dir --no-deps wheelhouse/synaps_repairflow-*.whl \
 && rm -rf /tmp/hashed.txt /tmp/git.txt wheelhouse /root/.cache/pip

WORKDIR /tmp
USER nobody
ENTRYPOINT ["repairflow"]
