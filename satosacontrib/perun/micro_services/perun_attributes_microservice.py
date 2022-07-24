from satosa.micro_services.base import ResponseMicroService
from perun.connector.utils.Logger import Logger
from perun.connector.adapters.AdaptersManager import AdaptersManager
from perun.connector.adapters.AdaptersManager import AdaptersManagerException
from perun.connector.adapters.AdaptersManager import AdaptersManagerNotExistsException # noqa e501
from satosa.exception import SATOSAError
from satosa.context import Context
from satosa.internal import InternalData

from satosacontrib.perun.utils.ConfigStore import ConfigStore


class PerunAttributes(ResponseMicroService):

    """
    This Satosa microservice fetches user attributes by its names listed
    as keys of attrMap config property and set them as Attributes
    values to keys specified as attrMap values. Old values of
    Attributes are replaced.

    It strongly relays on PerunIdentity microservice to obtain perun
    user id. Configure it before this microservice properly
    """

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__logger = Logger.get_logger(self.__class__.__name__)

        self.MODE_FULL = 'FULL'
        self.MODE_PARTIAL = 'PARTIAL'

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

        if not config['mode']:
            config['mode'] = self.MODE_FULL

        self.__mode = config['mode']

        if self.__mode != self.MODE_FULL and self.__mode != self.MODE_PARTIAL:
            self.__mode = self.MODE_FULL

        self.__attr_map = config['attr_map']

    def process(self, context: Context, data: InternalData):

        """
        This is where the micro service should modify the request / response.
        Subclasses must call this method (or in another way make sure the
        next callable is called).
        @param context: The current context
        @param data: Data to be modified
        """

        user_id = data.attributes.get(self.__global_cfg["perun_user_id_attribute"]) # noqa
        if not user_id:
            raise SATOSAError(
                self.__class__.__name__ +
                f"Missing mandatory attribute "
                f"'{self.__global_cfg['perun_user_id_attribute']}' "
                f"in data.attributes. Hint: Did you "
                f"configured PerunUser microservice "
                f"before this microservice?"
            )

        attributes = []
        if self.__mode == self.MODE_FULL:
            attributes = self.__attr_map.keys()
        elif self.__mode == self.MODE_PARTIAL:
            for attr_name, attr_value in self.__attr_map.items():
                if not attr_value:
                    attributes.append(attr_name)
                    break
                if not isinstance(attr_value, list):
                    attr_value = [attr_value]

                for value in attr_value:
                    if not data.attributes[value]:
                        attributes.append(attr_name)
                        break

        if attributes:
            attrs = self.__process_attrs(user_id, attributes)

            for attr_name, attr_value in attrs.items():
                data.attributes[attr_name] = attr_value

        return super().process(context, data)

    def __process_attrs(self, user_id, attributes):

        """
        This method converts given attributes

        @param user_id: user ID
        @param attributes: attributes for conversion

        @return converted attributes
        """

        result = dict()
        try:
            attrs = self.__adapters_manager.get_user_attributes(
                user_id, attributes
            )
        except (AdaptersManagerException, AdaptersManagerNotExistsException) as e: # noqa e501
            self.__logger.debug(e)
            attrs = dict()

        for attr_name, attr_value in attrs.items():
            satosa_attr = self.__attr_map[attr_name]

            if not attr_value:
                value = []
            elif isinstance(attr_value, str) or isinstance(attr_value, int):
                value = [attr_value]
            elif isinstance(attr_value, dict) or isinstance(attr_value, list):
                value = attr_value
            else:
                raise SATOSAError(
                    self.__class__.__name__
                    + '- Unsupported attribute type. Attribute name: '
                    + attr_name + ', Supported types: null, string, '
                                  'int, dict, list.'
                )

            if isinstance(satosa_attr, str):
                attr_array = [satosa_attr]
            elif isinstance(satosa_attr, list):
                attr_array = satosa_attr
            else:
                raise SATOSAError(
                    self.__class__.__name__
                    + '- Unsupported attribute type. Attribute name: '
                    + attr_name + ', Supported types: string, dict.'
                )

            self.__logger.debug(
                self.__class__.__name__
                + ': Perun attribute: ' + attr_name + ' was fetched. '
                'Value ' + ','.join(str(value)) +
                ' is being set to satosa attributes ' + ','.join(attr_array)
            )

            for attribute in attr_array:
                result[attribute] = value

        return result
