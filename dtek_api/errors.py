# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

class DtekError(Exception):
    code = "upstream_unavailable"
    http_status = 503
    public_message = "The DTEK schedule source is temporarily unavailable."


class DtekBlockedError(DtekError):
    code = "upstream_blocked"
    http_status = 502
    public_message = "The DTEK schedule source rejected the request."


class DtekRateLimitError(DtekError):
    code = "upstream_rate_limited"
    public_message = "The DTEK schedule source is rate limiting requests."


class DtekProtocolError(DtekError):
    code = "upstream_protocol_error"
    http_status = 502
    public_message = "The DTEK response format was not recognized."


class HouseNotFoundError(Exception):
    pass
