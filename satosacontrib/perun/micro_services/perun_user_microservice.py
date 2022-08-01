import logging
from typing import List

from perun.connector.adapters.AdaptersManager import (
    AdaptersManager,
    AdaptersManagerNotExistsException,
)
from satosa.context import Context
from satosa.exception import SATOSAError
from satosa.internal import InternalData
from satosa.micro_services.base import ResponseMicroService
from satosa.response import Redirect

from satosacontrib.perun.utils.ConfigStore import ConfigStore
from satosacontrib.perun.utils.Utils import Utils

logger = logging.getLogger(__name__)


class PerunUser(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("PerunUser is active")
        global_config = ConfigStore.get_global_cfg(config["global_cfg_filepath"])

        self.__perun_user_id_attr = global_config["perun_user_id_attribute"]
        self.__perun_login_attribute = global_config["perun_login_attribute"]
        self.__internal_login_attribute = config["internal_login_attribute"]
        self.__internal_extsource_attribute = config["internal_extsource_attribute"]
        self.__proxy_extsource_name = config["proxy_extsource_name"]
        self.__allowed_requesters = config.get("allowed_requesters", [])
        self.__registration_page_url = config.get("registration_page_url", [])
        self.__registration_result_url = config["registration_result_url"]

        adapters_manager_cfg = global_config["adapters_manager"]
        attrs_map = ConfigStore.get_attributes_map(global_config["attrs_cfg_path"])

        self.__adapters_manager = AdaptersManager(adapters_manager_cfg, attrs_map)
        self.__endpoint = "/process"
        self.__signing_cfg = global_config["jwk"]

    def __handle_registration_response(self, context: Context):
        """
        Handles response from external service with the result of new user
        registration.

        @param context: request context
        @return: loaded newly registered user if registration was successful
        """
        context, data = Utils.handle_registration_response(
            context, self.__signing_cfg, self.__registration_result_url, self.name
        )
        return self.process(context, data)

    def process(self, context: Context, data: InternalData):
        """
        Load user login from Perun for specified IdPs.

        @param context: request context
        @param data: the internal request
        """

        if data.requester not in self.__allowed_requesters:
            raise SATOSAError("Data request not allowed.")

        name = data.auth_info.issuer
        logins = data.attributes[self.__internal_login_attribute]

        try:
            user = self.__adapters_manager.get_perun_user(name, logins)
        except AdaptersManagerNotExistsException:
            return self.handle_user_not_found(name, logins, context, data)

        user_attrs = self.__adapters_manager.get_user_attributes(
            user.id, [self.__perun_login_attribute]
        )
        login = user_attrs.get(self.__perun_login_attribute)

        data.subject_id = login
        data.attributes[self.__internal_extsource_attribute] = [
            self.__proxy_extsource_name
        ]
        data.attributes[self.__perun_user_id_attr] = user.id

        return super().process(context, data)

    def handle_user_not_found(
        self, name: str, logins: List[str], context: Context, data: InternalData
    ) -> Redirect:
        """
        Handles a case when user we were looking for wasn't found in the
        external system. Redirects user to a registration page if possible,
        otherwise raises SATOSAError.

        @param name: name of the user we were looking for
        @param logins: possible logins of user with given name
        @param context: request context
        @param data: the internal request
        @return: redirect to registration page
        """
        if not self.__registration_page_url:
            raise SATOSAError(
                f"User with name {name} and idp IDs {logins} was not "
                "found in Perun. And redirect link to registration "
                "page is missing in the config file."
            )

        request_data = {}
        return Utils.secure_redirect_with_nonce(
            context,
            data,
            request_data,
            self.__registration_page_url,
            self.__signing_cfg,
            self.name,
        )

    def register_endpoints(self):
        """
        Registers an endpoint for external service reply when looking for
        user's credentials.

        @return: url of endpoint for external service to reply to and a method
                 to handle the reply
        """
        return [(f"^perunuser{self.__endpoint}$", self.__handle_registration_response)]
