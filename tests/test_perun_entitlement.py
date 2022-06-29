from perun.connector.adapters.AdaptersManager import AdaptersManager
from perun.connector.models.User import User
from perun.connector.models.Group import Group
from perun.connector.models.VO import VO
from satosa.internal import InternalData
from satosa.context import Context
from satosacontrib.perun.utils.ConfigStore import ConfigStore
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


class TestData(InternalData):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.requester = None


class TestContext(Context):
    def __init__(self):
        super().__init__()


TEST_CONTEXT = TestContext()

CONFIG = {
    'entitlementExtended': False,
    'global_cfg_path': 'path',
    'groupNameAARC': 'groupNameAARC',
    'groupMapping':
        {
            'entityID1':
                {
                    'group1': 'mappedGroup1',
                    'group2': 'mappedGroup2'
                },
            'entityID2':
                {
                    'group1': 'mappedGroup1'
                },
            "entityID3":
                {
                    'defaultgroup': 'defaultGroupMapped'
                }
        },
    'entitlementPrefix': 'prefix:',
    'entitlementAuthority': 'authority'
}

CONFIG_EXTENDED = {
    'entitlementExtended': True,
    'global_cfg_path': 'path',
    'groupNameAARC': 'groupNameAARC',
    'groupMapping':
        {
            'entityID1':
                {
                    'group1': 'mappedGroup1',
                    'group2': 'mappedGroup2'
                },
            'entityID2':
                {
                    'group1': 'mappedGroup1'
                },
            "entityID3":
                {
                    'defaultgroup': 'defaultGroupMapped'
                }
        },
    'entitlementPrefix': 'prefix:',
    'entitlementAuthority': 'authority'
}

CONFIG_2 = {
    'entitlementExtended': 'true',
    'global_cfg_path': 'path',
    'groupNameAARC': 'groupNameAARC',
    'groupMapping':
        {
            'entityID1':
                {
                    'group1': 'mappedGroup1',
                    'group2': 'mappedGroup2'
                },
            'entityID2':
                {
                    'group1': 'mappedGroup1'
                },
            "entityID3":
                {
                    'defaultgroup': 'defaultGroupMapped'
                }
        },
    'entitlementPrefix': None,
    'entitlementAuthority': 'authority'
}

CONFIG_3 = {
    'entitlementExtended': 'true',
    'global_cfg_path': 'path',
    'groupNameAARC': 'groupNameAARC',
    'groupMapping':
        {
            'entityID1':
                {
                    'group1': 'mappedGroup1',
                    'group2': 'mappedGroup2'
                },
            'entityID2':
                {
                    'group1': 'mappedGroup1'
                },
            "entityID3":
                {
                    'defaultgroup': 'defaultGroupMapped'
                }
        },
    'entitlementPrefix': 'prefix:',
    'entitlementAuthority': None
}

GLOBAL_CONFIG = {
    'eduPersonEntitlement': 'entitlement',
    'outputAttrName': 'outputAttr',
    'releaseForwardedEntitlement': 'releaseForwardedEntitlement',
    'forwardedEduPersonEntitlement': 'forwardedEduPersonEntitlement',
    'entityID': 'entityID1',
    'attr_cfg_path': 'path'
}


class Loader:
    def __init__(self, config, global_config, attr_map):
        self.config = config
        self.global_config = global_config
        self.attr_map = attr_map

    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_global_cfg")
    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_attributes_map") # noqa e501
    @patch("perun.connector.adapters.AdaptersManager.AdaptersManager.__init__") # noqa e501
    def create_mocked_instance(self, mock_request, mock_request2, mock_request3): # noqa e501
        ConfigStore.get_global_cfg = MagicMock(return_value=self.global_config) # noqa e501
        ConfigStore.get_attributes_map = MagicMock(return_value=self.attr_map)
        AdaptersManager.__init__ = MagicMock(return_value=None)

        return PerunEntitlement(self.config, 'PerunEnsureMember', 'BaseUrl')


