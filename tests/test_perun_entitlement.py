from perun.connector.adapters.AdaptersManager import AdaptersManager
from perun.connector.models.User import User
from perun.connector.models.Group import Group
from perun.connector.models.VO import VO
from tests.test_microservice_loader import Loader, TestContext, TestData
from satosacontrib.perun.micro_services.perun_entitlement import PerunEntitlement # noqa e501
from unittest.mock import patch, MagicMock

import pytest


TEST_VO = VO(1, 'vo', 'vo_short_name')
TEST_GROUP_1 = Group(1, TEST_VO, 'uuid', 'group1', 'group1', '')
TEST_GROUP_2 = Group(2, TEST_VO, 'uuid', 'group2', 'group2', '')

DATA = {
    'perun': {
        'groups': [TEST_GROUP_1, TEST_GROUP_2],
        'user': User(1, 'name')
    },
    'attributes': {}
}

DATA_WITHOUT_USER = {
    'perun': {
        'groups': ['grp1', 'grp2'],
    }
}

TEST_CONTEXT = TestContext()

CONFIG = {
    'entitlement_extended': False,
    'global_cfg_path': 'path',
    'group_name_AARC': 'group_name_AARC',
    'group_mapping':
        {
            'entity_id_1':
                {
                    'group1': 'mapped_group1',
                    'group2': 'mapped_group2'
                },
            'entity_id_2':
                {
                    'group1': 'mapped_group1'
                },
            "entity_id_3":
                {
                    'default_group': 'default_group_mapped'
                }
        },
    'entitlement_prefix': 'prefix:',
    'entitlement_authority': 'authority'
}

CONFIG_EXTENDED = {
    'entitlement_extended': True,
    'global_cfg_path': 'path',
    'group_name_AARC': 'group_name_AARC',
    'group_mapping':
        {
            'entity_id_1':
                {
                    'group1': 'mapped_group1',
                    'group2': 'mapped_group2'
                },
            'entity_id_2':
                {
                    'group1': 'mapped_group1'
                },
            "entity_id_3":
                {
                    'default_group': 'default_group_mapped'
                }
        },
    'entitlement_prefix': 'prefix:',
    'entitlement_authority': 'authority'
}

CONFIG_2 = {
    'entitlement_extended': 'true',
    'global_cfg_path': 'path',
    'group_name_AARC': 'groupN=_name_AARC',
    'group_mapping':
        {
            'entity_id_1':
                {
                    'group1': 'mapped_group1',
                    'group2': 'mapped_group2'
                },
            'entity_id_2':
                {
                    'group1': 'mapped_group1'
                },
            "entity_id_3":
                {
                    'default_group': 'default_group_mapped'
                }
        },
    'entitlement_prefix': None,
    'entitlement_authority': 'authority'
}

CONFIG_3 = {
    'entitlement_extended': 'true',
    'global_cfg_path': 'path',
    'group_name_AARC': 'group_name_AARC',
    'group_mapping':
        {
            'entity_id_1':
                {
                    'group1': 'mapped_group1',
                    'group2': 'mapped_group2'
                },
            'entity_id_2':
                {
                    'group1': 'mapped_group1'
                },
            "entity_id_3":
                {
                    'default_group': 'default_group_mapped'
                }
        },
    'entitlement_prefix': 'prefix:',
    'entitlement_authority': None
}

TEST_INSTANCE = Loader(CONFIG, PerunEntitlement.__name__).create_mocked_instance() # noqa e501
TEST_INSTANCE_WITHOUT_PREFIX = Loader(CONFIG_2, PerunEntitlement.__name__).create_mocked_instance() # noqa e501
TEST_INSTANCE_WITHOUT_AUTHORITY = Loader(CONFIG_3, PerunEntitlement.__name__).create_mocked_instance() # noqa e501


