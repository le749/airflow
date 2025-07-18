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

import os
import warnings
from dataclasses import fields
from unittest import mock

import pytest
from botocore import UNSIGNED
from botocore.config import Config

from airflow.exceptions import AirflowException
from airflow.models import Connection
from airflow.providers.amazon.aws.utils.connection_wrapper import AwsConnectionWrapper, _ConnectionMetadata

pytestmark = pytest.mark.db_test


MOCK_AWS_CONN_ID = "mock-conn-id"
MOCK_CONN_TYPE = "aws"
MOCK_ROLE_ARN = "arn:aws:iam::222222222222:role/awesome-role"


def mock_connection_factory(
    conn_id: str | None = MOCK_AWS_CONN_ID, conn_type: str | None = MOCK_CONN_TYPE, **kwargs
) -> Connection | None:
    if os.environ.get("_AIRFLOW_SKIP_DB_TESTS") == "true":
        return None
    return Connection(conn_id=conn_id, conn_type=conn_type, **kwargs)


class TestsConnectionMetadata:
    @pytest.mark.parametrize("extra", [{"foo": "bar", "spam": "egg"}, '{"foo": "bar", "spam": "egg"}', None])
    def test_compat_with_connection(self, extra):
        """Simple compatibility test with `airflow.models.connection.Connection`."""
        conn_kwargs = {
            "conn_id": MOCK_AWS_CONN_ID,
            "conn_type": "aws",
            "login": "mock-login",
            "password": "mock-password",
            "extra": extra,
            # AwsBaseHook never use this attributes from airflow.models.Connection
            "host": "mock-host",
            "schema": "mock-schema",
            "port": 42,
        }
        conn = Connection(**conn_kwargs)
        conn_meta = _ConnectionMetadata(**conn_kwargs)

        assert conn.conn_id == conn_meta.conn_id
        assert conn.conn_type == conn_meta.conn_type
        assert conn.login == conn_meta.login
        assert conn.password == conn_meta.password
        assert conn.host == conn_meta.host
        assert conn.schema == conn_meta.schema
        assert conn.port == conn_meta.port

        assert conn.extra_dejson == conn_meta.extra_dejson