TEST_INSTANCE = Loader(CONFIG, GLOBAL_CONFIG, None).create_mocked_instance() # noqa e501
TEST_INSTANCE_WITHOUT_PREFIX = Loader(CONFIG_2, GLOBAL_CONFIG, None).create_mocked_instance() # noqa e501
TEST_INSTANCE_WITHOUT_AUTHORITY = Loader(CONFIG_3, GLOBAL_CONFIG, None).create_mocked_instance() # noqa e501


def test_map_group_name():
    group_name_1 = 'group1'
    group_name_2 = 'group2'
    not_existing_group = 'group420'

    result_1 = 'mappedGroup1'
    result_2 = 'mappedGroup2'
    result_3 = 'prefix:group:group420'

    assert TEST_INSTANCE._PerunEntitlement__map_group_name(group_name_1, 'entityID1') == result_1 # noqa e501
    assert TEST_INSTANCE._PerunEntitlement__map_group_name(group_name_2, 'entityID1') == result_2 # noqa e501
    assert TEST_INSTANCE._PerunEntitlement__map_group_name(not_existing_group, 'entityID1') == result_3 # noqa e501


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

    for capability in TEST_INSTANCE._PerunEntitlement__get_capabilities(TestData(DATA)): # noqa e501
        assert capability in result


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_resource_capabilities_by_rp_id") # noqa e501
def test_get_capabilities_exception(mock_request_1):
    AdaptersManager.get_resource_capabilities_by_rp_id = MagicMock(
        side_effect=[Exception("sth went wrong")]
    )

    assert TEST_INSTANCE._PerunEntitlement__get_capabilities(TestData(DATA)) == [] # noqa e501


def test_get_forwarded_edu_person_entitlement_user_missing():
    assert not TEST_INSTANCE._PerunEntitlement__get_forwarded_edu_person_entitlement(TestData(DATA_WITHOUT_USER)) # noqa e501


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_user_ext_source_attributes") # noqa e501
def test_get_forwarded_edu_person_entitlement(mock_request):
    ext_src_attrs = {
        'attr1': 'this_is_entitlement',
        'attr2': 'attr2',
        'attr3': 'attr3'
    }

    result = ['this_is_entitlement']
    AdaptersManager.get_user_ext_source_attributes = MagicMock(
        return_value=ext_src_attrs
    )

    assert TEST_INSTANCE._PerunEntitlement__get_forwarded_edu_person_entitlement(TestData(DATA)) == result # noqa e501


def test_get_edu_person_entitlement_extended():
    result = ['prefix:groupuuid#authority',
              'prefix:groupAttributesuuid?=displayName=group1#authority',
              'prefix:groupuuid#authority',
              'prefix:groupAttributesuuid?=displayName=group2#authority']


    assert TEST_INSTANCE._PerunEntitlement__get_edu_person_entitlement_extended(TestData(DATA)) == result # noqa e501


def test_get_edu_person_entitlement():
    result = ['prefix:groupgroup1#authority',
              'prefix:groupgroup2#authority']

    assert TEST_INSTANCE._PerunEntitlement__get_edu_person_entitlement(TestData(DATA)) == result # noqa e501


def test_get_edu_person_entitlement_exception():
    expected_error_message = 'perun:PerunEntitlement: missing ' \
                             'mandatory configuration options ' \
                             '\'groupNameAuthority\' ' \
                             'or \'groupNamePrefix\'.'

    with pytest.raises(Exception) as error:
        _ = TEST_INSTANCE_WITHOUT_PREFIX._PerunEntitlement__get_edu_person_entitlement(TestData(DATA)) # noqa e501

    assert str(error.value.args[0]) == expected_error_message

    with pytest.raises(Exception) as error:
        _ = TEST_INSTANCE_WITHOUT_AUTHORITY._PerunEntitlement__get_edu_person_entitlement(TestData(DATA)) # noqa e501

    assert str(error.value.args[0]) == expected_error_message
