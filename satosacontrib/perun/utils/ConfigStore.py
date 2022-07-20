import os

import yaml


class ConfigStore:
    __global_cfg_current_file = None
    __global_config = None

    __global_attributes_map_file = None
    __global_attributes_map = None

    @staticmethod
    def __load_cfg(cfg_filepath, property_name):
        if not os.path.exists(cfg_filepath):
            raise Exception("Config: missing config file: ", cfg_filepath)
        with open(cfg_filepath, "r") as f:
            setattr(ConfigStore, property_name, yaml.safe_load(f))

    @staticmethod
    def get_global_cfg(filepath):
        if (
            ConfigStore.__global_config is None
            or ConfigStore.__global_cfg_current_file != filepath
        ):
            ConfigStore.__load_cfg(filepath, "_ConfigStore__global_config")
            ConfigStore.__global_cfg_current_file = filepath
        return ConfigStore.__global_config

    @staticmethod
    def get_attributes_map(filepath):
        if (
            ConfigStore.__global_attributes_map is None
            or ConfigStore.__global_attributes_map_file != filepath
        ):
            ConfigStore.__load_cfg(filepath, "_ConfigStore__global_attributes_map")
            ConfigStore.__global_attributes_map_file = filepath
        return ConfigStore.__global_attributes_map
