from perun.connector.adapters.AdaptersManager import AdaptersManager
from satosa.context import Context
from satosa.internal import InternalData

from unittest.mock import patch, MagicMock
from satosacontrib.perun.utils.ConfigStore import ConfigStore


class TestContext(Context):
    def __init__(self):
        super().__init__()


class TestData(InternalData):
    def __init__(self, data, attributes):
        super().__init__()
        self.data = data
        self.attributes = attributes
        self.auth_info = None


class Loader:
    def __init__(self, config, global_config, name_of_microservice):
        self.config = config
        self.global_config = global_config
        self.name = name_of_microservice

    @patch("utils.ConfigStore.ConfigStore.get_global_cfg")
    @patch("utils.ConfigStore.ConfigStore.get_attributes_map")
    @patch("perun.connector.adapters.AdaptersManager.AdaptersManager.__init__")
    def create_mocked_instance(self, mock_request, mock_request2, mock_request3): # noqa e501
        ConfigStore.get_global_cfg = MagicMock(return_value=self.global_config)
        ConfigStore.get_attributes_map = MagicMock(return_value=None)
        AdaptersManager.__init__ = MagicMock(return_value=None)

        return globals()[self.name](self.config, self.name, self.name + "Url")
