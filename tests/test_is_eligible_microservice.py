import logging
from datetime import datetime
from unittest.mock import patch, MagicMock

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from satosa.context import Context
from satosa.internal import InternalData
from satosa.micro_services.base import MicroService
from satosa.response import Redirect
from tests.test_microservice_loader import Loader

from satosacontrib.perun.micro_services.is_eligible_microservice import IsEligible # noqa
from satosacontrib.perun.utils.PerunConstants import PerunConstants

DATE_NOW = "2022-01-30 12:00:00"

EXAMPLE_TIMESTAMP_ATTR = "example_timestamp_attr"
VALIDITY_PERIOD = 1  # months
TRIGGER_ATTRIBUTE = "example_trigger_attr"
TRIGGER_ATTR_NOT_CONSUMED_ERROR_MESSAGE = (
    "SP does not consume the trigger "
    f"attribute '{TRIGGER_ATTRIBUTE}'. "
    "Terminating execution of this "
    "microservice."
)

MICROSERVICE_CONFIG = {
    "filter_config": {
        "trigger_attribute": TRIGGER_ATTRIBUTE,
        "eligible_last_seen_timestamp_attribute": EXAMPLE_TIMESTAMP_ATTR,
        "validity_period_months": VALIDITY_PERIOD,
    },
    "unauthorized_redirect_url": "example_url",
}

MICROSERVICE = Loader(
    MICROSERVICE_CONFIG, IsEligible.__name__
).create_mocked_instance()


def test_process_data_without_destination(caplog):
    data_without_destination = InternalData()

    with caplog.at_level(logging.INFO):
        MICROSERVICE.process(Context(), data_without_destination)

        assert TRIGGER_ATTR_NOT_CONSUMED_ERROR_MESSAGE in caplog.text


def test_process_data_without_destination_attrs(caplog):
    data_without_destination_attrs = InternalData()
    data_without_destination_attrs.attributes[PerunConstants.DESTINATION] = {}

    with caplog.at_level(logging.INFO):
        MICROSERVICE.process(Context(), data_without_destination_attrs)

        assert TRIGGER_ATTR_NOT_CONSUMED_ERROR_MESSAGE in caplog.text


def test_process_data_without_trigger_attr(caplog):
    data_without_trigger_attr = InternalData()
    data_without_trigger_attr.attributes = {
        PerunConstants.DESTINATION: {PerunConstants.DESTINATION_ATTRIBUTES: {}}
    }

    with caplog.at_level(logging.INFO):
        MICROSERVICE.process(Context(), data_without_trigger_attr)

        assert TRIGGER_ATTR_NOT_CONSUMED_ERROR_MESSAGE in caplog.text


@patch("satosacontrib.perun.micro_services.is_eligible_microservice.IsEligible.unauthorized") # noqa
def test_process_data_without_timestamp(mock_request_1, caplog):
    data_without_timestamp = InternalData()
    data_without_timestamp.attributes = {
        PerunConstants.DESTINATION: {
            PerunConstants.DESTINATION_ATTRIBUTES: {
                TRIGGER_ATTRIBUTE: "example_value"
            }
        }
    }
    missing_timestamp_error_message = (
        "Timestamp of the last seen eligibility is empty, cannot let user go"
        " through. Redirecting to unauthorized explanation page."
    )

    IsEligible.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.INFO):
        MICROSERVICE.process(Context(), data_without_timestamp)

        assert missing_timestamp_error_message in caplog.text
        IsEligible.unauthorized.assert_called()


@freeze_time(DATE_NOW)
@patch("satosacontrib.perun.micro_services.is_eligible_microservice.IsEligible.unauthorized") # noqa
def test_process_data_with_old_timestamp(mock_request_1, caplog):
    # make the mocked timestamp twice as old as the max allowed validity period
    old_timestamp = str(
        datetime.fromisoformat(DATE_NOW)
        - relativedelta(months=VALIDITY_PERIOD * 2)
    )
    data_with_old_timestamp = InternalData()
    data_with_old_timestamp.attributes = {
        PerunConstants.DESTINATION: {
            PerunConstants.DESTINATION_ATTRIBUTES: {
                TRIGGER_ATTRIBUTE: "example_value"
            }
        },
        PerunConstants.ATTRIBUTES: {EXAMPLE_TIMESTAMP_ATTR: [old_timestamp]},
    }
    old_timestamp_error_message = (
        f"Last seen eligibility timestamp '{old_timestamp}' is older than"
        f" {VALIDITY_PERIOD} month(s), which is the maximum allowed period of"
        " time. Redirecting to unauthorized explanation page."
    )

    IsEligible.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.INFO):
        MICROSERVICE.process(Context(), data_with_old_timestamp)

        assert old_timestamp_error_message in caplog.text
        IsEligible.unauthorized.assert_called()


@freeze_time(DATE_NOW)
@patch("satosa.micro_services.base.MicroService.process")
def test_process_data_with_valid_timestamp(mock_request_1, caplog):
    # make the mocked timestamp as old as the max allowed validity period
    valid_timestamp = str(
        datetime.fromisoformat(DATE_NOW)
        - relativedelta(months=VALIDITY_PERIOD)
    )
    data_with_valid_timestamp = InternalData()
    data_with_valid_timestamp.attributes = {
        PerunConstants.DESTINATION: {
            PerunConstants.DESTINATION_ATTRIBUTES: {
                TRIGGER_ATTRIBUTE: "example_value"
            }
        },
        PerunConstants.ATTRIBUTES: {EXAMPLE_TIMESTAMP_ATTR: [valid_timestamp]},
    }
    valid_timestamp_message = (
        f"Last seen eligibility timestamp '{valid_timestamp}' is not older"
        f" than {VALIDITY_PERIOD} month(s), which is the maximum allowed"
        " period of time. Continuing with the next check."
    )

    MicroService.process = MagicMock(return_value=None)

    with caplog.at_level(logging.INFO):
        MICROSERVICE.process(Context(), data_with_valid_timestamp)

        assert valid_timestamp_message in caplog.text
        MicroService.process.assert_called()


def test_unauthorized_access():
    result = MICROSERVICE.unauthorized()
    expected_header = (
        "Location",
        MICROSERVICE_CONFIG["unauthorized_redirect_url"],
    )

    assert isinstance(result, Redirect)
    assert expected_header in result.headers
