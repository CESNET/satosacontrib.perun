from perun.connector.adapters.AdaptersManager import AdaptersManager
from satosa.exception import SATOSAError
from satosacontrib.perun.micro_services.perun_attributes_microservice import PerunAttributes # noqa
from tests.test_microservice_loader import Loader, TestData, TestContext
from unittest.mock import patch, MagicMock

import pytest


CONFIG = {
  'mode': 'FULL',
  'global_cfg_path': "path",
  'attr_map': {
    'eduperson_unique_id': "eduperson_unique_id",
    'eduperson_principal_name': 'eduperson_principal_name',
    'eduperson_targeted_id': 'eduperson_targeted_id',
    'name_id': 'name_id',
    'uid': 'uid',
    'random_attr': 'attr',
    'random_attr2': 'attr2'
  }
}

CONFIG_ERROR = {
  'mode': 'FULL',
  'global_cfg_path': "path",
  'attr_map': {
    'eduperson_unique_id': "eduperson_unique_id",
    'eduperson_principal_name': 'eduperson_principal_name',
    'eduperson_targeted_id': 'eduperson_targeted_id',
    'name_id': 'name_id',
    'uid': 'uid',
    'random_attr': 1,
  }
}

ATTRIBUTES = {
    'uid': 'uid',
    'name_id': 'name_id',
    'eduperson_targeted_id': 'eduperson_targeted_id',
    'eduperson_principal_name': 'eduperson_principal_name',
    'eduperson_unique_id': 'eduperson_unique_id'
}

DATA = {}
TEST_INSTANCE = Loader(CONFIG, PerunAttributes.__name__).create_mocked_instance() # noqa e501
TEST_INSTANCE_ERROR =  Loader(CONFIG_ERROR, PerunAttributes.__name__).create_mocked_instance() # noqa e501


@patch(
    "perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_attributes" # noqa e501
)
def test_process_attrs(mock_request):
    user_attrs = {
        'eduperson_unique_id': "unique_id",
        'eduperson_principal_name': 'principal_name',
        'eduperson_targeted_id': 'targeted_id',
        'name_id': 'name',
        'uid': 1,
        'random_attr': [1, 2],
        'random_attr2': {
            "1": 1
        }
    }

    expected_result = {
        'eduperson_unique_id': ['unique_id'],
        'eduperson_principal_name': ['principal_name'],
        'eduperson_targeted_id': ['targeted_id'],
        'name_id': ['name'],
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
        'random_attr': 1.1,
    }

    user_attrs_2 = {
        'random_attr': 1
    }

    AdaptersManager.get_user_attributes = MagicMock(
        return_value=user_attrs
    )

    error_message = 'PerunAttributes' + '- Unsupported attribute type. ' \
                                        'Attribute name: ' + 'random_attr' + \
                    ', Supported types: null, string, int, dict, list.'

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE._PerunAttributes__process_attrs(None, None)
        assert str(error.value.args[0]) == error_message

    AdaptersManager.get_user_attributes = MagicMock(
        return_value=user_attrs_2
    )

    error_message = 'PerunAttributes' + '- Unsupported attribute type. ' \
                                        'Attribute name: ' + 'random_attr' + \
                    ', Supported types: string, dict.'

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE_ERROR._PerunAttributes__process_attrs(None, None)
        assert str(error.value.args[0]) == error_message


def test_process_error():
    error_message = "PerunAttributes: " \
                    "Missing mandatory attribute " \
                    "'example_user_id' " \
                    "in data.attributes. Hint: Did you " \
                    "configured PerunUser microservice " \
                    "before this microservice?" \

    with pytest.raises(SATOSAError) as error:
        TEST_INSTANCE.process(TestContext(), TestData(DATA, ATTRIBUTES))
        print(error.value.args[0])
        assert str(error.value.args[0]) == error_message
