# (C) StackState 2021
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)


def test_endpoint_generation(dynatrace_client):
    urls = ["https://custom.domain.com/e/abc123", "https://custom.domain.com/e/abc123/"]
    paths = ["api/v1/entity/infrastructure/processes", "/api/v1/entity/infrastructure/processes"]
    expected_url = "https://custom.domain.com/e/abc123/api/v1/entity/infrastructure/processes"
    for url in urls:
        for path in paths:
            assert dynatrace_client.get_endpoint(url, path) == expected_url
