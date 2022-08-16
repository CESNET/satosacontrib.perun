import copy
import logging
from unittest.mock import patch, MagicMock

import pytest
from perun.connector import MemberStatusEnum, Group, VO
from perun.connector.adapters.AdaptersManager import AdaptersManager
from satosa.context import Context
from satosa.exception import SATOSAError
from satosa.internal import InternalData
from satosa.micro_services.base import MicroService
from satosa.response import Redirect

from satosacontrib.perun.micro_services.sp_authorization_microservice import (
    SpAuthorization,
)
from satosacontrib.perun.utils.PerunConstants import PerunConstants
from satosacontrib.perun.utils.Utils import Utils
from tests.test_microservice_loader import Loader

MICROSERVICE_CONFIG = {
    "global_cfg_filepath": "example_path",
    "filter_config": {
        "check_group_membership_attr": "example_attr",
        "vo_short_names_attr": "example_attr",
        "allow_registration_attr": "example_attr",
        "registrar_url": "example_url",
        "registration_link_attr": "example_attr",
        "skip_notification_sps": ["sp1", "sp2", "sp3"],
        "handle_unsatisfied_membership": True,
    },
    "unauthorized_redirect_url": "example_url",
    "single_group_registration_url": "example_url",
    "register_choose_vo_and_group_url": "example_url",
    "notification_url": "example_url",
    "registration_result_url": "example_url",
}


MICROSERVICE = Loader(
    MICROSERVICE_CONFIG, SpAuthorization.__name__
).create_mocked_instance()

DEBUG_PREFIX = MICROSERVICE._SpAuthorization__DEBUG_PREFIX
REGISTRAR_URL = MICROSERVICE._SpAuthorization__REGISTRAR_URL
REGISTRATION_LINK_ATTR = MICROSERVICE._SpAuthorization__REGISTRATION_LINK_ATTR


