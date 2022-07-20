import logging
from satosa.micro_services.base import ResponseMicroService
from saml2.saml import NAMEID_FORMAT_PERSISTENT

logger = logging.getLogger(__name__)


class NameIDAttribute(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("NameIDAttribute is active")
        self.__nameid_attribute = config["nameid_attribute"]
        self.__sp_entity_id = config["sp_entity_id"]
        self.__subject_attribute = config.get("subject_attribute", None)

    def process(self, context, data):
        """
        Copy SAML nameID to an internal attribute.
        :param context: request context
        :param data: the internal request
        """
        if data.subject_type == NAMEID_FORMAT_PERSISTENT and data.subject_id:
            data.attributes[self.__nameid_attribute] = "{}!{}!{}".format(
                data["auth_info"]["issuer"], self.__sp_entity_id, data.subject_id
            )

        if self.__subject_attribute:
            # instead of e.g. user_id_from_attrs: [publicid]
            data.subject_id = data.attributes[self.__subject_attribute][0]

        return super().process(context, data)