def test_map_group_name():
    group_name_1 = 'group1'
    group_name_2 = 'group2'
    not_existing_group = 'group420'

    result_1 = 'mapped_group1'
    result_2 = 'mapped_group2'
    result_3 = 'prefix:group:group420'

    assert TEST_INSTANCE._PerunEntitlement__map_group_name(group_name_1, 'entity_id_1') == result_1 # noqa e501
    assert TEST_INSTANCE._PerunEntitlement__map_group_name(group_name_2, 'entity_id_1') == result_2 # noqa e501
    assert TEST_INSTANCE._PerunEntitlement__map_group_name(not_existing_group, 'entity_id_1') == result_3 # noqa e501


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_resource_capabilities_by_rp_id") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_facility_capabilities_by_rp_id") # noqa e501
def test_get_capabilities(mock_request_1, mock_request_2):
    resource_capabilities = ['res_cap_1', 'res_cap_2']
    facility_capabilities = ['fac_cap_1', 'fac_cap_2']

    AdaptersManager.get_resource_capabilities_by_rp_id = MagicMock(
        return_value=resource_capabilities
    )
    AdaptersManager.get_facility_capabilities_by_rp_id = MagicMock(
        return_value=facility_capabilities
    )

    result = ['prefix:fac_cap_2#authority', 'prefix:fac_cap_1#authority',
              'prefix:res_cap_1#authority', 'prefix:res_cap_2#authority']

    for capability in TEST_INSTANCE._PerunEntitlement__get_capabilities(TestData(DATA, None)): # noqa e501
        assert capability in result


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_resource_capabilities_by_rp_id") # noqa e501
def test_get_capabilities_exception(mock_request_1):
    AdaptersManager.get_resource_capabilities_by_rp_id = MagicMock(
        side_effect=[Exception("sth went wrong")]
    )

    assert TEST_INSTANCE._PerunEntitlement__get_capabilities(TestData(DATA, None)) == [] # noqa e501


def test_get_forwarded_edu_person_entitlement_user_missing():
    attrs = {
        'example_user_id': 'example_user_id'
    }

    test_data = TestData(data=DATA_WITHOUT_USER, attributes=attrs)
    assert not TEST_INSTANCE._PerunEntitlement__get_forwarded_edu_person_entitlement(test_data) # noqa e501


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_attributes") # noqa e501
def test_get_forwarded_edu_person_entitlement(mock_request):
    ext_src_attrs = {
        'attr1': 'this_is_entitlement',
        'attr2': 'attr2',
        'attr3': 'attr3'
    }

    attrs = {
        'example_user_id': 'example_user_id'
    }

    test_data = TestData(data=DATA, attributes=attrs)

    result = ['this_is_entitlement']
    AdaptersManager.get_user_attributes = MagicMock(
        return_value=ext_src_attrs
    )

    assert TEST_INSTANCE._PerunEntitlement__get_forwarded_edu_person_entitlement(test_data) == result # noqa e501


def test_get_edu_person_entitlement_extended():
    expected_result = ['prefix:groupuuid#authority',
                       'prefix:groupAttributes:uuid?=displayName=group1#authority', # noqa
                       'prefix:groupuuid#authority',
                       'prefix:groupAttributes:uuid?=displayName=group2#authority'] # noqa

    result = TEST_INSTANCE._PerunEntitlement__get_edu_person_entitlement_extended(TestData(DATA, None)) # noqa

    assert expected_result == result


def test_get_edu_person_entitlement():
    expected_result = ['prefix:group:group1#authority',
                       'prefix:group:group2#authority']

    result = TEST_INSTANCE._PerunEntitlement__get_edu_person_entitlement(TestData(DATA, None)) # noqa

    assert expected_result == result # noqa e501


def test_get_edu_person_entitlement_exception():
    expected_error_message = 'perun:PerunEntitlement: missing ' \
                             'mandatory configuration options ' \
                             '\'groupNameAuthority\' ' \
                             'or \'groupNamePrefix\'.'

    with pytest.raises(Exception) as error:
        _ = TEST_INSTANCE_WITHOUT_PREFIX._PerunEntitlement__get_edu_person_entitlement(TestData(DATA, None)) # noqa e501

    assert str(error.value.args[0]) == expected_error_message

    with pytest.raises(Exception) as error:
        _ = TEST_INSTANCE_WITHOUT_AUTHORITY._PerunEntitlement__get_edu_person_entitlement(TestData(DATA, None)) # noqa e501

    assert str(error.value.args[0]) == expected_error_message
