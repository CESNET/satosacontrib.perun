import os
import logging

import xml.etree.ElementTree as ET
import requests
from satosa.micro_services.base import ResponseMicroService
from satosa.plugin_loader import load_backends
from satosa.satosa_config import SATOSAConfig

logger = logging.getLogger(__name__)


def get_idp_metadata(entity_id, federations):
    for fed in federations:
        file_path = "/tmp/{}.xml".format(fed.split("/")[-1])
        if not os.path.exists(file_path):
            fed_xml = requests.get(fed).text
            with open(file_path, "w") as writer:
                writer.writelines(fed_xml)
        metadata = ET.parse(file_path).find(
            './/{urn:oasis:names:tc:SAML:2.0:metadata}EntityDescriptor[@entityID="'
            + entity_id
            + '"]'
        )
        if metadata:
            return metadata
    return None


text_attributes = {
    "lang": "{http://www.w3.org/XML/1998/namespace}lang",
    "width": "width",
    "height": "height",
    "text": "text",
}


def find_texts(metadata, element_name):
    return [
        {
            attribute_key: (text.attrib[xml_key] if xml_key != "text" else text.text)
            for (attribute_key, xml_key) in text_attributes.items()
            if xml_key == "text" or xml_key in text.attrib
        }
        for text in metadata.findall(element_name)
    ]


class ContextAttributes(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("ContextAttributes is active")
        self.__federations = config.get("federations", [])
        self.__federation_backends = config.get("federation_backends", [])
        self.__allowed_requesters = config.get("allowed_requesters", None)
        self.__target_backend_attribute = config.get(
            "target_backend_attribute", "targetbackend"
        )
        self.__target_issuer_attributes = config.get(
            "target_issuer_attributes", ["targetissuer"]
        )

    def process(self, context, data):
        """
        Add target IdP data to attributes.
        :param context: request context
        :param data: the internal request
        """
        if (
            self.__allowed_requesters is None
            or data.requester in self.__allowed_requesters
        ):
            logger.info("Generating backend attributes for {}".format(data.requester))
            if context.target_backend in self.__federation_backends:
                metadata = get_idp_metadata(
                    data["auth_info"]["issuer"], self.__federations
                )
                if metadata:
                    data.attributes[self.__target_backend_attribute] = {
                        "display_name": find_texts(
                            metadata,
                            ".//{urn:oasis:names:tc:SAML:metadata:ui}DisplayName",
                        ),
                        "description": find_texts(
                            metadata,
                            ".//{urn:oasis:names:tc:SAML:metadata:ui}Description",
                        ),
                        "logo": find_texts(
                            metadata, ".//{urn:oasis:names:tc:SAML:metadata:ui}Logo"
                        ),
                    }
                else:
                    logger.info(
                        "SP {} not found in any federation: {}".format(
                            data["auth_info"]["issuer"], ",".join(self.__federations)
                        )
                    )
            else:
                config_file = os.environ.get("SATOSA_CONFIG", "proxy_conf.yaml")
                satosa_config = SATOSAConfig(config_file)
                satosa_config["BACKEND_MODULES"] = [
                    backend
                    for backend in satosa_config["BACKEND_MODULES"]
                    if backend["name"] not in self.__federation_backends
                ]
                backend_modules = load_backends(
                    satosa_config, None, satosa_config["INTERNAL_ATTRIBUTES"]
                )
                target_backends = [
                    backend
                    for backend in backend_modules
                    if backend.name == context.target_backend
                ]
                if target_backends:
                    target_backend = target_backends[0]
                    entity_descriptors = target_backend.get_metadata_desc()
                    if entity_descriptors:
                        entity_descriptor = entity_descriptors[0].to_dict()
                        if (
                            "service" in entity_descriptor
                            and "idp" in entity_descriptor["service"]
                            and "ui_info" in entity_descriptor["service"]["idp"]
                        ):
                            data.attributes[
                                self.__target_backend_attribute
                            ] = entity_descriptor["service"]["idp"]["ui_info"]

            for target_issuer_attribute in self.__target_issuer_attributes:
                data.attributes[target_issuer_attribute] = data["auth_info"]["issuer"]
        else:
            logger.info("Skipping backend attributes for {}".format(data.requester))

        return super().process(context, data)
