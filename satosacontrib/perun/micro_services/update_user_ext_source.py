from adapters.AdaptersManager import AdaptersManager
from satosa.micro_services.base import ResponseMicroService
from satosa import exception
from typing import List, Union, Any

import threading
import logging

logger = logging.getLogger(__name__)


class UpdateUserExtSource(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__config = config

        self.DEBUG_PREFIX = "UpdateUserExtSource: "
        self.NAMESPACE = "namespace"
        self.UES_ATTR_NMS = "urn:perun:ues:attribute-def:def"
        self.DEFAULT_CONFIG = {
            'sourceIdPAttributeKey': 'sourceIdPEntityID',
            'userIdentifiers': ['eduPersonUniqueId',
                                'eduPersonPrincipalName',
                                'eduPersonTargetedID',
                                'nameid',
                                'uid']
        }

        self.__perun_id = config['perunId'] # ??
        self.__adapters_manager = AdaptersManager()
        self.__attr_map = config['attrMap']
        self.__append_only_attrs = []
        self.__array_to_str_conversion = []
        if config['arrayToStringConversion']:
            self.__array_to_str_conversion = config['arrayToStringConversion']
        if config['arrayToStringConversion']:
            self.__append_only_attrs = config['appendOnlyAttrs']

    def process(self, context, data):
        data_to_conversion = {
            'attributes': data.attributes,
            'attrMap': self.__attr_map,
            'attrsToConversion': self.__array_to_str_conversion,
            'appendOnlyAttrs': self.__append_only_attrs,
            'perunUserId': data.attributes[self.__perun_id][0],
            'auth_info': data.auth_info
        }

        threading.Thread(
            target=self.__run,
            args=(data_to_conversion,)
        ).start()

        return super().process(context, data)

    def __run(self, data_to_conversion):
        attrs_from_idp = data_to_conversion['attributes']
        attr_map = data_to_conversion['attrMap']
        serialized_attrs = data_to_conversion['attrsToConversion']
        append_only_attrs = data_to_conversion['appendOnlyAttrs']
        user_id = data_to_conversion['perunUserId']

        config = self.__get_configuration()

        source_idp_attribute = config['sourceIdPAttributeKey']
        identifier_attributes = config['userIdentifiers']

        try:
            if not data_to_conversion['auth_info']['issuer']:
                raise exception.SATOSAError(
                    self.DEBUG_PREFIX + 'Invalid attributes from IdP '
                                        '- Attribute \'' +
                    source_idp_attribute + '\' is empty'
                )

            ext_source_name = data_to_conversion['auth_info']['issuer']

            user_ext_source = self.__find_user_ext_source(
                ext_source_name,
                attrs_from_idp,
                identifier_attributes
            )

            if not user_ext_source:
                raise exception.SATOSAError(
                    self.DEBUG_PREFIX + 'There is no UserExtSource that '
                                        'could be used for user '
                    + user_id + ' and IdP ' + ext_source_name
                )

            attrs_from_perun = self.__get_attributes_from_perun(
                attr_map,
                user_ext_source
            )
            attrs_to_update = self.__get_attributes_to_update(
                attrs_from_perun,
                attr_map,
                serialized_attrs,
                append_only_attrs,
                attrs_from_idp
            )

            if self.__update_user_ext_source(
                    user_ext_source,
                    attrs_to_update
            ):
                logger.debug(
                    self.DEBUG_PREFIX + 'Updating UES for user with userId: '
                    + user_id + 'was successful.'
                )
        except KeyError:
            logger.warning(
                self.DEBUG_PREFIX + 'Updating UES for user with userId: '
                + user_id + 'was  not successful.'
            )

    def __get_configuration(self):
        config = self.DEFAULT_CONFIG
        try:
            assert 'sourceIdPEntityID' in self.__config['sourceIdPAttributeKey']
            assert 'eduPersonPrincipalName' in self.__config['userIdentifiers']
            assert 'eduPersonTargetedID' in self.__config['userIdentifiers']
            assert 'eduPersonUniqueId' in self.__config['userIdentifiers']
            assert 'nameid' in self.__config['userIdentifiers']
            assert 'uid' in self.__config['userIdentifiers']
            config = self.__config

        except AssertionError:
            logger.warning(self.DEBUG_PREFIX + 'Configuration is invalid. '
                                               'Using default values')
        return config

    def __get_user_ext_source(self, ext_source_name, ext_login):
        return self.__adapters_manager.get_user_ext_source(
            ext_source_name, ext_login
        )

    def __find_user_ext_source(
            self,
            ext_source_name,
            attributes_from_idp,
            id_attr
    ):
        for attr_name in attributes_from_idp:
            if attr_name not in id_attr:
                continue

            if not isinstance(attributes_from_idp[attr_name], list):
                new_value = list(attributes_from_idp[attr_name])
                attributes_from_idp[attr_name] = new_value

            for ext_login in attributes_from_idp[attr_name]:
                user_ext_source = self.__get_user_ext_source(
                    ext_source_name,
                    ext_login
                )
                if user_ext_source:
                    logger.debug(self.DEBUG_PREFIX + "Found user ext source "
                                                     "for combination "
                                                     "extSourceName \'" +
                                 ext_source_name + "\' and extLogin \'" +
                                 ext_login + "\'")
                    return user_ext_source

        return

    def __get_attributes_from_perun(self, attr_map, user_ext_source):
        attributes_from_perun = []
        attributes_from_perun_raw = \
            self.__adapters_manager.get_user_ext_source_attributes(
                user_ext_source,
                attr_map.keys()
            )

        if not attributes_from_perun_raw:
            raise exception.SATOSAError(
                self.DEBUG_PREFIX + "Getting attributes for UES "
                                    "was not successful."
            )

        for raw_attr in attributes_from_perun_raw:
            if isinstance(raw_attr, dict) and raw_attr["name"]:
                attributes_from_perun[raw_attr["name"]] = raw_attr

        if not attributes_from_perun:
            raise exception.SATOSAError(
                self.DEBUG_PREFIX + "Getting attributes for UES "
                                    "was not successful."
            )

        return attributes_from_perun

    def __get_attributes_to_update(
            self,
            attributes_from_perun,
            attr_map,
            serialized_attrs,
            append_only_attrs,
            attrs_from_idp
    ):
        attrs_to_update = []

        for attribute in attributes_from_perun:
            attr_name = attribute["name"]

            attr = dict()
            if attrs_from_idp[attr_map[attr_name]]:
                attr = attrs_from_idp[attr_map[attr_name]]

            if attr_name in append_only_attrs and attribute["value"] and \
                    (self.__is_complex_type(attribute["type"]) or
                     attr_name in serialized_attrs):
                if attr_name in serialized_attrs:
                    attr |= attribute["value"].split(';')
                else:
                    attr |= attribute["value"]

            if self.__is_simple_type(attribute["type"]):
                new_value = self.__convert_to_string(attr)
            elif self.__is_complex_type(attribute["type"]):
                if attr:
                    new_value = list(set(list(attr.values())))
                else:
                    new_value = []
                if attr_name in serialized_attrs:
                    new_value = self.__convert_to_string(new_value)
            else:
                logger.debug(self.DEBUG_PREFIX +
                             "Unsupported type of attribute.")
                continue

            if new_value != attribute['value']:
                attribute['value'] = new_value
                attribute[self.NAMESPACE] = self.UES_ATTR_NMS
                attrs_to_update.append(attribute)

        return attrs_to_update

    def __update_user_ext_source(self, user_ext_source, attrs_to_update):
        attrs_to_update_final = []

        if attrs_to_update:
            for attr in attrs_to_update:
                attr['name'] = 'urn:perun:ues:attribute-def:def:' \
                               + attr['friendlyName']
                attrs_to_update_final.append(attr)

            self.__adapters_manager.set_user_ext_source_attributes(
                user_ext_source,
                attrs_to_update_final
            )

        self.__adapters_manager.update_user_ext_source_last_access(
            user_ext_source
        )

        return True

    @staticmethod
    def __is_complex_type(attribute_type: str) -> bool:
        return attribute_type == "list" or attribute_type == "dict"

    @staticmethod
    def __is_simple_type(attribute_type: str) -> bool:
        return attribute_type == "bool" or \
               attribute_type == "str" or \
               attribute_type == "int"

    @staticmethod
    def __convert_to_string(
            new_value: List[Union[str, int, dict, bool, List[Any]]]
    ) -> str:
        if new_value:
            new_value = list(set(new_value))
            attr_value_as_string = ';'.join(new_value)
        else:
            attr_value_as_string = ''

        return attr_value_as_string
