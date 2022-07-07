from perun.connector.utils.Logger import Logger
from perun.connector.models.MemberStatusEnum import MemberStatusEnum
from perun.connector.adapters.AdaptersManager import AdaptersManager
from perun.connector.adapters.AdaptersManager import AdaptersManagerNotExistsException # noqa e501
from perun.connector.adapters.AdaptersManager import AdaptersManagerException
from satosa.micro_services.base import ResponseMicroService
from satosa.exception import SATOSAError
from satosa.response import Redirect
from satosacontrib.perun.utils.ConfigStore import ConfigStore
from satosacontrib.perun.utils.Utils import Utils


class PerunEnsureMember(ResponseMicroService):
    """
    This Satosa microservice checks member status
    of the user and calls registration if needed
    """
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.LOG_PREFIX = 'perun:PerunEnsureMember: '
        self.REGISTER_URL = 'registerUrl'
        self.VO_SHORT_NAME = 'voShortName'
        self.GROUP_NAME = 'groupName'
        self.CALLBACK_PARAMETER_NAME = 'callbackParameterName'
        self.PARAM_REGISTRATION_URL = 'registrationUrl'

        self.__logger = Logger.get_logger(self.__class__.__name__)

        self.__config = config
        self.__global_cfg = ConfigStore.get_global_cfg(
            config["global_cfg_path"]
        )
        self.__attr_map_cfg = ConfigStore.get_attributes_map(
            self.__global_cfg["attrs_cfg_path"]
        )
        self.__adapters_manager = AdaptersManager(
            self.__global_cfg,
            self.__attr_map_cfg
        )

        self.__signing_cfg = self.__global_cfg["jwk"]

        if self.REGISTER_URL not in self.__config \
                or not self.__config[self.REGISTER_URL]:
            raise SATOSAError(
                self.LOG_PREFIX + 'Missing configuration option \''
                + self.REGISTER_URL + '\''
            )
        self.__register_url = self.__config[self.REGISTER_URL]

        if self.CALLBACK_PARAMETER_NAME not in self.__config \
                or not self.__config[self.CALLBACK_PARAMETER_NAME]:
            raise SATOSAError(
                self.LOG_PREFIX + 'Missing configuration option \''
                + self.CALLBACK_PARAMETER_NAME + '\''
            )
        self.__callback_param_name = self.__config[self.CALLBACK_PARAMETER_NAME] # noqa e501

        if self.VO_SHORT_NAME not in self.__config \
                or not self.__config[self.VO_SHORT_NAME]:
            raise SATOSAError(
                self.LOG_PREFIX + 'Missing configuration option \''
                + self.VO_SHORT_NAME + '\''
            )
        self.__vo_short_name = self.__config[self.VO_SHORT_NAME]

        self.__group_name = self.__config[self.GROUP_NAME]

        self.__unauthorized_redirect_url = \
            self.__config["unauthorizedRedirectUrl"]

        self.__registration_result_url = self.__config["registrationResultUrl"]

        self.__endpoint = "/process"

    def process(self, context, data):
        """
        This is where the micro service should modify the request / response.
        Subclasses must call this method (or in another way make sure the
        next callable is called).
        @param context: The current context
        @param data: Data to be modified
        """
        if data.data['perun']['user']:
            user = data.data['perun']['user']
        else:
            raise SATOSAError(
                self.LOG_PREFIX + 'Missing mandatory field '
                '\'perun.user\' in request. Hint: Did you '
                'configured PerunIdentity microservice '
                'before this microservice?'
            )
        try:
            vo = self.__adapters_manager.get_vo(short_name=self.__vo_short_name)
        except (AdaptersManagerException, AdaptersManagerNotExistsException) as _:  # noqa e501
            raise SATOSAError(
                self.LOG_PREFIX + 'VO with vo_short_name \''
                + self.__vo_short_name + '\' not found.'
            )

        self.__handle_user(user, vo, data, context)

        return super().process(context, data)

    def __handle_user(self, user, vo, data, context):
        """
        Handles user according to his member status
        @param user: current user
        @param vo: current vo
        @param data: microservice data
        @param context: microservice context
        @return: None
        """
        is_user_in_group = not self.__group_name or self.__is_user_in_group(user, vo) # noqa e501
        member_status = self.__adapters_manager.get_member_status_by_user_and_vo(user, vo) # noqa e501

        if member_status == MemberStatusEnum.VALID and is_user_in_group:
            self.__logger.debug(
                self.LOG_PREFIX + 'User is allowed to continue.'
            )

            return

        member_status = self.__adapters_manager.get_member_status_by_user_and_vo(user, vo)  # noqa e501
        vo_has_registration_form = \
            self.__adapters_manager.has_registration_form_by_vo_short_name(self.__vo_short_name) # noqa e501
        group_has_registration_form = self.__group_has_registration_form(vo) # noqa e501

        if member_status == MemberStatusEnum.VALID and is_user_in_group:
            self.__logger.debug(
                self.LOG_PREFIX + 'User is allowed to continue.'
            )
        elif member_status == MemberStatusEnum.VALID \
                and not is_user_in_group and group_has_registration_form:
            self.__logger.debug(
                self.LOG_PREFIX + 'User is not valid in group ' +
                self.__group_name + ' - sending to registration.'
            )
            self.register(context, data)
        elif not member_status and vo_has_registration_form \
                and is_user_in_group and not group_has_registration_form: # noqa e501
            self.__logger.debug(
                self.LOG_PREFIX + 'User is not member of vo ' +
                self.__vo_short_name + ' - sending to registration.'
            )
            self.register(context, data)
        elif not member_status and vo_has_registration_form and \
                not is_user_in_group and group_has_registration_form:
            self.__logger.debug(
                self.LOG_PREFIX + 'User is not valid in group ' +
                self.__group_name + ' - sending to registration.'
            )
            self.register(context, data, self.__group_name)
        elif member_status == MemberStatusEnum.EXPIRED \
                and vo_has_registration_form and is_user_in_group:
            self.__logger.debug(
                self.LOG_PREFIX + 'User is expired - sending to registration.'
            )
            self.register(context, data)
        elif member_status == MemberStatusEnum.EXPIRED \
                and not is_user_in_group and vo_has_registration_form \
                and group_has_registration_form:
            self.__logger.debug(
                self.LOG_PREFIX + 'User is expired and not in group '
                + self.__group_name + ' - sending to registration.'
            )
            self.register(context, data, self.__group_name)
        else:
            self.__logger.debug(
                self.LOG_PREFIX + 'User is not valid in vo/group and cannot'
                ' be sent to the registration - sending to unauthorized'
            )
            self.unauthorized(context, data)

    def __is_user_in_group(self, user, vo):
        member_groups = self.__adapters_manager.get_member_groups(user, vo)

        for group in member_groups:
            if self.__group_name == group.name:
                return True

        return False

    def __group_has_registration_form(self, vo):
        try:
            group = self.__adapters_manager.get_group_by_name(vo, self.__group_name) # noqa e501
        except (AdaptersManagerException, AdaptersManagerNotExistsException) as _:  # noqa e501
            group = None

        if group is not None:
            return self.__adapters_manager.has_registration_form_group(group) # noqa e501

        return False

    def register(self, context, data, group_name=None):
        """
        Registers member according to given data
        @param context: current microservice context
        @param data: microservice data
        @param group_name: name of the group to register to
        @return: Redirect to registration url if possible
        """
        params = {}

        callback = ""  # ??

        if self.__callback_param_name:
            registration_url = self.__register_url + '?vo=' \
                               + self.__vo_short_name
            if group_name:
                registration_url += '&group=' + group_name

            params['targetnew'] = callback
            params['targetexisting'] = callback
            params['targetextended'] = callback


            self.__logger.debug(
                self.LOG_PREFIX + 'Redirecting to \'' + registration_url
                + ', callback parameter \'' + self.__callback_param_name
                + '\' set to value \'' + callback + '\'.'
            )
            data.attributes = params
            request_data = {}

            return Utils.secure_redirect_with_nonce(
                context,
                data,
                request_data,
                registration_url,
                self.__signing_cfg,
                self.name
            )

        else:
            raise SATOSAError(
                self.LOG_PREFIX +  'No configuration for registration set. Cannot proceed.' # noqa e501
            )

    def unauthorized(self, context, data):
        """
        Saves user state and redirects them away to a configurable url whenever
        they're not authorized for an operation within this microservice.
        @return: Redirect to a pre-configured url with "unauthorized" page
        """
        return Redirect(self.__unauthorized_redirect_url)

    def __handle_registration_response(self, context):
        context, data = Utils.handle_registration_response(
            context,
            self.__signing_cfg,
            self.__registration_result_url,
            self.name,
        )
        return self.process(context, data)

    def register_endpoints(self):
        """
        Registers an endpoint for external service reply when registering user
        into a group.
        @return: url of endpoint for external service to reply to and a method
                 to handle the reply
        """
        return [
            (
                f"^perunensuremember{self.__endpoint}$",
                self.__handle_registration_response,
            )
        ]
