import threading

from perun.connector.adapters.AdaptersManager import AdaptersManager
from perun.connector.models.User import User
from perun.connector.models.UserExtSource import UserExtSource
from satosacontrib.perun.micro_services.update_user_ext_source import UpdateUserExtSource # noqa e501
from satosa.internal import InternalData
from satosa.context import Context
from satosa.exception import SATOSAError
from satosa.micro_services.base import ResponseMicroService
from satosacontrib.perun.utils.ConfigStore import ConfigStore
from unittest.mock import patch, MagicMock

import pytest


GLOBAL_CONFIG = {
    "attrs_cfg_path": "path",
    "perun_user_id_attr": "user_id"
}

CONFIG = {
  'arrayToStringConversion': {
    'attribute1': 'value',
    'attribute2': 1,
    'attribute3': True,
    'attribute4': ['value1', 'value2'],
    'attribute5': {
       'key': 'value'
    },
  },
  'appendOnlyAttrs': {
    'attribute1': 'value',
    'attribute2': 1,
    'attribute3': True,
    'attribute4': ['value1', 'value2'],
    'attribute5': {
       'key': 'value'
    },
  },
  'userIdentifiers': {
      'eduPersonUniqueId': {"eduPersonUniqueId": 1},
      'eduPersonPrincipalName': {'eduPersonPrincipalName': 2},
      'eduPersonTargetedID': {'eduPersonTargetedID': 3},
      'nameid': {'nameid': 4},
      'uid': {'uid': 5}
  },
  'global_cfg_path': "path"
}

ATTRIBUTES = {
    'uid': 'uid',
    'nameid': 'nameid',
    'eduPersonTargetedID': 'eduPersonTargetedID',
    'eduPersonPrincipalName': 'eduPersonPrincipalName',
    'eduPersonUniqueId': 'eduPersonUniqueId'
}

DATA = {}

ATTR_MAP = {
  'eduPersonUniqueId': "eduPersonUniqueId",
  'eduPersonPrincipalName': 'eduPersonPrincipalName',
  'eduPersonTargetedID': 'eduPersonTargetedID',
  'nameid': 'nameid',
  'uid': 'uid'
}


class TestContext(Context):
    def __init__(self):
        super().__init__()


class TestData(InternalData):
    def __init__(self, data, attributes):
        super().__init__()
        self.data = data
        self.attributes = attributes
        self.auth_info = None


class Loader:
    def __init__(self, config, global_config, attr_map):
        self.config = config
        self.global_config = global_config
        self.attr_map = attr_map

    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_global_cfg") # noqa e501
    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_attributes_map") # noqa e501
    @patch("perun.connector.adapters.AdaptersManager.AdaptersManager.__init__") # noqa e501
    def create_mocked_instance(self, mock_request, mock_request2, mock_request3): # noqa e501
        ConfigStore.get_global_cfg = MagicMock(return_value=self.global_config) # noqa e501
        ConfigStore.get_attributes_map = MagicMock(return_value=self.attr_map)
        AdaptersManager.__init__ = MagicMock(return_value=None)

        return UpdateUserExtSource(self.config, None, None)


TEST_INSTANCE = Loader(CONFIG, GLOBAL_CONFIG, ATTR_MAP).create_mocked_instance() # noqa e501
TEST_DATA = TestData(DATA, ATTRIBUTES)
USER = User(1, "Joe Doe")
EXT_SOURCE = UserExtSource(1, "ext_source", "login", USER)


@patch(
    "microservices.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__get_user_ext_source" # noqa e501
)
def test_find_user_ext_source(mock_request_1):
    TEST_INSTANCE._UpdateUserExtSource__find_user_ext_source = MagicMock(return_value=EXT_SOURCE) # noqa e501

    assert TEST_INSTANCE._UpdateUserExtSource__find_user_ext_source(
        "name", ATTRIBUTES, CONFIG['userIdentifiers']
    ) == EXT_SOURCE


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_ext_source_attributes" # noqa e501
)
def test_get_attributes_from_perun_error(mock_request_1):
    attrs_without_name = {
        "attr": 1
    }

    AdaptersManager.get_user_ext_source_attributes = MagicMock(
        return_value=None
    )

    error_message = "UpdateUserExtSource" + "Getting attributes for UES " \
                    "was not successful."
    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._UpdateUserExtSource__get_attributes_from_perun(
            EXT_SOURCE
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
      'eduPersonUniqueId': 1,
      'eduPersonPrincipalName': 'newEduPersonPrincipalName',
      'eduPersonTargetedID': 'newEduPersonTargetedID',
      'nameid': 'newNameid',
      'uid': 'newUid'
    }

    expected_result = [
        {'eduPersonUniqueId': 'eduPersonUniqueId'},
        {'eduPersonPrincipalName': 'eduPersonPrincipalName'},
        {'eduPersonTargetedID': 'eduPersonTargetedID'},
        {'nameid': 'nameid'},
        {'uid': 'uid'}
    ]

    result = TEST_INSTANCE._UpdateUserExtSource__get_attributes_to_update(
        attrs_from_perun,
        ATTR_MAP,
        ATTRIBUTES,
        CONFIG["appendOnlyAttrs"],
        CONFIG['userIdentifiers']
    )

    assert result == expected_result


@patch(
    "satosacontrib.perun.micro_services.update_user_ext_source.UpdateUserExtSource._UpdateUserExtSource__find_user_ext_source" # noqa e501
)
def test_run_error(mock_request_1):
    data_to_conversion_1 = {
        "attributes": CONFIG['userIdentifiers'],
        "attrMap": ATTR_MAP,
        "attrsToConversion": CONFIG['arrayToStringConversion'],
        "appendOnlyAttrs": CONFIG['appendOnlyAttrs'],
        "perunUserId": 1,
        "auth_info": {
            "issuer": None
        }
    }

    data_to_conversion_2 = {
        "attributes": CONFIG['userIdentifiers'],
        "attrMap": ATTR_MAP,
        "attrsToConversion": CONFIG['arrayToStringConversion'],
        "appendOnlyAttrs": CONFIG['appendOnlyAttrs'],
        "perunUserId": 1,
        "auth_info": {
            "issuer": "id"
        }
    }

    error_msg = "UpdateUserExtSource" + 'Invalid attributes from IdP ' \
                '- Attribute \' is empty'

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._UpdateUserExtSource__run(
            data_to_conversion_1
        )
        assert str(error.value.args[0]) == error_msg

    TEST_INSTANCE._UpdateUserExtSource__find_user_ext_source = MagicMock(
        return_value=None
    )

    error_msg = 'UpdateUserExtSource' + 'There is no UserExtSource that' \
                ' could be used for user ' \
                + str(data_to_conversion_2['perunUserId']) \
                + ' and IdP ' + data_to_conversion_2['auth_info']['issuer']

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._UpdateUserExtSource__run(
            data_to_conversion_2
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
        "attributes": CONFIG['userIdentifiers'],
        "attrMap": ATTR_MAP,
        "attrsToConversion": CONFIG['arrayToStringConversion'],
        "appendOnlyAttrs": CONFIG['appendOnlyAttrs'],
        "perunUserId": 1,
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

    _ = TEST_INSTANCE.process(TestContext(), TestData(DATA, {'user_id': '1'}))
    threading.Thread.start.assert_called()
    ResponseMicroService.process.assert_called()
