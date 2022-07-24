from perun.connector.adapters.AdaptersManager import AdaptersManager
from satosa.internal import InternalData
from satosa.context import Context
from satosa.exception import SATOSAError
from satosacontrib.perun.micro_services.perun_attributes import PerunAttributes
from satosacontrib.perun.utils.ConfigStore import ConfigStore
from unittest.mock import patch, MagicMock

import pytest


GLOBAL_CONFIG = {
    "attrs_cfg_path": "path",
    "perun_user_id_attr": "user_id",
    "perunId": 1
}

CONFIG = {
  'mode': 'FULL',
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
    'uid': 'uid',
    'randomAttr': 'attr',
    'randomAttr2': 'attr2'
}

ATTR_MAP_ERROR = {
    'eduPersonUniqueId': "eduPersonUniqueId",
    'eduPersonPrincipalName': 'eduPersonPrincipalName',
    'eduPersonTargetedID': 'eduPersonTargetedID',
    'nameid': 'nameid',
    'uid': 'uid',
    'randomAttr': 1,
}


class TestContext(Context):
    def __init__(self):
        super().__init__()


class TestData(InternalData):
    def __init__(self, our_data, our_attributes):
        super().__init__(our_data, our_attributes)
        self.data = our_data
        self.attributes = our_attributes


class Loader:
    def __init__(self, config, global_config, attr_map):
        self.config = config
        self.global_config = global_config
        self.attr_map = attr_map

    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_global_cfg")
    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_attributes_map")
    @patch("perun.connector.adapters.AdaptersManager.AdaptersManager.__init__") # noqa e501
    def create_mocked_instance(self, mock_request, mock_request2, mock_request3): # noqa e501
        ConfigStore.get_global_cfg = MagicMock(return_value=self.global_config) # noqa e501
        ConfigStore.get_attributes_map = MagicMock(return_value=self.attr_map)
        AdaptersManager.__init__ = MagicMock(return_value=None)

        return PerunAttributes(self.config, None, None)

TEST_INSTANCE = Loader(CONFIG, GLOBAL_CONFIG, ATTR_MAP).create_mocked_instance() # noqa e501
TEST_INSTANCE_ERROR =  Loader(CONFIG, GLOBAL_CONFIG, ATTR_MAP_ERROR).create_mocked_instance() # noqa e501


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_attributes" # noqa e501
)
def test_process_attrs(mock_request):
    user_attrs = {
        'eduPersonUniqueId': "uniqueId",
        'eduPersonPrincipalName': 'principalName',
        'eduPersonTargetedID': 'targetedID',
        'nameid': 'name',
        'uid': 1,
        'randomAttr': [1, 2],
        'randomAttr2': {
            "1": 1
        }
    }

    expected_result = {
        'eduPersonUniqueId': ['uniqueId'],
        'eduPersonPrincipalName': ['principalName'],
        'eduPersonTargetedID': ['targetedID'],
        'nameid': ['name'],
        'uid': [1],
        'attr': [1, 2],
        'attr2': {
            "1": 1
        }
    }

    AdaptersManager.get_user_attributes = MagicMock(
        return_value=user_attrs
    )

    result = TEST_INSTANCE._PerunAttributes__process_attrs(None, None)
    assert result == expected_result


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_attributes" # noqa e501
)
def test_process_attrs_error(mock_request):
    user_attrs = {
        'randomAttr': 1.1,
    }

    user_attrs_2 = {
        'randomAttr': 1
    }

    AdaptersManager.get_user_attributes = MagicMock(
        return_value=user_attrs
    )

    error_message = 'PerunAttributes' + '- Unsupported attribute type. ' \
                                        'Attribute name: ' + 'randomAttr' + \
                    ', Supported types: null, string, int, dict, list.'

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._PerunAttributes__process_attrs(None, None)
        assert str(error.value.args[0]) == error_message

    AdaptersManager.get_user_attributes = MagicMock(
        return_value=user_attrs_2
    )

    error_message = 'PerunAttributes' + '- Unsupported attribute type. ' \
                                        'Attribute name: ' + 'randomAttr' + \
                    ', Supported types: string, dict.'

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE_ERROR._PerunAttributes__process_attrs(None, None)
        assert str(error.value.args[0]) == error_message


def test_process_error():
    error_message = "PerunAttributes: missing mandatory field" \
                    " \'perun.user\' in request. Hint: Did you " \
                    "configured PerunIdentity microservice before " \
                    "this microservice?"

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE.process(TestContext(), TestData(DATA, ATTRIBUTES))
        assert str(error.value.args[0]) == error_message
