FROM pgvector/pgvector:pg16

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg lsb-release ca-certificates \
    && curl -sL https://packagecloud.io/timescale/timescaledb/gpgkey | \
       gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg \
    && echo "deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -cs) main" \
       > /etc/apt/sources.list.d/timescaledb.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       timescaledb-2-postgresql-16 \
    && rm -rf /var/lib/apt/lists/*

RUN echo "shared_preload_libraries = 'timescaledb'" >> /usr/share/postgresql/postgresql.conf.sample

USER postgres
