from unittest.mock import patch, MagicMock

from perun.connector.adapters.AdaptersManager import AdaptersManager
from satosa.context import Context
from satosa.internal import InternalData
import satosacontrib.perun.micro_services

from satosacontrib.perun.utils.ConfigStore import ConfigStore


class TestContext(Context):
    __test__ = False

    def __init__(self):
        super().__init__()


class TestData(InternalData):
    __test__ = False

    def __init__(self, data, attributes):
        super().__init__()
        self.data = data
        self.attributes = attributes
        self.auth_info = None


class Loader:
    GLOBAL_CONFIG = {
        "perun_user_id_attribute": "example_user_id",
        "perun_login_attribute": "example_login",
        "attrs_cfg_path": "example_path",
        "adapters_manager": "adapters manager cfg info",
        "jwk": {
            "keystore": "example_keystore",
            "keyid": "example_keyid",
            "token_alg": "example_token_alg",
        },
    }

    def __init__(self, config, name_of_microservice):
        self.config = config
        self.name = name_of_microservice

    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_global_cfg")
    @patch("satosacontrib.perun.utils.ConfigStore.ConfigStore.get_attributes_map")
    @patch("perun.connector.adapters.AdaptersManager.AdaptersManager.__init__")
    def create_mocked_instance(
        self, mock_request, mock_request2, mock_request3
    ):  # noqa e501
        ConfigStore.get_global_cfg = MagicMock(return_value=Loader.GLOBAL_CONFIG)
        ConfigStore.get_attributes_map = MagicMock(return_value=None)
        AdaptersManager.__init__ = MagicMock(return_value=None)
        my_class = getattr(satosacontrib.perun.micro_services, self.name)
        return my_class(self.config, self.name, self.name + "Url")