def test_initial_misconfiguration():
    bad_config = copy.deepcopy(MICROSERVICE_CONFIG)
    bad_config["filter_config"]["registration_link_attr"] = None
    bad_config["filter_config"]["registrar_url"] = None
    bad_config["filter_config"]["handle_unsatisfied_membership"] = True
    misconfiguration_error_message = (
        f"{DEBUG_PREFIX}: 'Invalid configuration: microservice should handle"
        " unsatisfied membership via registration, but neither registrar_url"
        " nor registration_link_attr have been configured. Use option"
        f" '{REGISTRAR_URL}' to configure the registrar location or/and option"
        f" '{REGISTRATION_LINK_ATTR}' to configure attribute for Service"
        " defined registration link."
    )

    with pytest.raises(SATOSAError) as error:
        _ = Loader(
            bad_config, SpAuthorization.__name__
        ).create_mocked_instance()
        assert str(error.value.args[0]) == misconfiguration_error_message


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
def test_process_no_user_in_request(mock_request_1, caplog):
    no_user_error_message = (
        "Request does not contain Perun user. Did you configure PerunUser"
        " microservice?"
    )
    data_without_user = InternalData()
    data_without_user.attributes["example_user_id"] = None

    SpAuthorization.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        MICROSERVICE.process(None, data_without_user)
        assert no_user_error_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_facility_by_rp_identifier"  # noqa
)
def test_process_no_facility_found(mock_request_1, caplog):
    non_existent_sp_id = "non_existent_sp_id"
    no_facility_error_message = (
        f"No facility found for SP '{non_existent_sp_id}', skipping processing"
        " filter."
    )
    data_with_non_existent_sp_id = InternalData()
    data_with_non_existent_sp_id.requester = non_existent_sp_id
    data_with_non_existent_sp_id.attributes["example_user_id"] = "example user"

    AdaptersManager.get_facility_by_rp_identifier = MagicMock(
        return_value=None
    )

    with caplog.at_level(logging.DEBUG):
        result = MICROSERVICE.process(None, data_with_non_existent_sp_id)
        assert no_facility_error_message in caplog.text
        assert result is None


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_facility_by_rp_identifier"  # noqa
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__get_sp_attributes"  # noqa
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
def test_process_no_attrs_in_facility(
    mock_request_1, mock_request_2, mock_request_3, caplog
):
    no_facility_attrs_error_message = (
        "Could not fetch SP attributes, user will be redirected to"
        " unauthorized for security reasons"
    )
    data_without_facility_attrs = InternalData()
    data_without_facility_attrs.attributes["example_user_id"] = "example user"

    AdaptersManager.get_facility_by_rp_identifier = MagicMock(
        return_value="example facility"
    )
    SpAuthorization._SpAuthorization__get_sp_attributes = MagicMock(
        return_value={}
    )
    SpAuthorization.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        MICROSERVICE.process(None, data_without_facility_attrs)
        assert no_facility_attrs_error_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager"
    ".get_facility_by_rp_identifier"
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization"  # noqa
    "._SpAuthorization__get_sp_attributes"
)
def test_process_group_membership_check_not_required(
    mock_request_1, mock_request_2, caplog
):
    group_membership_not_required_message = (
        "Group membership check not requested by the service."
    )
    data_without_group_membership_check = InternalData()
    data_without_group_membership_check.attributes[
        "example_user_id"
    ] = "example user"

    AdaptersManager.get_facility_by_rp_identifier = MagicMock(
        return_value="example facility"
    )
    SpAuthorization._SpAuthorization__get_sp_attributes = MagicMock(
        return_value={"check_group_membership": False}
    )

    with caplog.at_level(logging.WARNING):
        result = MICROSERVICE.process(
            None, data_without_group_membership_check
        )
        assert group_membership_not_required_message in caplog.text
        assert result is None


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager"
    ".get_facility_by_rp_identifier"
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager"
    ".get_users_groups_on_facility"
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization"  # noqa
    "._SpAuthorization__get_sp_attributes"
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization"  # noqa
    ".handle_unsatisfied_membership"
)
def test_process_no_users_groups_found(
    mock_request_1, mock_request_2, mock_request_3, mock_request_4
):
    data_user_without_groups = InternalData()
    data_user_without_groups.attributes["example_user_id"] = "example user"

    AdaptersManager.get_facility_by_rp_identifier = MagicMock(
        return_value="example facility"
    )
    SpAuthorization._SpAuthorization__get_sp_attributes = MagicMock(
        return_value={"check_group_membership": True}
    )
    AdaptersManager.get_users_groups_on_facility = MagicMock(return_value=[])
    SpAuthorization.handle_unsatisfied_membership = MagicMock(
        return_value=None
    )

    result = MICROSERVICE.process(None, data_user_without_groups)
    assert result is None
    SpAuthorization.handle_unsatisfied_membership.assert_called()


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager"
    ".get_facility_by_rp_identifier"
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager"
    ".get_users_groups_on_facility"
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization"  # noqa
    "._SpAuthorization__get_sp_attributes"
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization"  # noqa
    ".handle_unsatisfied_membership"
)
@patch("satosa.micro_services.base.MicroService.process")
def test_process_users_groups_found(
    mock_request_1,
    mock_request_2,
    mock_request_3,
    mock_request_4,
    mock_request_5,
    caplog,
):
    user_satisfies_check_message = "User satisfies the group membership check."
    data_user_with_groups = InternalData()
    data_user_with_groups.attributes["example_user_id"] = "example user"

    AdaptersManager.get_facility_by_rp_identifier = MagicMock(
        return_value="example facility"
    )
    SpAuthorization._SpAuthorization__get_sp_attributes = MagicMock(
        return_value={"check_group_membership": True}
    )
    AdaptersManager.get_users_groups_on_facility = MagicMock(
        return_value=["group1", "group2"]
    )
    MicroService.process = MagicMock(return_value=None)

    with caplog.at_level(logging.INFO):
        MICROSERVICE.process(None, data_user_with_groups)
        assert user_satisfies_check_message in caplog.text
        MicroService.process.assert_called()


