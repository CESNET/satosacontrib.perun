import logging

from perun.connector.adapters.AdaptersManager import AdaptersManager
from satosa.internal import InternalData
from satosa.context import Context
from satosacontrib.perun.micro_services.perun_ensure_member import PerunEnsureMember # noqa e501
from satosacontrib.perun.utils.ConfigStore import ConfigStore
from perun.connector.models.MemberStatusEnum import MemberStatusEnum
from perun.connector.models.User import User
from perun.connector.models.Group import Group
from perun.connector.models.VO import VO
from unittest.mock import patch, MagicMock


GLOBAL_CONFIG = {
    "attrs_cfg_path": "path",
    "jwk": "key"
}

CONFIG = {
  'global_cfg_path': "path",
  'registerUrl': 'url',
  'callbackParameterName': 'callbackParameterName',
  'voShortName': 'voShortName',
  'groupName': 'groupName',
  'unauthorizedRedirectUrl': 'unauthorized_redirect_url',
  'registrationResultUrl': 'registration_result_url',
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
    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_attributes_map") # noqa e501
    @patch("perun.connector.adapters.AdaptersManager.AdaptersManager.__init__") # noqa e501
    def create_mocked_instance(self, mock_request, mock_request2, mock_request3): # noqa e501
        ConfigStore.get_global_cfg = MagicMock(return_value=self.global_config) # noqa e501
        ConfigStore.get_attributes_map = MagicMock(return_value=self.attr_map)
        AdaptersManager.__init__ = MagicMock(return_value=None)

        return PerunEnsureMember(self.config, None, None)


TEST_INSTANCE = Loader(CONFIG, GLOBAL_CONFIG, ATTR_MAP).create_mocked_instance() # noqa e501
TEST_VO = VO(1, 'test_vo', 'vo')
TEST_GROUP = Group(1, TEST_VO, 'uuid', 'test_group', 'group', '')
TEST_USER = User(1, 'Joe Doe')
TEST_CONTEXT = TestContext()
TEST_DATA = TestData(DATA, ATTRIBUTES)


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
def test_handle_user_valid_in_group(mock_request_1, mock_request_2, caplog):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        return_value=True
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.VALID
    )

    message = 'perun:PerunEnsureMember: User is allowed to continue.'

    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
def test_handle_user_not_in_group_has_registration_form(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        caplog):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        resturn_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.VALID
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.VALID
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=True
    )

    message = 'perun:PerunEnsureMember: User is not valid in group ' \
              'groupName - sending to registration.'
    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
def test_handle_user_in_group_vo_has_registration_form(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        resturn_value=True
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=None
    )

    message = 'perun:PerunEnsureMember: User is not member of vo ' \
              'voShortName - sending to registration.'
    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
def test_handle_user_vo_and_group_have_registratiion_form(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        resturn_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=True
    )

    message = 'perun:PerunEnsureMember: User is not valid in group ' \
              'groupName - sending to registration.'

    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
def test_handle_user_expired_user(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        resturn_value=True
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.EXPIRED
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=None
    )

    message = 'perun:PerunEnsureMember: User is expired ' \
              '- sending to registration.'

    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
def test_handle_user_expired_not_in_group(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        resturn_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.EXPIRED
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=True
    )

    message = 'perun:PerunEnsureMember: User is expired and not in group ' \
              'groupName - sending to registration.'

    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_by_vo_short_name") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
def test_handle_user_unauthorized(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        resturn_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.INVALID
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.INVALID
    )
    AdaptersManager.has_registration_form_by_vo_short_name = MagicMock(
        return_value=False
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=False
    )

    message = 'perun:PerunEnsureMember: User is not valid in vo/group and ' \
              'cannot be sent to the registration - sending to unauthorized'

    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result
