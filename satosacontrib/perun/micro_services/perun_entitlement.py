from satosa.micro_services.base import ResponseMicroService
from perun.connector.utils.Logger import Logger
from perun.connector.adapters.AdaptersManager import AdaptersManager
from satosa.exception import SATOSAError
from re import sub
from natsort import natsorted
from urllib.parse import quote

from satosacontrib.perun.utils.ConfigStore import ConfigStore


def encode_entitlement(group_name):
    return quote(group_name, safe='!$\'()*,;&=@:+')


def encode_name(name):
    return quote(name, safe='!\'()*')


class PerunEntitlement(ResponseMicroService):

    """ This Satosa microservice joins
    eduPersonEntitlement, forwardedEduPersonEntitlement,
    resource capabilities and facility capabilities"""

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__logger = Logger.get_logger(self.__class__.__name__)

        self.OUTPUT_ATTR_NAME = 'eduperson_entitlement'
        self.RELEASE_FORWARDED_ENTITLEMENT = 'release_forwarded_entitlement'
        self.FORWARDED_EDU_PERSON_ENTITLEMENT = 'forwarded_eduperson_entitlement' # noqa
        self.ENTITLEMENT_PREFIX_ATTR = 'entitlement_prefix'
        self.ENTITLEMENT_AUTHORITY_ATTR = 'entitlement_authority'
        self.GROUP_NAME_AARC_ATTR = 'group_name_AARC'

        self.__config = config

        self.__group_mapping = self.__config['group_mapping']
        self.__extended = False
        if self.__config['entitlement_extended'] == 'true':
            self.__extended = True

        self.__global_cfg = ConfigStore.get_global_cfg(
            config["global_cfg_path"]
        )

        self.__attr_map_cfg = ConfigStore.get_attributes_map(
            self.__global_cfg["attrs_cfg_path"]
        )
        self.__adapters_manager = AdaptersManager(
            self.__global_cfg["adapters_manager"],
            self.__attr_map_cfg
        )
        if not self.__extended:
            self.__edu_person_entitlement = \
                self.__global_cfg[self.OUTPUT_ATTR_NAME]
        else:
            self.__output_attr_name = \
                self.__global_cfg[self.OUTPUT_ATTR_NAME]

        self.__release_forwarded_entitlement = \
            self.__global_cfg.get(self.RELEASE_FORWARDED_ENTITLEMENT, True)

        self.__forwarded_edu_person_entitlement = \
            self.__global_cfg[self.FORWARDED_EDU_PERSON_ENTITLEMENT]

        self.__group_name_aarc = self.__config[self.GROUP_NAME_AARC_ATTR]

        self.__entitlement_prefix = \
            self.__config[self.ENTITLEMENT_PREFIX_ATTR]

        self.__entitlement_authority = \
            self.__config[self.ENTITLEMENT_AUTHORITY_ATTR]

    def process(self, context, data):

        """
        This is where the micro service should modify the request / response.
        Subclasses must call this method (or in another way make sure the
        next callable is called).

        @param context: The current context
        @param data: Data to be modified
        """

        edu_person_entitlement = []
        edu_person_entitlement_extended = []
        capabilities = []
        forwarded_edu_person_entitlement = []

        if data.data['perun']['groups']:
            if not self.__extended:
                edu_person_entitlement = self.__get_edu_person_entitlement(data) # noqa e501
            else:
                edu_person_entitlement_extended = \
                    self.__get_edu_person_entitlement_extended(data)

            capabilities = self.__get_capabilities(data)

        else:
            self.__logger.debug(
                'perun:PerunEntitlement: There are no user '
                'groups assigned to facility. => Skipping '
                'getEduPersonEntitlement and getCapabilities'
            )

        if self.__release_forwarded_entitlement:
            forwarded_edu_person_entitlement = \
                self.__get_forwarded_edu_person_entitlement(
                    data,
                )

        if not self.__extended:
            data.attributes[self.__edu_person_entitlement] = \
                list(set(edu_person_entitlement +
                         forwarded_edu_person_entitlement + capabilities))
        else:
            data.attributes[self.__edu_person_entitlement] = \
                list(set(edu_person_entitlement_extended +
                         forwarded_edu_person_entitlement + capabilities))

        return super().process(context, data)

    def __get_edu_person_entitlement(self, data):

        """
        This method gets entitlements of groups stored in `data`

        @param data: Data (from process) to be modified
        @return: list of entitlements
        """

        edu_person_entitlement = []

        groups = data.data['perun']['groups']
        for group in groups:
            group_name = group.unique_name
            group_name = sub(r'^(\w*):members$', r'\1', group_name)

            if self.__config['group_name_AARC'] \
                    or self.__group_name_aarc:
                if not self.__entitlement_authority \
                        or not self.__entitlement_prefix:
                    raise SATOSAError(
                        'perun:PerunEntitlement: missing '
                        'mandatory configuration options '
                        '\'groupNameAuthority\' '
                        'or \'groupNamePrefix\'.'
                    )

                group_name = self.__group_name_wrapper(group_name)
            else:
                group_name = self.__map_group_name(group_name, data.requester)

            edu_person_entitlement.append(group_name)

        natsorted(edu_person_entitlement)

        return edu_person_entitlement

    def __get_edu_person_entitlement_extended(self, data):

        """
        This method gets entitlements of groups stored in `data`
        in extended mode

        @param data: Data (from process) to be modified
        @return: list of entitlements
        """

        edu_person_entitlement_extended = []

        groups = data.data['perun']['groups']
        for group in groups:
            entitlement = self.__group_entitlement_wrapper(group.uuid)

            edu_person_entitlement_extended.append(entitlement)

            group_name = group.unique_name
            group_name = sub(r'^(\w*):members$', r'\1', group_name)

            entitlement_with_attributes = \
                self.__group_entitlement_with_attributes_wrapper(
                    group.uuid,
                    group_name
                )
            edu_person_entitlement_extended.append(
                entitlement_with_attributes
            )

        natsorted(edu_person_entitlement_extended)
        return edu_person_entitlement_extended

    def __get_forwarded_edu_person_entitlement(self, data):

        """
        This method gets forwarded_edu_person_entitlement
        based on the user in `data`

        @param data: Data (from process) to be modified
        @return: list of forwarded edu person entitlements
        """

        result = []

        user_id = data.attributes.get(self.__global_cfg["perun_user_id_attribute"]) # noqa
        if not user_id:
            self.__logger.debug(
                'perun:Entitlement: Perun User Id is not '
                'specified. => Skipping getting forwardedEntitlement.'
            )

            return result

        forwarded_edu_person_entitlement_map = dict()

        try:
            forwarded_edu_person_entitlement_map = \
                self.__adapters_manager.get_user_attributes(
                    user_id,
                    [self.__forwarded_edu_person_entitlement]
                )
        except Exception as e:
            self.__logger.debug(
                'perun:Entitlement: Exception ' + str(e) +
                ' was thrown in method \'getForwardedEduPersonEntitlement\'.'
            )

        if forwarded_edu_person_entitlement_map:
            result = [list(forwarded_edu_person_entitlement_map.values())[0]]

        return result

    def __get_capabilities(self, data):

        """
        This method gets forwarded_edu_person_entitlement
        based on the user in `data`

        @param data: Data (from process) to be modified
        @return: list of forwarded edu person entitlements
        """

        resource_capabilities = []
        facility_capabilities = []
        capabilities_result = []

        try:
            resource_capabilities = \
                self.__adapters_manager.get_resource_capabilities_by_rp_id(
                    data.requester,
                    data.data['perun']['groups']
                )

            facility_capabilities = \
                self.__adapters_manager.get_facility_capabilities_by_rp_id(
                   data.requester
                )

        except Exception as e:
            self.__logger.warning(
                'perun:EntitlementUtils: Exception ' + str(e) +
                ' was thrown in method \'getCapabilities\'.'
            )

        capabilities = list(set(facility_capabilities + resource_capabilities)) # noqa e501

        for capability in capabilities:
            wrapped_capability = self.__capabilities_wrapper(capability)
            capabilities_result.append(wrapped_capability)

        return capabilities_result

    def __map_group_name(self, group_name, requester):

        """
        This method translates given name of group based on
        'groupMapping' in config

        @param group_name: given name of group
        @return: mapped group name
        """

        if requester in self.__group_mapping \
                and group_name in self.__group_mapping[requester] \
                and self.__group_mapping[requester][group_name]:
            self.__logger.debug(
                'Mapping ' + group_name + ' to '
                + self.__group_mapping[requester][group_name]
            )

            return self.__group_mapping[requester][group_name]

        self.__logger.debug(
            'No mapping found for group ' + group_name + ' for entity '
            + requester
        )

        return self.__entitlement_prefix + 'group:' + group_name

    def __group_name_wrapper(self, group_name):
        return '{prefix}group:{name}#{authority}'.format(
            prefix=self.__entitlement_prefix,
            name=encode_entitlement(group_name),
            authority=self.__entitlement_authority
        )

    def __capabilities_wrapper(self, capabilities):
        return '{prefix}{capabilities}#{authority}'.format(
            prefix=self.__entitlement_prefix,
            capabilities=encode_entitlement(capabilities),
            authority=self.__entitlement_authority
        )

    def __group_entitlement_wrapper(self, uuid):
        return '{prefix}group{uuid}#{authority}'.format(
            prefix=self.__entitlement_prefix,
            uuid=encode_name(uuid),
            authority=self.__entitlement_authority
        )

    def __group_entitlement_with_attributes_wrapper(
            self,
            group_uuid,
            group_name
    ):
        return '{prefix}groupAttributes:{uuid}?=displayName={name}#{authority}'.format(  # noqa e501
            prefix=self.__entitlement_prefix,
            uuid=group_uuid,
            name=encode_name(group_name),
            authority=self.__entitlement_authority
        )
