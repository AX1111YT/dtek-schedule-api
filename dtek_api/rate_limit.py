# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

from slowapi import Limiter
from slowapi.util import get_remote_address

from .settings import settings


limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
)
