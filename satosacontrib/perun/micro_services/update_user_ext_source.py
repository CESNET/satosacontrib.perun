from perun.connector.utils.Logger import Logger
from perun.connector.adapters.AdaptersManager import AdaptersManager
from perun.connector.adapters.AdaptersManager import AdaptersManagerNotExistsException # noqa e501
from perun.connector.adapters.AdaptersManager import AdaptersManagerException
from satosa.micro_services.base import ResponseMicroService
from satosa import exception
from typing import List, Union, Any
from satosacontrib.perun.utils.ConfigStore import ConfigStore
import threading


def is_complex_type(attribute_type: type) -> bool:
    return isinstance(attribute_type, list) \
           or isinstance(attribute_type, dict)


def is_simple_type(attribute_type: type) -> bool:
    return isinstance(attribute_type, bool) or \
           isinstance(attribute_type, str) or \
           isinstance(attribute_type, int)


def convert_to_string(
        new_value: List[Union[str, int, dict, bool, List[Any]]]
) -> str:
    if new_value:
        new_value = list(set(new_value))
        attr_value_as_string = ';'.join(new_value)
    else:
        attr_value_as_string = ''

    return attr_value_as_string


class UpdateUserExtSource(ResponseMicroService):
    """
    This Satosa microservice updates
    userExtSource attributes when the user logs in
    """

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__config = config
        self.DEFAULT_CONFIG = {
            'user_identifiers':
                ['eduPersonUniqueId',
                 'eduPersonPrincipalName',
                 'eduPersonTargetedID',
                 'nameId',
                 'uid']
        }

        self.__logger = Logger.get_logger(self.__class__.__name__)

        self.__global_conf = ConfigStore.get_global_cfg(
            config["global_cfg_path"]
        )
        self.__attr_map_cfg = ConfigStore.get_attributes_map( # noqa e501
                self.__global_conf["attrs_cfg_path"]
        )

        self.__perun_id_attr = self.__global_conf['perun_user_id_attribute']
        self.__adapters_manager = AdaptersManager(
            self.__global_conf["adapters_manager"],
            self.__attr_map_cfg
        )
        self.__append_only_attrs = []
        self.__array_to_str_conversion = []
        if config['array_to_string_conversion']:
            self.__array_to_str_conversion = config['array_to_string_conversion'] # noqa e501
        if config['append_only_attrs']:
            self.__append_only_attrs = config['append_only_attrs']

    def process(self, context, data):

        """
        This is where the micro service should modify the request / response.
        Subclasses must call this method (or in another way make sure the
        next callable is called).
        @param context: The current context
        @param data: Data to be modified
        """

        data_to_conversion = {
            'attributes': data.attributes,
            'attr_map': self.__config['attr_map'],
            'attrs_to_conversion': self.__array_to_str_conversion,
            'append_only_attrs': self.__append_only_attrs,
            'perun_user_id': data.attributes[self.__perun_id_attr],
            'auth_info': data.auth_info
        }

        threading.Thread(
            target=self.__run,
            args=(data_to_conversion,)
        ).start()

        return super().process(context, data)

    def __run(self, data_to_conversion):

        """
        This method runs the main logic
        of the process on another thread
        @param data_to_conversion: data to be modified
        """

        attrs_from_idp = data_to_conversion['attributes'].copy()
        attr_map = data_to_conversion['attr_map']
        serialized_attrs = data_to_conversion['attrs_to_conversion']
        append_only_attrs = data_to_conversion['append_only_attrs']
        user_id = data_to_conversion['perun_user_id']

        config = self.__get_configuration()

        identifier_attributes = config['user_identifiers']

        try:
            ext_source_name = data_to_conversion['auth_info']['issuer']

            user_ext_source = self.__find_user_ext_source(
                ext_source_name,
                attrs_from_idp,
                identifier_attributes
            )

            if not user_ext_source:
                raise exception.SATOSAError(
                    self.__class__.__name__
                    + 'No userExtSource found for IDP: '
                    + ext_source_name
                )

            attrs_from_perun = self.__get_attributes_from_perun(
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
                self.__logger.debug(
                    self.__class__.__name__ + 'Updating UES for user with '
                                              'userId: ' + str(user_id)
                    + 'was successful.'
                )
        except KeyError:
            self.__logger.warning(
                self.__class__.__name__ + 'Updating UES for user with userId:'
                + ' ' + str(user_id) + 'was  not successful.'
            )

    def __find_user_ext_source(
            self,
            ext_source_name,
            attributes_from_idp,
            id_attrs
    ):

        """
        This method finds and gets UES from Perun
        @param ext_source_name: name of UES
        @param attributes_from_idp: attributes from idp
        @param id_attrs: user identifiers
        @return: Optional[UES]
        """

        for attr_name in attributes_from_idp:
            if attr_name not in id_attrs:
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
                    self.__logger.debug(self.__class__.__name__ +
                                        "Found user ext source for combination " # noqa e501
                                        "extSourceName \'" + ext_source_name
                                        + "\' and extLogin \'" + ext_login + "\'") # noqa e501
                    return user_ext_source

        return None

    def __get_attributes_from_perun(self, user_ext_source):

        """
        This method gets UES attributes from Perun
        @param user_ext_source: UES
        @return: list of attributes
        """

        attributes_from_perun = dict()
        try:
            attributes_from_perun_raw = \
                self.__adapters_manager.get_user_ext_source_attributes(
                    user_ext_source,
                    list(self.__config['attr_map'].keys())
                )
        except (AdaptersManagerException, AdaptersManagerNotExistsException) as e: # noqa e501
            self.__logger.debug(e)
            raise exception.SATOSAError(
                self.__class__.__name__ + "Getting attributes for UES "
                                          "was not successful."
            )

        if not attributes_from_perun_raw:
            raise exception.SATOSAError(
                self.__class__.__name__ + "Getting attributes for UES "
                                          "was not successful."
            )

        for raw_attr_name, raw_attr_val in attributes_from_perun_raw.items():
            if isinstance(raw_attr_val, dict) and "name" in raw_attr_val:
                attributes_from_perun[raw_attr_val["name"]] = raw_attr_val

        if not attributes_from_perun:
            raise exception.SATOSAError(
                self.__class__.__name__ + "Getting attributes for UES "
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

        """
        This method gets UES attributes that need to be updated
        @param attributes_from_perun: list of attributes
        @param attr_map: mapped attributes
        @param serialized_attrs
        @param append_only_attrs
        @param attrs_from_idp: attributes from idp
        @return: list of attributes to update
        """

        attrs_to_update = []
        for attr_name, attr_value in attributes_from_perun.items():
            attr = attrs_from_idp.get(attr_map[attr_name])
            if attr_name in append_only_attrs and attr_value and \
                    (is_complex_type(attr_value) or
                     attr_name in serialized_attrs):
                attr += attr_value.split(';') if \
                    attr_name in serialized_attrs else attr_value
                attr = list(set(attr))

            if is_simple_type(attr_value):
                new_value = convert_to_string(attr)
            elif is_complex_type(attr_value):
                new_value = list(set(attr)) if attr else []
                if attr_name in serialized_attrs:
                    new_value = convert_to_string(new_value)
            else:
                self.__logger.debug(self.__class__.__name__ +
                                    "Unsupported type of attribute.")
                continue

            if new_value != attr_value:
                attr_value = new_value
                attrs_to_update.append({attr_name: attr_value})

        return attrs_to_update

    def __update_user_ext_source(self, user_ext_source, attrs_to_update):

        """
        This method updates UES attributes
        @param user_ext_source: UES
        @param attrs_to_update: attributes to update
        @return: bool
        """

        try:
            self.__adapters_manager.update_user_ext_source_last_access(
                user_ext_source
            )

            self.__adapters_manager.set_user_ext_source_attributes(
                user_ext_source,
                attrs_to_update
            )

            return True
        except (AdaptersManagerException, AdaptersManagerNotExistsException) as e: # noqa e501
            self.__logger.debug(e)
            return False

    def __get_configuration(self):
        config = self.DEFAULT_CONFIG
        for key in config.keys():
            if key not in self.__config:
                self.__logger.warning('%s: %s missing in config. '
                                      'Using default value.' %
                                      self.__class__.__name__, key)
            else:
                config[key] = self.__config[key]
        return config

    def __get_user_ext_source(self, ext_source_name, ext_login):
        try:
            result = self.__adapters_manager.get_user_ext_source(
                ext_source_name, ext_login
            )

            return result
        except (AdaptersManagerException, AdaptersManagerNotExistsException) as _: # noqa e501
            return None
