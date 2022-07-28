import threading

from perun.connector.adapters.AdaptersManager import AdaptersManager
from perun.connector.models.User import User
from perun.connector.models.UserExtSource import UserExtSource
from perun.connector.adapters.AdaptersManager import AdaptersManagerException # noqa e501
from satosacontrib.perun.micro_services.update_user_ext_source import UpdateUserExtSource # noqa e501
from satosa.exception import SATOSAError
from satosa.micro_services.base import ResponseMicroService
from unittest.mock import patch, MagicMock
from tests.test_microservice_loader import Loader, TestData, TestContext

import pytest


CONFIG = {
  'array_to_string_conversion': ['ues_affiliation_attr',
                                 'ues_entitlement_attr'],
  'append_only_attrs': ['ues_entitlement_attr'],
  'user_identifiers': [
      'eduperson_unique_id',
      'eduperson_principal_name',
      'eduperson_targeted_id',
      'name_idd',
      'uid'
  ],
  'global_cfg_path': "path",
  'attr_map': {
      'ues_cn_attr': 'cn',
      'ues_display_name_attr': 'display_name',
      'ues_given_name_attr': 'given_name',
      'ues_sn_attr': 'sn',
      'ues_organization_attr': 'o',
      'ues_mail_attr': 'mail',
      'ues_affiliation_attr': 'eduperson_scoped_affiliation',
      'ues_entitlement_attr': 'eduperson_entitlement'
  }
}

ATTRIBUTES = {
    'cn': ['cn'],
    'display_name': ['display_name'],
    'given_name': ['given_name'],
    'sn': ['sn'],
    'o': ['o'],
    'mail': ['mail'],
    'eduperson_scoped_affiliation': ['eduperson_scoped_affiliation'],
    'eduperson_entitlement': ['eduperson_entitlement']
}

DATA = {}

TEST_INSTANCE = Loader(CONFIG, UpdateUserExtSource.__name__).create_mocked_instance() # noqa e501
TEST_DATA = TestData(DATA, ATTRIBUTES)
USER = User(1, "Joe Doe")
EXT_SOURCE = UserExtSource(1, "ext_source", "login", USER)


@patch(
    "satosacontrib.perun.micro_services.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__get_user_ext_source" # noqa e501
)
def test_find_user_ext_source(mock_request_1):
    TEST_INSTANCE._UpdateUserExtSource__find_user_ext_source = MagicMock(return_value=EXT_SOURCE) # noqa e501

    assert TEST_INSTANCE._UpdateUserExtSource__find_user_ext_source(
        "name", ATTRIBUTES, CONFIG['user_identifiers']
    ) == EXT_SOURCE


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_ext_source_attributes" # noqa e501
)
def test_get_attributes_from_perun_error(mock_request_1):
    attrs_without_name = {
        "attr": 1
    }

    error_message = "UpdateUserExtSource" + "Getting attributes for UES " \
                                            "was not successful."

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._UpdateUserExtSource__get_attributes_from_perun(
            None
        )
        assert str(error.value.args[0]) == error_message

    AdaptersManager.get_user_ext_source_attributes = MagicMock(
        return_value=attrs_without_name
    )

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._UpdateUserExtSource__get_attributes_from_perun(
            EXT_SOURCE
        )
        assert str(error.value.args[0]) == error_message


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_ext_source_attributes" # noqa e501
)
def test_get_attributes_from_perun(mock_request_1):
    attrs_with_name = {
        "attr": {
            "name": "name"
        }
    }

    expected_result = {
        "name": {
            "name": "name"
        }
    }

    AdaptersManager.get_user_ext_source_attributes = MagicMock(
        return_value=attrs_with_name
    )
    result = TEST_INSTANCE._UpdateUserExtSource__get_attributes_from_perun(
        EXT_SOURCE
    )

    assert result == expected_result


def test_get_attributes_to_update():
    attrs_from_perun = {
      'ues_cn_attr': 1,
      'ues_display_name_attr': 'display_name',
      'ues_given_name_attr': 'given_name',
      'ues_sn_attr': 'sn',
      'ues_organization_attr': 'o',
      'ues_mail_attr': 'mail',
      'ues_affiliation_attr': 'eduperson_scoped_affiliation',
      'ues_entitlement_attr': 'eduperson_entitlement'
    }

    expected_result = [
        {'ues_cn_attr': 'cn'}
    ]

    result = TEST_INSTANCE._UpdateUserExtSource__get_attributes_to_update(
        attrs_from_perun,
        CONFIG['attr_map'],
        CONFIG['array_to_string_conversion'],
        CONFIG["append_only_attrs"],
        ATTRIBUTES
    )

    assert result == expected_result


@patch(
    "satosacontrib.perun.micro_services.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__find_user_ext_source" # noqa e501
)
def test_run_error(mock_request_1):
    data_to_conversion = {
        "attributes": CONFIG['user_identifiers'],
        "attr_map": CONFIG['attr_map'],
        "attrs_to_conversion": CONFIG['array_to_string_conversion'],
        "append_only_attrs": CONFIG['append_only_attrs'],
        "perun_user_id": 1,
        "auth_info": {
            "issuer": "id"
        }
    }

    TEST_INSTANCE._UpdateUserExtSource__find_user_ext_source = MagicMock(
        return_value=None
    )

    error_msg = 'UpdateUserExtSource' + 'There is no UserExtSource that' \
                ' could be used for user ' \
                + str(data_to_conversion['perun_user_id']) \
                + ' and IdP ' + data_to_conversion['auth_info']['issuer']

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._UpdateUserExtSource__run(
            data_to_conversion
        )
        assert str(error.value.args[0]) == error_msg


@patch(
    "satosacontrib.perun.micro_services.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__find_user_ext_source" # noqa e501
)
@patch(
    "satosacontrib.perun.micro_services.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__get_attributes_from_perun" # noqa e501
)
@patch(
    "satosacontrib.perun.micro_services.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__get_attributes_to_update" # noqa e501
)
@patch(
    "satosacontrib.perun.micro_services.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__update_user_ext_source" # noqa e501
)
def test_run(mock_request_1, mock_request_2, mock_request_3, mock_request_4):
    data_to_conversion = {
        "attributes": CONFIG['user_identifiers'],
        "attr_map": CONFIG['attr_map'],
        "attrs_to_conversion": CONFIG['array_to_string_conversion'],
        "append_only_attrs": CONFIG['append_only_attrs'],
        "perun_user_id": 1,
        "auth_info": {
            "issuer": "id"
        }
    }

    TEST_INSTANCE._UpdateUserExtSource__find_user_ext_source = MagicMock(
        return_value=EXT_SOURCE
    )
    TEST_INSTANCE._UpdateUserExtSource__get_attributes_from_perun = MagicMock(
        return_value=None
    )
    TEST_INSTANCE._UpdateUserExtSource__get_attributes_to_update = MagicMock(
        return_value=None
    )
    TEST_INSTANCE._UpdateUserExtSource__update_user_ext_source = MagicMock(
        return_value=True
    )

    result = TEST_INSTANCE._UpdateUserExtSource__run(
        data_to_conversion
    )

    assert not result


@patch('threading.Thread.start')
@patch('satosa.micro_services.base.ResponseMicroService.process')
def test_process(mock_request_1, mock_request_2):
    threading.Thread.start = MagicMock(
        return_value=None
    )
    ResponseMicroService.process = MagicMock(
        return_value=None
    )

    _ = TEST_INSTANCE.process(TestContext(), TestData(DATA, {'example_user_id': '1'})) # noqa
    threading.Thread.start.assert_called()
    ResponseMicroService.process.assert_called()
