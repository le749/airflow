#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import pytest

from airflow.models import Connection
from airflow.providers.pagerduty.hooks.pagerduty import PagerdutyHook

DEFAULT_CONN_ID = "pagerduty_default"


@pytest.fixture(autouse=True)
def pagerduty_connections(create_connection_without_db):
    create_connection_without_db(
        Connection(
            conn_id=DEFAULT_CONN_ID,
            conn_type="pagerduty",
            password="token",
            extra='{"routing_key": "integration_key"}',
        )
    )
    create_connection_without_db(
        Connection(
            conn_id="pagerduty_no_extra", conn_type="pagerduty", password="pagerduty_token_without_extra"
        ),
    )


class TestPagerdutyHook:
    def test_get_token_from_password(self, pagerduty_connections):
        hook = PagerdutyHook(pagerduty_conn_id=DEFAULT_CONN_ID)
        assert hook.token == "token", "token initialised."
        assert hook.routing_key == "integration_key"

    def test_without_routing_key_extra(self):
        hook = PagerdutyHook(pagerduty_conn_id="pagerduty_no_extra")
        assert hook.token == "pagerduty_token_without_extra", "token initialised."
        assert hook.routing_key is None, "default routing key skipped."

    def test_token_parameter_override(self):
        hook = PagerdutyHook(token="pagerduty_param_token", pagerduty_conn_id=DEFAULT_CONN_ID)
        assert hook.token == "pagerduty_param_token", "token initialised."

    def test_get_service(self, requests_mock):
        hook = PagerdutyHook(pagerduty_conn_id=DEFAULT_CONN_ID)
        mock_response_body = {
            "id": "PZYX321",
            "name": "Apache Airflow",
            "status": "active",
            "type": "service",
            "summary": "Apache Airflow",
            "self": "https://api.pagerduty.com/services/PZYX321",
        }
        requests_mock.get("https://api.pagerduty.com/services/PZYX321", json={"service": mock_response_body})
        client = hook.client()
        resp = client.rget("/services/PZYX321")
        assert resp == mock_response_body
