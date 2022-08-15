from typing import Union, Optional, List, Set, Callable

from perun.connector.adapters.AdaptersManager import (
    AdaptersManager,
    AdaptersManagerException,
    AdaptersManagerNotExistsException,
)
from perun.connector.models.Facility import Facility
from perun.connector.models.Group import Group
from perun.connector.models.MemberStatusEnum import MemberStatusEnum
from perun.connector.utils.Logger import Logger
from satosa.context import Context
from satosa.exception import SATOSAError
from satosa.internal import InternalData
from satosa.micro_services.base import ResponseMicroService
from satosa.response import Redirect

from satosacontrib.perun.utils.ConfigStore import ConfigStore
from satosacontrib.perun.utils.PerunConstants import PerunConstants
from satosacontrib.perun.utils.Utils import Utils

logger = Logger.get_logger(__name__)


class SpAuthorization(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info(f"{SpAuthorization.__name__} is active")
        self.__DEBUG_PREFIX = self.name
        self.__endpoint = "/process"
        self.__config = config
        self.__global_config = ConfigStore.get_global_cfg(
            config["global_cfg_filepath"]
        )
        self.__signing_cfg = self.__global_config["jwk"]

        self.__filter_config = config["filter_config"]

        self.__CHECK_GROUP_MEMBERSHIP_ATTR = "check_group_membership_attr"
        self.__VO_SHORT_NAMES_ATTR = "vo_short_names_attr"
        self.__ALLOW_REGISTRATION_ATTR = "allow_registration_attr"
        self.__REGISTRATION_LINK_ATTR = "registration_link_attr"
        self.__REGISTRAR_URL = "registrar_url"
        self.__SKIP_NOTIFICATION_SPS = "skip_notification_sps"
        self.__HANDLE_UNSATISFIED_MEMBERSHIP = "handle_unsatisfied_membership"

        self.__CHECK_GROUP_MEMBERSHIP = "check_group_membership"
        self.__VO_SHORT_NAMES = "vo_short_names"
        self.__ALLOW_REGISTRATION = "allow_registration"
        self.__REGISTRATION_LINK = "registration_link"

        self.__REDIRECT_PARAMS = "redirect_params"
        self.__PARAM_REGISTRATION_URL = "registrationUrl"
        self.__PARAM_REGISTRATION_DATA = "registrationData"

        self.__unauthorized_redirect_url = config["unauthorized_redirect_url"]
        self.__single_group_registration_url = config[
            "single_group_registration_url"
        ]
        self.__register_choose_vo_and_group_url = config[
            "register_choose_vo_and_group_url"
        ]
        self.__notification_url = config["notification_url"]
        self.__registration_result_url = config["registration_result_url"]
        self.__check_group_membership_attr = self.__filter_config[
            self.__CHECK_GROUP_MEMBERSHIP_ATTR
        ]
        self.__vo_short_names_attr = self.__filter_config[
            self.__VO_SHORT_NAMES_ATTR
        ]
        self.__allow_registration_attr = self.__filter_config[
            self.__ALLOW_REGISTRATION_ATTR
        ]
        self.__registrar_url = self.__filter_config[self.__REGISTRAR_URL]
        self.__registration_link_attr = self.__filter_config[
            self.__REGISTRATION_LINK_ATTR
        ]
        self.__skip_notification_sps = self.__filter_config[
            self.__SKIP_NOTIFICATION_SPS
        ]
        self.__handle_unsatisfied_membership = self.__filter_config[
            self.__HANDLE_UNSATISFIED_MEMBERSHIP
        ]

        adapters_manager_cfg = self.__global_config["adapters_manager"]
        attrs_map = ConfigStore.get_attributes_map(
            self.__global_config["attrs_cfg_path"]
        )
        self.__adapters_manager = AdaptersManager(
            adapters_manager_cfg, attrs_map
        )

        is_missing_registration_data = not (
            self.__registration_link_attr and self.__registrar_url
        )
        if (
            self.__handle_unsatisfied_membership
            and is_missing_registration_data
        ):
            raise SATOSAError(
                f"{self.__DEBUG_PREFIX}: 'Invalid configuration: microservice "
                "should handle unsatisfied membership via registration, "
                "but neither registrar_url nor registration_link_attr have "
                f"been configured. Use option '{self.__REGISTRAR_URL}' to "
                "configure the registrar location or/and option '"
                f"{self.__REGISTRATION_LINK_ATTR}' to configure attribute "
                "for Service defined registration link."
            )

    def process(self, context: Context, data: InternalData):
        """
        Extracts user and sp entity ID from input data and checks whether user
        belongs to any group in facility with given sp ID. If any vital
        information about user or facility is missing or can't be
        obtained, this check ends in a failure. If all the information is
        found but user isn't a member of any group, necessary info is passed
        to the method handle_unsatisfied_membership.

        @param context: object for sharing proxy data through the current
                        request
        @param data: data carried between frontend and backend
        @return:
        """
        data_requester = data.requester
        user_id = data.attributes.get(
            self.__global_config["perun_user_id_attribute"]
        )
        if not user_id:
            logger.debug(
                "Request does not contain Perun user. Did you configure "
                "PerunUser microservice?"
            )
            return self.unauthorized()

        facility = self.__access_adapters_manager(
            self.__adapters_manager.get_facility_by_rp_identifier,
            data_requester
        )

        if not facility:
            logger.debug(
                f"No facility found for SP '{data_requester}', skipping "
                "processing filter."
            )
            return

        facility_attributes = self.__get_sp_attributes(facility)
        if not facility_attributes:
            logger.debug(
                "Could not fetch SP attributes, user will be redirected to "
                "unauthorized for security reasons"
            )
            return self.unauthorized()

        check_group_membership = facility_attributes.get(
            self.__CHECK_GROUP_MEMBERSHIP
        )
        if not check_group_membership:
            logger.warning(
                "Group membership check not requested by the service."
            )
            return

        user_groups = self.__access_adapters_manager(
            self.__adapters_manager.get_users_groups_on_facility,
            facility, user_id
        )
        if not user_groups:
            self.handle_unsatisfied_membership(
                context,
                data,
                user_id,
                data_requester,
                facility,
                facility_attributes,
            )
            return

        logger.info("User satisfies the group membership check.")
        return super().process(context, data)

    def unauthorized(self):
        """
        Saves user state and redirects them away to a configurable url whenever
        they're not authorized for an operation within this microservice.

        @return: Redirect to a pre-configured url with "unauthorized" page
        """
        return Redirect(self.__unauthorized_redirect_url)

    def handle_unsatisfied_membership(
        self,
        context: Context,
        data: InternalData,
        user_id: int,
        data_requester: str,
        facility: Facility,
        facility_attributes: dict[
            str, Union[str, Optional[int], bool, List[str], dict[str, str]]
        ],
    ):
        """
        Handles a situation when checked user and facility exist but user isn't
        a member of any group on facility. Initiates user registration to
        selected groups on given facility if configuration allows it. Relays
        info whether SP should be notified of registration based on config.
        Failure to initiate registration results in unauthorized access.

        @param context: object for sharing proxy data through the current
                        request
        @param data: data carried between frontend and backend
        @param user_id: Perun user id without a group in Facility
        @param data_requester: entity ID of a facility
        @param facility: facility found by given SP ID
        @param facility_attributes: attributes of given facility
        @return: Redirect to a pre-configured registration link if registration
                 is possible
        """
        if not self.__handle_unsatisfied_membership:
            logger.debug(
                "Handling unsatisfied membership is disabled, redirecting to "
                "unauthorized"
            )
            return self.unauthorized()

        is_allowed_registration = facility_attributes.get(
            self.__ALLOW_REGISTRATION, False
        )

        if is_allowed_registration:
            registration_link = facility_attributes.get(
                self.__REGISTRATION_LINK
            )
            if registration_link:
                logger.debug(
                    "Redirecting user to custom registration link '"
                    f"{registration_link}' configured for service ('"
                    f"{data_requester}')."
                )
                context.state[self.name] = data.to_dict()
                return Redirect(registration_link)

            try:
                registration_data = self.__get_registration_data(
                    user_id, facility, data_requester, facility_attributes
                )
                if registration_data:
                    skip_notification = (
                        data_requester in self.__skip_notification_sps
                    )
                    self.register(
                        context, data, registration_data, skip_notification
                    )
                    return
                logger.debug(
                    "No VO is available for registration into groups"
                    f" of resources for service '{data_requester}'"
                )
            except Exception as ex:
                logger.warning(
                    "Caught an exception, user will be redirected to "
                    "unauthorized for security reasons"
                )
                logger.debug(ex)
        else:
            logger.debug(
                "User is not member of any assigned groups of resources for "
                f"service ('{data_requester}'). Registration to the groups is "
                "disabled."
            )

        return self.unauthorized()

    def __get_sp_attributes(
        self, facility: Facility
    ) -> dict[str, Union[str, Optional[int], bool, List[str], dict[str, str]]]:
        """
        Fetches attributes required for user registration into VOs from given
        facility.

        @param facility: Facility which attributes should be extracted
        @return: attributes of given a facility necessary for registration
        """
        attr_names = [
            self.__check_group_membership_attr,
            self.__vo_short_names_attr,
        ]

        if self.__allow_registration_attr:
            attr_names.append(self.__allow_registration_attr)

        if self.__registration_link_attr:
            attr_names.append(self.__registration_link_attr)

        result = {}

        facility_attrs = self.__access_adapters_manager(
            self.__adapters_manager.get_facility_attributes,
            facility, attr_names
        )

        result[self.__CHECK_GROUP_MEMBERSHIP] = facility_attrs.get(
            self.__check_group_membership_attr, False
        )

        result[self.__VO_SHORT_NAMES] = facility_attrs.get(
            self.__vo_short_names_attr, []
        )

        result[self.__ALLOW_REGISTRATION] = facility_attrs.get(
            self.__allow_registration_attr, False
        )

        result[self.__REGISTRATION_LINK] = facility_attrs.get(
            self.__registration_link_attr
        )

        return result

    def register(
        self,
        context: Context,
        data: InternalData,
        registration_data: List[Group],
        skip_notification: bool,
    ):
        """
        Decides how to handle user registration based on the number
        of groups they're being registered to. Provides different handling of a
        single group registration compared to multiple groups registrations.

        @param context: object for sharing proxy data through the current
                        request
        @param data: data carried between frontend and backend
        @param registration_data: list of groups user should be registered to
        @param skip_notification: specifies whether SP should be notified of
                                  registration
        """
        has_single_registration = len(registration_data) == 1

        if has_single_registration:
            logger.debug(
                "Registration possible to only single VO and GROUP, "
                "redirecting directly to this registration."
            )
            group = registration_data[0]
            self.__register_directly(context, data, group, skip_notification)
        else:
            logger.debug(
                "Registration possible to more than a single VO and GROUP, "
                "letting user choose."
            )
            self.__register_choose_vo_and_group(
                context, data, registration_data
            )

    def __register_directly(
        self,
        context: Context,
        data: InternalData,
        group: Group,
        skip_notification: bool,
    ):
        """
        Called when user is being registered only into a single group. Fills in
        registration parameters about group and redirects user to registration.
        Displays notification about registration if not configured otherwise.

        @param context: object for sharing proxy data through the current
                        request
        @param data: data carried between frontend and backend
        @param group: group user should be registered to
        @param skip_notification: info whether SP should be notified of user
               registration into group or not
        @return: Redirect to a pre-configured registration link if registration
                 is possible
        """
        params = {}
        callback = ""
        if group:
            params[PerunConstants.VO] = group.vo.short_name
            if PerunConstants.GROUP_MEMBERS != group.name:
                params[PerunConstants.GROUP] = group.name
            params[PerunConstants.TARGET_NEW] = callback
            params[PerunConstants.TARGET_EXISTING] = callback
            params[PerunConstants.TARGET_EXTENDED] = callback

        registration_url = self.__single_group_registration_url
        if registration_url is None:
            raise SATOSAError(
                f"Unable to register user into group: {group}, redirect link "
                "to registration page is missing in the config file."
            )

        request_data = {}
        if not skip_notification:
            if self.__notification_url is None:
                raise SATOSAError(
                    f"Unable to register user into group: {group}, redirect "
                    "link to notification page is missing in the config file."
                )
            logger.debug(
                "Displaying registration notification. After that, "
                f"redirecting to '{registration_url}'."
            )
            data[self.__PARAM_REGISTRATION_URL] = registration_url
            return Utils.secure_redirect_with_nonce(
                context,
                data,
                request_data,
                self.__notification_url,
                self.__signing_cfg,
                self.name,
            )
        else:
            logger.debug(
                "Skipping registration notification. Redirecting directly "
                f"to '{registration_url}."
            )

        data.attributes = params
        return Utils.secure_redirect_with_nonce(
            context,
            data,
            request_data,
            registration_url,
            self.__signing_cfg,
            self.name,
        )

    def __register_choose_vo_and_group(
        self,
        context: Context,
        data: InternalData,
        registration_data: List[Group],
    ):
        """
        Sets necessary request attributes before redirecting user to a
        selection option when multiple VOs and/or groups are available for
        registration.

        @param context: object for sharing proxy data through the current
                        request
        @param data: data carried between frontend and backend
        @param registration_data:
        @return: Redirect to a pre-configured link where user chooses which
                 VO and group to register to
        """
        data.attributes[self.__REDIRECT_PARAMS] = {
            self.__PARAM_REGISTRATION_DATA: registration_data,
            self.__PARAM_REGISTRATION_URL: self.__registrar_url,
        }

        request_data = {}
        return Utils.secure_redirect_with_nonce(
            context,
            data,
            request_data,
            self.__register_choose_vo_and_group_url,
            self.__signing_cfg,
            self.name,
        )

    def __get_registration_data(
        self,
        user_id: int,
        facility: Facility,
        data_requester: str,
        facility_attributes: dict[
            str, Union[str, Optional[int], bool, List[str], dict[str, str]]
        ],
    ) -> List[Group]:
        """
        Fetches a list of possible groups where user can be registered on
        given facility.

        @param user_id: user id to be registered into a group in given facility
        @param facility: facility into which user should be registered
        @param data_requester: entity ID of a facility
        @param facility_attributes: attributes of given facility
        @return: list of available SP groups for registration
        """
        vo_short_names = facility_attributes.get(self.__VO_SHORT_NAMES)
        if not vo_short_names:
            raise SATOSAError(
                f"{self.__DEBUG_PREFIX}: Service misconfiguration - service "
                f"'{data_requester}' has membership check enabled, but does "
                "not have any resources for membership management created."
            )

        vo_short_names_for_registration = (
            self.__get_registration_vo_short_names(user_id, vo_short_names)
        )
        return self.__get_registration_groups(
            facility, vo_short_names_for_registration
        )

    def __get_registration_vo_short_names(
        self, user_id: int, vo_short_names: List[str]
    ) -> Set[str]:
        """
        Filters out unsuitable VOs from input and returns a list of short names
        of VOs where given user can register. User can register into VOs where
        they're already a valid member or VOs which provide registration form.

        @param user_id: candidate user id for registration into VOs
        @param vo_short_names: short names of all available VOs for
                               registration
        @return: list of short names of VOs where user can be registered to
        """
        suitable_vos = set()

        for vo_short_name in vo_short_names:
            vo = self.__access_adapters_manager(
                self.__adapters_manager.get_vo, short_name=vo_short_name
            )
            if not vo:
                logger.debug(
                    "Could not fetch VO with short na"
                    f"me '{vo_short_name}', skipping it."
                )
                continue

            member_status = self.__access_adapters_manager(
                self.__adapters_manager.get_member_status_by_user_and_vo,
                user_id, vo
            )

            has_registration_form = self.__access_adapters_manager(
                self.__adapters_manager.has_registration_form_by_vo_short_name,
                vo_short_name
            )

            if not member_status:
                logger.debug(
                    "User is not a member in the VO with short name '"
                    f"{vo_short_name}'."
                )

                if has_registration_form:
                    suitable_vos.add(vo_short_name)
                    logger.debug(
                        "User is not a member in the VO with short name "
                        f"'{vo_short_name}', groups of this VO will be"
                        " included in registration list as it has got "
                        "registration form."
                    )
                else:
                    logger.debug(
                        f"VO with shortName '{vo_short_name}' does "
                        "not have "
                        "a registration form, ignoring it."
                    )
            elif member_status == MemberStatusEnum("VALID"):
                suitable_vos.add(vo_short_name)
                logger.debug(
                    "User is valid in VO with short na"
                    f"me '{vo_short_name}', groups of this VO will be "
                    "included in registration list."
                )
            elif member_status == MemberStatusEnum("EXPIRED"):
                logger.debug(
                    "User is expired in the VO with short name '"
                    f"{vo_short_name}', checking registration form "
                    "availability."
                )
                if has_registration_form:
                    suitable_vos.add(vo_short_name)
                    logger.debug(
                        "User is expired in the VO with short name "
                        f"'{vo_short_name}', groups of this VO will be"
                        " included in registration list as it has got "
                        "extension form."
                    )
            else:
                logger.debug(
                    "User is a member in the VO with short name '"
                    f"{vo_short_name}' but is neither valid nor expired. "
                    "VO will be ignored for registration."
                )

        return suitable_vos

    def __get_registration_groups(
        self, facility: Facility, vo_short_names_for_registration: Set[str]
    ) -> List[Group]:
        """
        Fetches list of groups from given VOs. Input VOs are suitable for
        registration and user can choose from groups within these VOs.

        @param facility: facility where user should be registered
        @param vo_short_names_for_registration: list of VO short names for
               registration
        @return: list of groups suitable for user registration
        """
        sp_groups = self.__access_adapters_manager(
            self.__adapters_manager.get_sp_groups_by_facility, facility
        )
        registration_data = []

        for sp_group in sp_groups:
            vo_short_name = sp_group.vo.short_name
            group_name = sp_group.name

            if vo_short_name not in vo_short_names_for_registration:
                continue

            has_registration_form = self.__access_adapters_manager(
                self.__adapters_manager.has_registration_form_group,
                vo_short_name
            )

            if (
                group_name == PerunConstants.GROUP_MEMBERS
                or has_registration_form
            ):
                registration_data.append(sp_group)
                logger.debug(
                    f"Group '{sp_group.unique_name}' added to "
                    "the registration list."
                )

        return registration_data

    def __handle_registration_response(self, context: Context):
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
                f"^spauthorization{self.__endpoint}$",
                self.__handle_registration_response,
            )
        ]

    def __access_adapters_manager(self, method: Callable, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (
            AdaptersManagerException,
            AdaptersManagerNotExistsException,
        ) as e:
            raise SATOSAError(
                f"{self.__DEBUG_PREFIX} {e.message}"
            )
