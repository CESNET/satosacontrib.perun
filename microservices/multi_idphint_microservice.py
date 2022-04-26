import logging
import base64
import json
import urllib.parse
from satosa.context import Context
from satosa.internal import InternalData
from satosa.backends.saml2 import SAMLBackend

from satosa.micro_services.base import RequestMicroService
from satosa.exception import SATOSAError

logger = logging.getLogger(__name__)


class MultiIdpHintingError(SATOSAError):
    """SATOSA exception raised by CustomRouting rules"""


def get_wayf_filter(entity_ids):
    return base64.urlsafe_b64encode(
        json.dumps(
            {
                "ver": "2",
                "allowFeeds": {
                    "eduID.cz": {"allowIdPs": entity_ids},
                    "eduGAIN": {"allowIdPs": entity_ids},
                    "SocialIdPs": {"allowIdPs": entity_ids},
                    "StandaloneIdP": {"allowIdPs": []},
                    "Haka": {"allowIdPs": []},
                },
            }
        ).encode("utf-8")
    ).decode("utf-8")


class MultiIdpHinting(RequestMicroService):
    """Process multivalued idphint"""

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("MultiIdpHinting is active")
        self.__entity_id_mapping = config.get("entity_id_mapping", {})

    def process(self, context: Context, data: InternalData):
        qs_params = context.qs_params
        if qs_params and "idphint" in qs_params and "," in qs_params["idphint"]:
            entity_ids = qs_params["idphint"].split(",")
            if self.__entity_id_mapping:
                entity_ids = [
                    self.__entity_id_mapping.get(entity_id, entity_id)
                    for entity_id in entity_ids
                ]
            wayf_filter = get_wayf_filter(entity_ids)
            parsed = urllib.parse.urlparse("https://ds.eduid.cz/wayf.php?")
            url = parsed._replace(query="filter={}".format(wayf_filter)).geturl()
            logger.info(
                "multivalued idphint detected, using DS filter {}".format(wayf_filter)
            )
            context.decorate(SAMLBackend.KEY_SAML_DISCOVERY_SERVICE_URL, url)
            del context.qs_params["idphint"]
        return super().process(context, data)