def test_unauthorized_access():
    result = MICROSERVICE.unauthorized()
    expected_header = (
        "Location",
        MICROSERVICE_CONFIG["unauthorized_redirect_url"],
    )

    assert isinstance(result, Redirect)
    assert expected_header in result.headers


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
def test_handle_unsatisfied_membership_disabled(mock_request_1, caplog):
    handling_disabled_message = (
        "Handling unsatisfied membership is disabled, redirecting to"
        " unauthorized"
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = False
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    SpAuthorization.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        microservice.handle_unsatisfied_membership(
            None, None, None, None, None, None
        )
        assert handling_disabled_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
def test_handle_unsatisfied_membership_registration_unspecified(
    mock_request_1, caplog
):
    handling_disabled_message = (
        "Handling unsatisfied membership is disabled, redirecting to"
        " unauthorized"
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = False
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    SpAuthorization.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        microservice.handle_unsatisfied_membership(
            None, None, None, None, None, facility_attributes={}
        )
        assert handling_disabled_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
def test_handle_unsatisfied_membership_registration_disallowed(
    mock_request_1, caplog
):
    data_requester = "example_entity_id"
    registration_disallowed_message = (
        "User is not member of any assigned groups of resources for service"
        f" ('{data_requester}'). Registration to the groups is disabled."
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = True
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    SpAuthorization.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        facility_attrs = {"allow_registration": False}
        microservice.handle_unsatisfied_membership(
            context=None,
            data=None,
            user_id=None,
            data_requester=data_requester,
            facility=None,
            facility_attributes=facility_attrs,
        )
        assert registration_disallowed_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
def test_handle_unsatisfied_membership_registration_not_set(
    mock_request_1, caplog
):
    data_requester = "example_entity_id"
    registration_not_set_message = (
        "User is not member of any assigned groups of resources for service"
        f" ('{data_requester}'). Registration to the groups is disabled."
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = True
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    SpAuthorization.unauthorized = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        microservice.handle_unsatisfied_membership(
            context=None,
            data=None,
            user_id=None,
            data_requester=data_requester,
            facility=None,
            facility_attributes={},
        )
        assert registration_not_set_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


def test_handle_unsatisfied_membership_registration_link_set(caplog):
    data_requester = "example_entity_id"
    registration_link = "example_registration_link"
    registration_redirect_message = (
        f"Redirecting user to custom registration link '{registration_link}'"
        f" configured for service ('{data_requester}')."
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = True
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    expected_header = ("Location", registration_link)

    with caplog.at_level(logging.DEBUG):
        facility_attrs = {
            "allow_registration": True,
            "registration_link": registration_link,
        }
        context = Context()
        context.state = {}
        result = microservice.handle_unsatisfied_membership(
            context=context,
            data=InternalData(),
            user_id=None,
            data_requester=data_requester,
            facility=None,
            facility_attributes=facility_attrs,
        )
        assert isinstance(result, Redirect)
        assert expected_header in result.headers
        assert registration_redirect_message in caplog.text


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__get_registration_data"  # noqa
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.register"  # noqa
)
def test_handle_unsatisfied_membership_has_available_groups(
    mock_request_1, mock_request_2
):
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = True
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    SpAuthorization._SpAuthorization__get_registration_data = MagicMock(
        return_value=["group1", "group2"]
    )
    SpAuthorization.register = MagicMock(return_value=None)

    facility_attrs = {"allow_registration": True}
    microservice.handle_unsatisfied_membership(
        context=None,
        data=None,
        user_id=None,
        data_requester=None,
        facility=None,
        facility_attributes=facility_attrs,
    )
    SpAuthorization.register.assert_called()


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__get_registration_data"  # noqa
)
def test_handle_unsatisfied_membership_no_available_groups(
    mock_request_1, mock_request_2, caplog
):
    data_requester = "example_entity_id"
    no_available_groups_message = (
        "No VO is available for registration into groups of resources for"
        f" service '{data_requester}'"
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = True
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    SpAuthorization.unauthorized = MagicMock(return_value=None)
    SpAuthorization._SpAuthorization__get_registration_data = MagicMock(
        return_value=[]
    )

    with caplog.at_level(logging.DEBUG):
        facility_attrs = {"allow_registration": True}
        microservice.handle_unsatisfied_membership(
            context=None,
            data=None,
            user_id=None,
            data_requester=data_requester,
            facility=None,
            facility_attributes=facility_attrs,
        )
        assert no_available_groups_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__get_registration_data"  # noqa
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization.unauthorized"  # noqa
)
def test_handle_unsatisfied_membership_exception(
    mock_request_1, mock_request_2, caplog
):
    exception_occurred_message = (
        "Caught an exception, user will be redirected to unauthorized for"
        " security reasons"
    )
    exception_message = "Some error happened"
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["filter_config"]["handle_unsatisfied_membership"] = True
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    SpAuthorization._SpAuthorization__get_registration_data = MagicMock(
        side_effect=Exception(exception_message)
    )
    SpAuthorization.unauthorized = MagicMock(return_value=None)

    facility_attrs = {"allow_registration": True}

    with caplog.at_level(logging.WARNING):
        microservice.handle_unsatisfied_membership(
            context=None,
            data=None,
            user_id=None,
            data_requester=None,
            facility=None,
            facility_attributes=facility_attrs,
        )
        assert exception_occurred_message in caplog.text
        SpAuthorization.unauthorized.assert_called()

    with caplog.at_level(logging.DEBUG):
        microservice.handle_unsatisfied_membership(
            context=None,
            data=None,
            user_id=None,
            data_requester=None,
            facility=None,
            facility_attributes=facility_attrs,
        )
        assert exception_message in caplog.text
        SpAuthorization.unauthorized.assert_called()


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__register_directly"  # noqa
)
def test_register_single_option(mock_request_1, caplog):
    single_registration_message = (
        "Registration possible to only single VO and GROUP, redirecting"
        " directly to this registration."
    )

    SpAuthorization._SpAuthorization__register_directly = MagicMock(
        return_value=None
    )

    with caplog.at_level(logging.DEBUG):
        MICROSERVICE.register(
            context=None,
            data=None,
            registration_data=["group1"],
            skip_notification=None,
        )
        assert single_registration_message in caplog.text
        SpAuthorization._SpAuthorization__register_directly.assert_called()


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__register_choose_vo_and_group"  # noqa
)
def test_register_multiple_options(mock_request_1, caplog):
    multiple_options_message = (
        "Registration possible to more than a single VO and GROUP, letting"
        " user choose."
    )

    SpAuthorization._SpAuthorization__register_choose_vo_and_group = MagicMock(
        return_value=None
    )

    with caplog.at_level(logging.DEBUG):
        MICROSERVICE.register(
            context=None,
            data=None,
            registration_data=["group1", "group2"],
            skip_notification=None,
        )
        assert multiple_options_message in caplog.text
        SpAuthorization._SpAuthorization__register_choose_vo_and_group.assert_called()  # noqa


def test_register_directly_no_registration_url():
    no_url_error_message = (
        "Unable to register user into group: None, redirect link to"
        " registration page is missing in the config file."
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["single_group_registration_url"] = None
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    with pytest.raises(SATOSAError) as error:
        microservice._SpAuthorization__register_directly(
            None, None, None, None
        )
        assert str(error.value.args[0]) == no_url_error_message


def test_register_directly_no_notification_url():
    no_url_error_message = (
        "Unable to register user into group: None, redirect link to"
        " notification page is missing in the config file."
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["single_group_registration_url"] = "example url"
    custom_config["notification_url"] = None
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    with pytest.raises(SATOSAError) as error:
        microservice._SpAuthorization__register_directly(
            context=None,
            data=InternalData(),
            group=None,
            skip_notification=False,
        )
        assert str(error.value.args[0]) == no_url_error_message


@patch("satosacontrib.perun.utils.Utils.Utils.secure_redirect_with_nonce")
def test_register_directly_no_notification(mock_request_1, caplog):
    registration_url = "example url"
    skip_notification_message = (
        "Skipping registration notification. Redirecting directly to"
        f" '{registration_url}."
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["single_group_registration_url"] = registration_url
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    Utils.secure_redirect_with_nonce = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        microservice._SpAuthorization__register_directly(
            context=None,
            data=InternalData(),
            group=None,
            skip_notification=True,
        )
        assert skip_notification_message in caplog.text
        Utils.secure_redirect_with_nonce.assert_called()  # noqa


@patch("satosacontrib.perun.utils.Utils.Utils.secure_redirect_with_nonce")
def test_register_directly_with_notification(mock_request_1, caplog):
    registration_url = "example url"
    sending_notification_message = (
        "Displaying registration notification. After that, redirecting to"
        f" '{registration_url}'."
    )
    custom_config = copy.deepcopy(MICROSERVICE_CONFIG)
    custom_config["single_group_registration_url"] = registration_url
    custom_config["notification_url"] = "example url"
    microservice = Loader(
        custom_config, SpAuthorization.__name__
    ).create_mocked_instance()

    Utils.secure_redirect_with_nonce = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        microservice._SpAuthorization__register_directly(
            context=None,
            data=InternalData(),
            group=None,
            skip_notification=False,
        )
        assert sending_notification_message in caplog.text
        Utils.secure_redirect_with_nonce.assert_called()  # noqa


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__register_choose_vo_and_group"  # noqa
)
def test_register_choose_vo_and_group(mock_request_1):

    SpAuthorization._SpAuthorization__register_vo_and_group = MagicMock(
        return_value=None
    )

    MICROSERVICE._SpAuthorization__register_choose_vo_and_group(
        context=None, data=InternalData(), registration_data=None
    )

    SpAuthorization._SpAuthorization__register_choose_vo_and_group.assert_called()  # noqa


def test_get_registration_data_misconfigured():
    data_requester = "example_entity_id"
    debug_prefix = MICROSERVICE._SpAuthorization__DEBUG_PREFIX
    no_resources_error_message = (
        f"{debug_prefix}: Service misconfiguration - service '{data_requester}'"  # noqa
        " has membership check enabled, but does not have any resources for"
        " membership management created."
    )

    with pytest.raises(SATOSAError) as error:
        MICROSERVICE._SpAuthorization__get_registration_data(
            None, None, None, facility_attributes={}
        )
        assert str(error.value.args[0]) == no_resources_error_message


@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__get_registration_vo_short_names"  # noqa
)
@patch(
    "satosacontrib.perun.micro_services.sp_authorization_microservice.SpAuthorization._SpAuthorization__get_registration_groups"  # noqa
)
def test_get_registration_data(mock_request_1, mock_request_2):
    SpAuthorization._SpAuthorization__get_registration_vo_short_names = (
        MagicMock(return_value=None)
    )
    SpAuthorization._SpAuthorization__get_registration_groups = MagicMock(
        return_value=None
    )

    facility_attrs = {"vo_short_names": ["name1", "name2"]}
    MICROSERVICE._SpAuthorization__get_registration_data(
        None, None, None, facility_attributes=facility_attrs
    )
    SpAuthorization._SpAuthorization__get_registration_vo_short_names.assert_called()  # noqa
    SpAuthorization._SpAuthorization__get_registration_groups.assert_called()


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo")
def test_get_registraion_vo_short_names_vo_not_fetched(mock_request_1, caplog):
    vo_short_name = "example vo short name"
    vo_not_found_message = (
        f"Could not fetch VO with short name '{vo_short_name}', skipping it."
    )

    AdaptersManager.get_vo = MagicMock(return_value=None)

    with caplog.at_level(logging.DEBUG):
        result = (
            MICROSERVICE._SpAuthorization__get_registration_vo_short_names(
                None, vo_short_names=[vo_short_name]
            )
        )
        assert result == set()
        assert vo_not_found_message in caplog.text


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo")
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo"  # noqa
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name"  # noqa
)
def test_get_registration_vo_short_names_user_valid_member(
    mock_request_1, mock_request_2, mock_request_3, caplog
):
    vo_short_name = "example vo short name"
    expected_set = {vo_short_name}
    valid_vo_member_message = (
        f"User is valid in VO with short name '{vo_short_name}', groups of"
        " this VO will be included in registration list."
    )

    AdaptersManager.get_vo = MagicMock(return_value="example_vo")
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum("VALID")
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )

    with caplog.at_level(logging.DEBUG):
        result = (
            MICROSERVICE._SpAuthorization__get_registration_vo_short_names(
                None, vo_short_names=[vo_short_name]
            )
        )
        assert result == expected_set
        assert valid_vo_member_message in caplog.text


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo")
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo"  # noqa
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name"  # noqa
)
def test_get_registration_vo_short_names_expired_member_with_form(
    mock_request_1, mock_request_2, mock_request_3, caplog
):
    vo_short_name = "example vo short name"
    expected_set = {vo_short_name}
    expired_vo_member_message = (
        f"User is expired in the VO with short name '{vo_short_name}',"
        " checking registration form availability."
    )
    has_form_message = (
        f"User is expired in the VO with short name '{vo_short_name}', groups"
        " of this VO will be included in registration list as it has got"
        " extension form."
    )

    AdaptersManager.get_vo = MagicMock(return_value="example_vo")
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum("EXPIRED")
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )

    with caplog.at_level(logging.DEBUG):
        result = (
            MICROSERVICE._SpAuthorization__get_registration_vo_short_names(
                None, vo_short_names=[vo_short_name]
            )
        )
        assert result == expected_set
        assert expired_vo_member_message in caplog.text
        assert has_form_message in caplog.text


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo")
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo"  # noqa
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name"  # noqa
)
def test_get_registration_vo_short_names_unknown_status(
    mock_request_1, mock_request_2, mock_request_3, caplog
):
    vo_short_name = "example vo short name"
    unknown_status_message = (
        f"User is a member in the VO with short name '{vo_short_name}' but is"
        " neither valid nor expired. VO will be ignored for registration."
    )

    AdaptersManager.get_vo = MagicMock(return_value="example_vo")
    # INVALID status should not be recognized, only VALID and EXPIRED are used
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum("INVALID")
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )

    with caplog.at_level(logging.DEBUG):
        result = (
            MICROSERVICE._SpAuthorization__get_registration_vo_short_names(
                None, vo_short_names=[vo_short_name]
            )
        )
        assert result == set()
        assert unknown_status_message in caplog.text


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo")
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo"  # noqa
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name"  # noqa
)
def test_get_registration_vo_short_names_non_member_without_form(
    mock_request_1, mock_request_2, mock_request_3, caplog
):
    vo_short_name = "example vo short name"
    user_not_member_message = (
        f"User is not a member in the VO with short name '{vo_short_name}'."
    )
    no_form_message = (
        f"VO with shortName '{vo_short_name}' does not have a registration"
        " form, ignoring it."
    )

    AdaptersManager.get_vo = MagicMock(return_value="example_vo")
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=False
    )

    with caplog.at_level(logging.DEBUG):
        result = (
            MICROSERVICE._SpAuthorization__get_registration_vo_short_names(
                None, vo_short_names=[vo_short_name]
            )
        )
        assert result == set()
        assert user_not_member_message in caplog.text
        assert no_form_message in caplog.text


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo")
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo"  # noqa
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name"  # noqa
)
def test_get_registration_vo_short_names_non_member_with_form(
    mock_request_1, mock_request_2, mock_request_3, caplog
):
    vo_short_name = "example vo short name"
    expected_set = {vo_short_name}
    user_not_member_message = (
        f"User is not a member in the VO with short name '{vo_short_name}'."
    )
    has_form_message = (
        f"User is not a member in the VO with short name '{vo_short_name}',"
        " groups of this VO will be included in registration list as it has"
        " got registration form."
    )

    AdaptersManager.get_vo = MagicMock(return_value="example_vo")
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )

    with caplog.at_level(logging.DEBUG):
        result = (
            MICROSERVICE._SpAuthorization__get_registration_vo_short_names(
                None, vo_short_names=[vo_short_name]
            )
        )
        assert result == expected_set
        assert user_not_member_message in caplog.text
        assert has_form_message in caplog.text


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_sp_groups_by_facility"  # noqa
)
@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_group"  # noqa
)
def test_get_registration_groups(mock_request_1, mock_request_2, caplog):
    vo_not_for_registration = VO(1, "not for registration", "short name")
    group_not_for_registration = Group(
        1,
        vo_not_for_registration,
        "uuid",
        "name",
        "unique name",
        "description",
    )

    vo_with_registration_form = VO(2, "for registration", "short name 2")
    group_with_registration_form = Group(
        2,
        vo_with_registration_form,
        "uuid 2",
        "name 2",
        "unique name 2",
        "description 2",
    )

    vo_without_registration_form = VO(2, "for registration 2", "short name 3")
    group_without_registration_form = Group(
        2,
        vo_without_registration_form,
        "uuid 3",
        "name 3",
        "unique name 3",
        "description 3",
    )

    member_vo = VO(2, "for registration 3", "short name 4")
    member_group = Group(
        2,
        member_vo,
        "uuid 4",
        PerunConstants.GROUP_MEMBERS,
        "unique name 4",
        "description 4",
    )
    sp_groups_on_facility = [
        group_not_for_registration,
        group_with_registration_form,
        group_without_registration_form,
        member_group,
    ]
    vo_names_for_registration = [
        "short name 2",
        "short name 3",
        "short name 4",
    ]
    expected_groups = [group_with_registration_form, member_group]

    AdaptersManager.get_sp_groups_by_facility = MagicMock(
        return_value=sp_groups_on_facility
    )
    AdaptersManager.has_registration_form_group = MagicMock(
        side_effect=[True, False, True]
    )

    with caplog.at_level(logging.DEBUG):
        result = MICROSERVICE._SpAuthorization__get_registration_groups(
            facility=None,
            vo_short_names_for_registration=vo_names_for_registration,
        )
        assert len(expected_groups) == len(result)
        for expected_group in expected_groups:
            assert expected_group in result
            expected_message = (
                f"Group '{expected_group.unique_name}' added to the"
                " registration list."
            )
            assert expected_message in caplog.text