class TestAwsConnectionWrapper:
    @pytest.mark.parametrize("extra", [{"foo": "bar", "spam": "egg"}, '{"foo": "bar", "spam": "egg"}', None])
    def test_values_from_connection(self, extra):
        mock_conn = mock_connection_factory(
            login="mock-login",
            password="mock-password",
            extra=extra,
            # AwsBaseHook never use this attributes from airflow.models.Connection
            host=None,
            schema="mock-schema",
            port=42,
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn)

        assert wrap_conn.conn_id == mock_conn.conn_id
        assert wrap_conn.conn_type == mock_conn.conn_type
        assert wrap_conn.login == mock_conn.login
        assert wrap_conn.password == mock_conn.password

        # Check that original extra config from connection persists in wrapper
        assert wrap_conn.extra_config == mock_conn.extra_dejson
        assert wrap_conn.extra_config is not mock_conn.extra_dejson
        # `extra_config` is a same object that return by `extra_dejson`
        assert wrap_conn.extra_config is wrap_conn.extra_dejson
        assert wrap_conn.schema == "mock-schema"

        # Check that not assigned other attributes from airflow.models.Connection to wrapper
        assert not hasattr(wrap_conn, "host")
        assert not hasattr(wrap_conn, "port")

        # Check that Wrapper is True if assign connection
        assert wrap_conn

    def test_no_connection(self):
        assert not AwsConnectionWrapper(conn=None)

    @pytest.mark.parametrize("conn_type", ["aws", None])
    def test_expected_aws_connection_type(self, conn_type):
        wrap_conn = AwsConnectionWrapper(conn=mock_connection_factory(conn_type=conn_type))
        assert wrap_conn.conn_type == "aws"

    @pytest.mark.parametrize("conn_type", ["AWS", "boto3", "emr", "google", "google-cloud-platform"])
    def test_unexpected_aws_connection_type(self, conn_type):
        warning_message = f"expected connection type 'aws', got '{conn_type}'"
        with pytest.warns(UserWarning, match=warning_message):
            wrap_conn = AwsConnectionWrapper(conn=mock_connection_factory(conn_type=conn_type))
        assert wrap_conn.conn_type == conn_type

    @pytest.mark.parametrize("aws_session_token", [None, "mock-aws-session-token"])
    @pytest.mark.parametrize("aws_secret_access_key", ["mock-aws-secret-access-key"])
    @pytest.mark.parametrize("aws_access_key_id", ["mock-aws-access-key-id"])
    def test_get_credentials_from_login(self, aws_access_key_id, aws_secret_access_key, aws_session_token):
        mock_conn = mock_connection_factory(
            login=aws_access_key_id,
            password=aws_secret_access_key,
            extra={"aws_session_token": aws_session_token} if aws_session_token else None,
        )

        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert wrap_conn.aws_access_key_id == aws_access_key_id
        assert wrap_conn.aws_secret_access_key == aws_secret_access_key
        assert wrap_conn.aws_session_token == aws_session_token

    @pytest.mark.parametrize("aws_session_token", [None, "mock-aws-session-token"])
    @pytest.mark.parametrize("aws_secret_access_key", ["mock-aws-secret-access-key"])
    @pytest.mark.parametrize("aws_access_key_id", ["mock-aws-access-key-id"])
    def test_get_credentials_from_extra(self, aws_access_key_id, aws_secret_access_key, aws_session_token):
        mock_conn_extra = {
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        }
        if aws_session_token:
            mock_conn_extra["aws_session_token"] = aws_session_token
        mock_conn = mock_connection_factory(login=None, password=None, extra=mock_conn_extra)

        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert wrap_conn.aws_access_key_id == aws_access_key_id
        assert wrap_conn.aws_secret_access_key == aws_secret_access_key
        assert wrap_conn.aws_session_token == aws_session_token

    @pytest.mark.parametrize("aws_access_key_id", [None, "mock-aws-access-key-id"])
    @pytest.mark.parametrize("aws_secret_access_key", [None, "mock-aws-secret-access-key"])
    @pytest.mark.parametrize("aws_session_token", [None, "mock-aws-session-token"])
    @pytest.mark.parametrize("profile_name", [None, "mock-profile"])
    @pytest.mark.parametrize("region_name", [None, "mock-region-name"])
    def test_get_session_kwargs_from_wrapper(
        self, aws_access_key_id, aws_secret_access_key, aws_session_token, profile_name, region_name
    ):
        mock_conn_extra = {
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "aws_session_token": aws_session_token,
            "profile_name": profile_name,
            "region_name": region_name,
        }
        mock_conn = mock_connection_factory(extra=mock_conn_extra)
        expected = {}
        if aws_access_key_id:
            expected["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            expected["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            expected["aws_session_token"] = aws_session_token
        if profile_name:
            expected["profile_name"] = profile_name
        if region_name:
            expected["region_name"] = region_name
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # Not expected any warnings here
            wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        session_kwargs = wrap_conn.session_kwargs
        assert session_kwargs == expected

        # Test that session parameters immutable
        session_kwargs["botocore_session"] = "foo.bar"
        assert wrap_conn.session_kwargs == expected
        assert wrap_conn.session_kwargs != session_kwargs

    @pytest.mark.parametrize(
        "region_name,conn_region_name",
        [
            ("mock-region-name", None),
            ("mock-region-name", "mock-connection-region-name"),
            (None, "mock-connection-region-name"),
            (None, None),
        ],
    )
    def test_get_region_name(self, region_name, conn_region_name):
        mock_conn = mock_connection_factory(
            extra={"region_name": conn_region_name} if conn_region_name else None
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn, region_name=region_name)
        if region_name:
            assert wrap_conn.region_name == region_name, "Expected provided region_name"
        else:
            assert wrap_conn.region_name == conn_region_name, "Expected connection region_name"

    def test_warn_wrong_profile_param_used(self):
        mock_conn = mock_connection_factory(extra={"profile": "mock-profile"})
        warning_message = "Found 'profile' without specifying 's3_config_file' in .* set 'profile_name' in"
        with pytest.warns(UserWarning, match=warning_message):
            wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert "profile_name" not in wrap_conn.session_kwargs

    @mock.patch("airflow.providers.amazon.aws.utils.connection_wrapper.Config")
    @pytest.mark.parametrize(
        "botocore_config, botocore_config_kwargs",
        [
            (Config(s3={"us_east_1_regional_endpoint": "regional"}), None),
            (Config(region_name="ap-southeast-1"), {"user_agent": "Airflow Amazon Provider"}),
            (None, {"user_agent": "Airflow Amazon Provider"}),
            (None, {"signature_version": "unsigned"}),
            (None, None),
        ],
    )
    def test_get_botocore_config(self, mock_botocore_config, botocore_config, botocore_config_kwargs):
        mock_conn = mock_connection_factory(
            extra={"config_kwargs": botocore_config_kwargs} if botocore_config_kwargs else None
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn, botocore_config=botocore_config)

        if botocore_config:
            assert wrap_conn.botocore_config == botocore_config, "Expected provided botocore_config"
            assert mock_botocore_config.assert_not_called
        elif not botocore_config_kwargs:
            assert wrap_conn.botocore_config is None, "Expected default botocore_config"
            assert mock_botocore_config.assert_not_called
        else:
            assert mock_botocore_config.assert_called_once
            if botocore_config_kwargs.get("signature_version") == "unsigned":
                botocore_config_kwargs["signature_version"] = UNSIGNED
            assert mock.call(**botocore_config_kwargs) in mock_botocore_config.mock_calls

    @pytest.mark.parametrize("aws_account_id, aws_iam_role", [(None, None), ("111111111111", "another-role")])
    def test_get_role_arn(self, aws_account_id, aws_iam_role):
        mock_conn = mock_connection_factory(
            extra={
                "role_arn": MOCK_ROLE_ARN,
                "aws_account_id": aws_account_id,
                "aws_iam_role": aws_iam_role,
            }
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert wrap_conn.role_arn == MOCK_ROLE_ARN

    def test_empty_role_arn(self):
        wrap_conn = AwsConnectionWrapper(conn=mock_connection_factory())
        assert wrap_conn.role_arn is None
        assert wrap_conn.assume_role_method is None
        assert wrap_conn.assume_role_kwargs == {}

    @pytest.mark.parametrize(
        "assume_role_method", ["assume_role", "assume_role_with_saml", "assume_role_with_web_identity"]
    )
    def test_get_assume_role_method(self, assume_role_method):
        mock_conn = mock_connection_factory(
            extra={"role_arn": MOCK_ROLE_ARN, "assume_role_method": assume_role_method}
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert wrap_conn.assume_role_method == assume_role_method

    def test_default_assume_role_method(self):
        mock_conn = mock_connection_factory(
            extra={
                "role_arn": MOCK_ROLE_ARN,
            }
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert wrap_conn.assume_role_method == "assume_role"

    def test_unsupported_assume_role_method(self):
        mock_conn = mock_connection_factory(
            extra={"role_arn": MOCK_ROLE_ARN, "assume_role_method": "dummy_method"}
        )
        with pytest.raises(NotImplementedError, match="Found assume_role_method='dummy_method' in .* extra"):
            AwsConnectionWrapper(conn=mock_conn)

    @pytest.mark.parametrize("assume_role_kwargs", [None, {"DurationSeconds": 42}])
    def test_get_assume_role_kwargs(self, assume_role_kwargs):
        mock_conn_extra = {"role_arn": MOCK_ROLE_ARN}
        if assume_role_kwargs:
            mock_conn_extra["assume_role_kwargs"] = assume_role_kwargs
        mock_conn = mock_connection_factory(extra=mock_conn_extra)

        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        expected = assume_role_kwargs or {}
        assert wrap_conn.assume_role_kwargs == expected

    @pytest.mark.parametrize("external_id_in_extra", [None, "mock-external-id-in-extra"])
    def test_get_assume_role_kwargs_external_id_in_kwargs(self, external_id_in_extra):
        mock_external_id_in_kwargs = "mock-external-id-in-kwargs"
        mock_conn_extra = {
            "role_arn": MOCK_ROLE_ARN,
            "assume_role_kwargs": {"ExternalId": mock_external_id_in_kwargs},
        }
        if external_id_in_extra:
            mock_conn_extra["external_id"] = external_id_in_extra
        mock_conn = mock_connection_factory(extra=mock_conn_extra)

        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert "ExternalId" in wrap_conn.assume_role_kwargs
        assert wrap_conn.assume_role_kwargs["ExternalId"] == mock_external_id_in_kwargs
        assert wrap_conn.assume_role_kwargs["ExternalId"] != external_id_in_extra

    @pytest.mark.parametrize(
        "orig_wrapper",
        [
            AwsConnectionWrapper(
                conn=mock_connection_factory(
                    login="mock-login",
                    password="mock-password",
                    extra={
                        "region_name": "mock-region",
                        "botocore_kwargs": {"user_agent": "Airflow Amazon Provider"},
                        "role_arn": MOCK_ROLE_ARN,
                        "aws_session_token": "mock-aws-session-token",
                    },
                ),
            ),
            AwsConnectionWrapper(conn=mock_connection_factory()),
            AwsConnectionWrapper(conn=None),
            AwsConnectionWrapper(
                conn=None,
                region_name="mock-region",
                botocore_config=Config(user_agent="Airflow Amazon Provider"),
            ),
        ],
    )
    @pytest.mark.parametrize("region_name", [None, "ca-central-1"])
    @pytest.mark.parametrize("botocore_config", [None, Config(region_name="ap-southeast-1")])
    def test_wrap_wrapper(self, orig_wrapper, region_name, botocore_config):
        wrap_kwargs = {}
        if region_name:
            wrap_kwargs["region_name"] = region_name
        if botocore_config:
            wrap_kwargs["botocore_config"] = botocore_config
        wrap_conn = AwsConnectionWrapper(conn=orig_wrapper, **wrap_kwargs)

        # Non init fields should be same in orig_wrapper and child wrapper
        wrap_non_init_fields = [f.name for f in fields(wrap_conn) if not f.init]
        for field in wrap_non_init_fields:
            assert getattr(wrap_conn, field) == getattr(orig_wrapper, field), (
                "Expected no changes in non-init values"
            )

        # Test overwrite/inherit init fields
        assert wrap_conn.region_name == (region_name or orig_wrapper.region_name)
        assert wrap_conn.botocore_config == (botocore_config or orig_wrapper.botocore_config)

    @pytest.mark.parametrize("conn_id", [None, "mock-conn-id"])
    @pytest.mark.parametrize("profile_name", [None, "mock-profile"])
    @pytest.mark.parametrize("role_arn", [None, MOCK_ROLE_ARN])
    def test_get_wrapper_from_metadata(self, conn_id, profile_name, role_arn):
        mock_conn = mock_connection_factory(
            conn_id=conn_id,
            extra={
                "role_arn": role_arn,
                "profile_name": profile_name,
            },
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert wrap_conn
        assert wrap_conn.conn_id == conn_id
        assert wrap_conn.role_arn == role_arn
        assert wrap_conn.profile_name == profile_name

    def test_get_service_config(self):
        mock_conn = mock_connection_factory(
            conn_id="foo-bar",
            extra={
                "service_config": {
                    "sns": {"foo": "bar"},
                    "s3": {"spam": "egg", "baz": "qux"},
                    "dynamodb": None,
                },
            },
        )
        wrap_conn = AwsConnectionWrapper(conn=mock_conn)
        assert wrap_conn.get_service_config("sns") == {"foo": "bar"}
        assert wrap_conn.get_service_config("s3") == {"spam": "egg", "baz": "qux"}
        assert wrap_conn.get_service_config("ec2") == {}
        assert wrap_conn.get_service_config("dynamodb") is None

    def test_get_service_endpoint_url(self):
        fake_conn = mock_connection_factory(
            conn_id="foo-bar",
            extra={
                "endpoint_url": "https://spam.egg",
                "service_config": {
                    "sns": {"endpoint_url": "https://foo.bar"},
                    "ec2": {"endpoint_url": None},  # Enforce to boto3
                },
            },
        )
        wrap_conn = AwsConnectionWrapper(conn=fake_conn)
        assert wrap_conn.get_service_endpoint_url("sns") == "https://foo.bar"
        assert wrap_conn.get_service_endpoint_url("sts") == "https://spam.egg"
        assert wrap_conn.get_service_endpoint_url("ec2") is None

    @pytest.mark.parametrize(
        "global_endpoint_url, sts_service_endpoint_url, expected_endpoint_url",
        [
            pytest.param(None, None, None, id="not-set"),
            pytest.param("https://global.service", None, None, id="global-only"),
            pytest.param(None, "https://sts.service:1234", "https://sts.service:1234", id="service-only"),
            pytest.param(
                "https://global.service", "https://sts.service:1234", "https://sts.service:1234", id="mixin"
            ),
        ],
    )
    def test_get_service_endpoint_url_sts(
        self, global_endpoint_url, sts_service_endpoint_url, expected_endpoint_url
    ):
        fake_extra = {}
        if global_endpoint_url:
            fake_extra["endpoint_url"] = global_endpoint_url
        if sts_service_endpoint_url:
            fake_extra["service_config"] = {"sts": {"endpoint_url": sts_service_endpoint_url}}

        fake_conn = mock_connection_factory(conn_id="foo-bar", extra=fake_extra)
        wrap_conn = AwsConnectionWrapper(conn=fake_conn)
        assert wrap_conn.get_service_endpoint_url("sts", sts_connection_assume=True) == expected_endpoint_url
        assert wrap_conn.get_service_endpoint_url("sts", sts_test_connection=True) == expected_endpoint_url

    def test_get_service_endpoint_url_sts_unsupported(self):
        wrap_conn = AwsConnectionWrapper(conn=mock_connection_factory())
        with pytest.raises(AirflowException, match=r"Can't resolve STS endpoint when both"):
            wrap_conn.get_service_endpoint_url("sts", sts_test_connection=True, sts_connection_assume=True)
        # This check is only affects STS service endpoints
        wrap_conn.get_service_endpoint_url("s3", sts_test_connection=True, sts_connection_assume=True)
