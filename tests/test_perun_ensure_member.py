import logging
import pytest

from perun.connector.adapters.AdaptersManager import AdaptersManager
from tests.test_microservice_loader import Loader, TestData, TestContext
from satosa.exception import SATOSAError
from satosacontrib.perun.micro_services.perun_ensure_member import PerunEnsureMember # noqa e501
from perun.connector.models.MemberStatusEnum import MemberStatusEnum
from perun.connector.models.User import User
from perun.connector.models.Group import Group
from perun.connector.models.VO import VO
from satosa.micro_services.base import ResponseMicroService
from unittest.mock import patch, MagicMock


CONFIG = {
  'global_cfg_path': "path",
  'register_url': 'url',
  'callback_parameter_name': 'callback_parameter_name',
  'vo_short_name': 'vo_short_name',
  'group_name': 'group_name',
  'unauthorized_redirect_url': 'unauthorized_redirect_url',
  'registration_result_url': 'registration_result_url',
}

ATTRIBUTES = {
    'uid': 'uid',
    'name_id': 'name_id',
    'eduperson_targeted_id': 'eduperson_targeted_id',
    'eduperson_principal_name': 'eduperson_principal_name',
    'eduperson_unique_id': 'eduperson_unique_id'
}

DATA = {}

TEST_INSTANCE = Loader(CONFIG, PerunEnsureMember.__name__).create_mocked_instance() # noqa e501
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
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_vo") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember.register") # noqa e501
def test_handle_user_not_in_group_has_registration_form(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        mock_request_6,
        caplog):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        return_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.VALID
    )
    AdaptersManager.has_registration_form_vo = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=True
    )
    PerunEnsureMember.register = MagicMock(
        return_value=None
    )

    message = 'perun:PerunEnsureMember: User is not valid in group ' \
              'group_name - sending to registration.'
    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result
        PerunEnsureMember.register.assert_called()


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_vo") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember.register") # noqa e501
def test_handle_user_in_group_vo_has_registration_form(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        mock_request_6,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        return_value=True
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.has_registration_form_vo = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=None
    )
    PerunEnsureMember.register = MagicMock(
        return_value=None
    )

    message = 'perun:PerunEnsureMember: User is not member of vo ' \
              'vo_short_name - sending to registration.'
    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result
        PerunEnsureMember.register.assert_called()


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_vo") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember.register") # noqa e501
def test_handle_user_vo_and_group_have_registratiion_form(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        mock_request_6,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        return_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.has_registration_form_vo = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=True
    )
    PerunEnsureMember.register = MagicMock(
        return_value=None
    )

    message = 'perun:PerunEnsureMember: User is not member of vo ' + \
              'vo_short_name and is not in group group_name - sending ' \
              'to registration.'

    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result
        PerunEnsureMember.register.assert_called()


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_vo") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember.register") # noqa e501
def test_handle_user_expired_user(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        mock_request_6,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        return_value=True
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.EXPIRED
    )
    AdaptersManager.has_registration_form_by_vo = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=None
    )
    PerunEnsureMember.register = MagicMock(
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
        PerunEnsureMember.register.assert_called()


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_vo") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember.register") # noqa e501
def test_handle_user_expired_not_in_group(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        mock_request_6,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        return_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=None
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.EXPIRED
    )
    AdaptersManager.has_registration_form_by_vo = MagicMock(
        return_value=True
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=True
    )
    PerunEnsureMember.register = MagicMock(
        return_value=None
    )

    message = 'perun:PerunEnsureMember: User is expired and not in group ' \
              'group_name - sending to registration.'

    with caplog.at_level(logging.DEBUG):
        result = TEST_INSTANCE._PerunEnsureMember__handle_user(
            TEST_USER,
            TEST_VO,
            TEST_DATA,
            TEST_CONTEXT
        )
        assert message in caplog.text
        assert not result
        PerunEnsureMember.register.assert_called()


@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__is_user_in_group") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_member_status_by_user_and_vo") # noqa e501
@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.has_registration_form_vo") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__group_has_registration_form") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember.unauthorized") # noqa e501
def test_handle_user_unauthorized(
        mock_request_1,
        mock_request_2,
        mock_request_3,
        mock_request_4,
        mock_request_5,
        mock_request_6,
        caplog
):
    PerunEnsureMember._PerunEnsureMember__is_user_in_group = MagicMock(
        return_value=False
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.INVALID
    )
    AdaptersManager.get_member_status_by_user_and_vo = MagicMock(
        return_value=MemberStatusEnum.INVALID
    )
    AdaptersManager.has_registration_form_vo = MagicMock(
        return_value=False
    )
    TEST_INSTANCE._PerunEnsureMember__group_has_registration_form = MagicMock(
        return_value=False
    )
    PerunEnsureMember.unauthorized = MagicMock(
        return_value=None
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
        PerunEnsureMember.unauthorized.assert_called()


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo") # noqa e501
def test_process_error(mock_request):
    data_wrong = {
        'example_user_id': None
    }

    data_correct = {
        'example_user_id': 1
    }

    expected_error_message = \
        "perun:PerunEnsureMember: " \
        + "Missing mandatory attribute " \
        + "'example_user_id' " \
        + "in data.attributes. Hint: Did you " \
        + "configured PerunUser microservice " \
        + "before this microservice?"

    with pytest.raises(SATOSAError) as error:
        _ = TEST_INSTANCE.process(TEST_CONTEXT, TestData(DATA, data_wrong))  # noqa e501

    assert str(error.value.args[0]) == expected_error_message

    AdaptersManager.get_vo = MagicMock(
        return_value=None
    )

    expected_error_message = 'perun:PerunEnsureMember: VO with' \
                             ' vo_short_name \'vo_short_name\' not found.'

    with pytest.raises(SATOSAError) as error:
        _ = TEST_INSTANCE.process(TEST_CONTEXT, TestData(DATA, data_correct)) # noqa e501  # noqa e501

    assert str(error.value.args[0]) == expected_error_message


@patch("perun.connector.adapters.AdaptersManager.AdaptersManager.get_vo") # noqa e501
@patch("satosacontrib.perun.micro_services.perun_ensure_member.PerunEnsureMember._PerunEnsureMember__handle_user") # noqa e501
@patch("satosa.micro_services.base.ResponseMicroService.process")
def test_process(mock_request_1, mock_request_2, mock_request_3):
    data = {
        'example_user_id': 1
    }

    AdaptersManager.get_vo = MagicMock(
        return_value='not None'
    )

    PerunEnsureMember._PerunEnsureMember__handle_user = MagicMock(
        return_value=None
    )

    ResponseMicroService.process = MagicMock(
        return_value=None
    )

    _ = TEST_INSTANCE.process(TEST_CONTEXT, TestData(DATA, data))
    PerunEnsureMember._PerunEnsureMember__handle_user.assert_called()
    ResponseMicroService.process.assert_called()
