import logging

try:
    from simplejson.errors import JSONDecodeError
except ImportError:
    from json.decoder import JSONDecodeError
import requests
from requests.auth import HTTPBasicAuth
from satosa.micro_services.base import ResponseMicroService

logger = logging.getLogger(__name__)


class PerunIdentityBeta(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("PerunIdentityBeta is active")
        self.__rpc_url = config["rpc_url"]
        self.__rpc_username = config["rpc_username"]
        self.__rpc_password = config["rpc_password"]
        self.__perun_login_attribute = config["perun_login_attribute"]
        self.__internal_login_attribute = config["internal_login_attribute"]
        self.__internal_extsource_attribute = config["internal_extsource_attribute"]
        self.__proxy_extsource_name = config["proxy_extsource_name"]
        self.__allowed_requesters = config.get("allowed_requesters", None)

    def __get_user_login(self, issuer_id, user_external_id):
        auth = HTTPBasicAuth(self.__rpc_username, self.__rpc_password)
        user = requests.post(
            self.__rpc_url
            + "/ba/rpc/json/usersManager/getUserByExtSourceNameAndExtLogin",
            json={"extSourceName": issuer_id, "extLogin": user_external_id},
            auth=auth,
        )
        if user.status_code != 200:
            return None
        try:
            user = user.json()
        except JSONDecodeError:
            return None
        login = requests.post(
            self.__rpc_url + "/ba/rpc/json/attributesManager/getAttribute",
            json={"user": user["id"], "attributeName": self.__perun_login_attribute},
            auth=auth,
        )
        if login.status_code != 200:
            return None
        try:
            login = login.json()
        except JSONDecodeError:
            return None
        return login["value"]

    def process(self, context, data):
        """
        Load user login from Perun for specified IdPs.
        :param context: request context
        :param data: the internal request
        """

        if (
            data["auth_info"]["issuer"]
            and data.attributes[self.__internal_login_attribute]
            and (
                self.__allowed_requesters is None
                or data.requester in self.__allowed_requesters
            )
        ):
            login = self.__get_user_login(
                data["auth_info"]["issuer"],
                data.attributes[self.__internal_login_attribute][0],
            )
            if login:
                data.subject_id = login
                data.attributes[self.__internal_extsource_attribute] = [
                    self.__proxy_extsource_name
                ]

        return super().process(context, data)
