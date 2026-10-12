# DTEK Schedule API

An unofficial, lightweight HTTP API for blackout schedule data published by [DTEK Kyiv Regional Networks](https://www.dtek-krem.com.ua/ua/shutdowns). It resolves Ukrainian addresses, returns their outage group, and provides DTEK's confirmed daily schedule and weekly forecast as JSON.

## Data source and limitations

DTEK does not document a public schedule API. This service reads data from the official schedule page and the AJAX requests used by that page. DTEK may change the page, request protocol, or response format; it may also limit or reject automated requests. These changes can interrupt retrieval until the integration is updated.

The address catalog and schedule data are cached in memory. When `/v1/schedule` is requested, the service checks for schedule changes no more often than every five minutes; it does not poll in the background. If an upstream refresh fails, a recent cached result may be returned with `stale: true`.

Published schedules are not live power telemetry. Emergency outages and local faults may differ from the published schedule. Check DTEK's page or official reports when current power status matters.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker, if using the container deployment

## Run with Python

## Clone the repo

```sh
git clone https://github.com/AX1111YT/dtek-schedule-api.git
```

then change directory

```sh
cd dtek-schedule-api
```

then chose the method that fits you:

### Windows PowerShell

- Step 1: Create your local configuration

```powershell
Copy-Item .env.example .env # Edit the .env if you want to tweak the settings.
```

- Step 2: Create a virtual environment, install dependencies, and start the API

```powershell
uv venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
uv run --no-project --env-file .env --python .venv\Scripts\python.exe --module dtek_api
```

### macOS or Linux

- Step 1: Create your local configuration

```bash
cp .env.example .env # Edit the .env if you want to tweak the settings.
```

- Step 2: Create a virtual environment, install dependencies, and start the API

```sh
uv venv
uv pip install --python .venv/bin/python -r requirements.txt
uv run --no-project --env-file .env --python .venv/bin/python --module dtek_api
```

The API listens on `http://127.0.0.1:8000` by default. FastAPI's interactive API reference is available at `http://127.0.0.1:8000/docs` when `DOCS_ENABLED` is true. The health endpoint is `http://127.0.0.1:8000/healthz`.

To allow another device on the local network to connect, set `HOST=0.0.0.0` in `.env`. Configure `API_KEY` as well, and place the service behind an HTTPS reverse proxy if it will be reachable beyond a trusted network.

## Run with Docker

Step 1: Clone the repo

```sh
git clone https://github.com/AX1111YT/dtek-schedule-api.git
```

Step 2: Change directory

```sh
cd dtek-schedule-api
```

Step 3: choose the method that fits you:

### Docker compose (recommended)

```sh
cp .env.example .env # Edit the .env if you want to tweak the settings.
docker compose up -d
```

### Docker run

#### Run a published release

```sh
cp .env.example .env # Edit the .env if you want to tweak the settings.
docker pull ghcr.io/ax1111yt/dtek-schedule-api:latest
docker run --rm --name dtek-schedule-api \
  --env-file .env \
  -e HOST=0.0.0.0 \
  -p 127.0.0.1:8000:8000 \
  ghcr.io/ax1111yt/dtek-schedule-api:latest
```

#### Build from source (for development)

To build the container locally instead of pulling a release:

```sh
docker build -t dtek-schedule-api:local .
docker run --name dtek-schedule-api \
  --env-file .env \
  -e HOST=0.0.0.0 \
  -p 127.0.0.1:8000:8000 \
  dtek-schedule-api:local
```

## API

All endpoints use the `krem` region by default. It is currently the only supported region. Address values must match the Ukrainian names returned by DTEK's address catalog. Use URL-encoded query parameters; `curl --get --data-urlencode` handles this for Cyrillic input.

| Method and path             | Purpose                                                                          |
| --------------------------- | -------------------------------------------------------------------------------- |
| `GET /healthz`              | Process health check; does not contact DTEK.                                     |
| `GET /v1/regions`           | Lists supported regions.                                                         |
| `GET /v1/locations/cities`  | Lists matching cities or settlements. Optional `q` filters by substring.         |
| `GET /v1/locations/streets` | Lists streets for a `city`. Optional `q` filters by substring.                   |
| `GET /v1/locations/houses`  | Lists houses for a `city` and `street`. Optional `q` filters house numbers.      |
| `GET /v1/schedule`          | Returns the address group, any reported outage details, and available schedules. |

### Address lookup examples

Use the exact city and street values returned by the preceding lookup. The values below are examples; replace them with the address names selected from DTEK's catalog.

```sh
curl --get 'http://127.0.0.1:8000/v1/locations/cities' \
  --data-urlencode 'region=krem' \
  --data-urlencode 'q=Українка'

curl --get 'http://127.0.0.1:8000/v1/locations/streets' \
  --data-urlencode 'region=krem' \
  --data-urlencode 'city=м. Українка' \
  --data-urlencode 'q=Юності'

curl --get 'http://127.0.0.1:8000/v1/locations/houses' \
  --data-urlencode 'region=krem' \
  --data-urlencode 'city=м. Українка' \
  --data-urlencode 'street=вул. Юності'
```

### Get a schedule

The schedule endpoint requires `city`, `street`, and `house_number`. `region` is optional and defaults to `krem`.

```sh
curl --get 'http://127.0.0.1:8000/v1/schedule' \
  --data-urlencode 'region=krem' \
  --data-urlencode 'city=м. Українка' \
  --data-urlencode 'street=вул. Юності' \
  --data-urlencode 'house_number=10'
```

If `API_KEY` is configured, add `-H 'Authorization: Bearer <key>'` to each `/v1/*` request.

### Response fields

`GET /v1/locations/cities`, `/streets`, and `/houses` return the selected region and address values, the matching results, and a `stale` flag. House results also include each house's group list, whether it belongs to multiple groups, and whether it is excluded from the published schedule.

The schedule response has this structure:

| Field                       | Meaning                                                                                                      |
| --------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `source`                    | Data provider; currently `dtek`.                                                                             |
| `timezone`                  | Time zone used for schedule dates and times: `Europe/Kyiv`.                                                  |
| `fetched_at`                | UTC timestamp for the oldest data component in the response.                                                 |
| `age_seconds`               | Age of that data in seconds.                                                                                 |
| `stale`                     | Whether the response contains cached data after a failed upstream refresh.                                   |
| `address`                   | The requested address, assigned groups, and schedule status.                                                 |
| `current_outage`            | Outage details reported by DTEK for the address, if any. This is not a live power sensor.                    |
| `schedules.weekly_forecast` | Forecast object with `active` and a `days` list, or `null` if unavailable.                                   |
| `schedules.confirmed`       | Confirmed schedule object with DTEK's `source_updated_at` value and a `days` list, or `null` if unavailable. |

The `address` object contains `region`, `city`, `street`, `house_number`, `groups`, `group`, and `status`. `groups` is always a list. `group` is populated only when one schedule group can be identified. `status` is one of:

- `scheduled`: one group was identified.
- `excluded`: DTEK did not assign the address to a published outage group.
- `multiple_groups`: DTEK assigned the address to more than one group, so the API does not guess which schedule applies.

Each schedule day contains its date or weekday and a `slots` list. A slot contains:

```json
{
  "index": 1,
  "start": "00:00",
  "end": "01:00",
  "status": "yes",
  "source_status": null
}
```

Slot boundaries come from DTEK and may change. Use `start` and `end` rather than assuming a fixed interval. `source_status` is `null` for recognized statuses; if DTEK adds a new status, the API returns `status: "unknown"` and preserves the original value in `source_status`.

The recognized `status` values preserve DTEK's schedule legend:

| Status               | Meaning                                                             |
| -------------------- | ------------------------------------------------------------------- |
| `yes`                | Power is scheduled to be on.                                        |
| `no`                 | Power is scheduled to be off.                                       |
| `maybe`              | An outage is possible.                                              |
| `first` / `second`   | Power will be off during the first / second 30 minutes of the slot. |
| `mfirst` / `msecond` | Power may be off during the first / second 30 minutes of the slot.  |
| `unknown`            | Unrecognized upstream status; inspect `source_status`.              |

### Authentication and errors

When `API_KEY` is set, every `/v1/*` endpoint requires an `Authorization: Bearer <key>` header. `/healthz` is always public. API key comparison is performed without a regular string equality check.

Typical errors include:

| HTTP status | Meaning                                                         |
| ----------- | --------------------------------------------------------------- |
| `401`       | API key is missing or invalid.                                  |
| `429`       | The configured API rate limit was exceeded.                     |
| `404`       | Unsupported region or house not found on the specified street.  |
| `422`       | A required query parameter is missing or invalid.               |
| `502`       | DTEK rejected the request or returned an unrecognized response. |
| `503`       | DTEK is unavailable or rejected an upstream request.            |

Upstream errors use a JSON body with `error` and `message` fields. Rate-limit, validation, and not-found responses use a JSON `detail` field.

## Configuration

Configuration can be set in the root `.env` file or provided through the process environment. The committed `.env.example` lists every supported setting and its default. Copy it to `.env` and edit the values for your deployment. `uv run --env-file .env` loads the file for Python runs. `.env` is ignored by Git and excluded from the Docker build context; pass it to Docker at runtime with `--env-file .env`. Environment variables set outside the file take precedence.

| Variable                       | Default     | Description                                                                     |
| ------------------------------ | ----------- | ------------------------------------------------------------------------------- |
| `HOST`                         | `127.0.0.1` | Address to bind. The Docker image sets this to `0.0.0.0` inside the container.  |
| `PORT`                         | `8000`      | HTTP port.                                                                      |
| `FORWARDED_ALLOW_IPS`          | `127.0.0.1` | Proxy IPs or CIDRs trusted to set `X-Forwarded-For`.                            |
| `API_KEY`                      | unset       | Optional bearer token required for `/v1/*`.                                     |
| `RATE_LIMIT_ENABLED`           | `true`      | Enables a shared per-IP limit across `/v1/*` and `/healthz`.                    |
| `RATE_LIMIT`                   | `30/minute` | SlowAPI limit applied when rate limiting is enabled.                            |
| `DOCS_ENABLED`                 | `false`     | Exposes `/docs` and `/openapi.json`; set false to disable both.                 |
| `UPSTREAM_TIMEOUT_SECONDS`     | `15`        | Timeout for a request to DTEK.                                                  |
| `SCHEDULE_CACHE_TTL_SECONDS`   | `600`       | How long a schedule response remains fresh in memory.                           |
| `SCHEDULE_CACHE_STALE_SECONDS` | `3600`      | Additional time a cached schedule may be served after a refresh failure.        |
| `LOCATION_CACHE_TTL_SECONDS`   | `3600`      | How long location catalog data remains fresh in memory.                         |
| `LOCATION_CACHE_STALE_SECONDS` | `86400`     | Additional time a cached location result may be served after a refresh failure. |
| `CACHE_MAX_ENTRIES`            | `64`        | Maximum number of cached entries per process.                                   |

`API_KEY` is optional for a local-only service. Set it to a long random value before exposing the API to other devices. When set, it is required on every `/v1/*` request.

Rate limits use the caller's remote IP and in-memory storage. The shared budget covers `/v1/*` and `/healthz`. Counters reset on restart and are separate per worker; the Docker image runs one worker. For a reverse proxy, set `FORWARDED_ALLOW_IPS` to its source IP or network, such as `172.20.0.0/16` for a Docker network. Uvicorn only trusts forwarded headers from those addresses; avoid `*` unless every client that can reach the API is trusted.

The response cache is also in memory only. Restarting the process clears it. Each worker maintains a separate cache, so run one worker unless you are comfortable with independent per-worker caches.

## Project layout

```text
dtek_api/
├── cache.py       # Bounded asynchronous TTL cache with stale fallback
├── dtek_client.py # DTEK page discovery, session, and AJAX requests
├── errors.py      # Upstream and address error types
├── main.py        # FastAPI app, lifecycle, auth, and server entry point
├── models.py      # Validated response models
├── rate_limit.py  # Shared SlowAPI limiter
├── routes.py      # HTTP endpoints and query validation
├── service.py     # Address resolution and schedule normalization
└── settings.py    # Environment-based configuration
```

## Contributing

Contributions and bug reports are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for project guidance and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

## License

Copyright © 2026 AX1111YT. The project software is licensed under the [Apache License, Version 2.0](LICENSE). The license applies to this project's code; it does not grant rights to DTEK's website, schedule data, or trademarks.
