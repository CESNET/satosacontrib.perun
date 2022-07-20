import logging

from satosa.micro_services.base import ResponseMicroService

logger = logging.getLogger(__name__)


class CardinalitySingle(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("CardinalitySingle is active")
        self.attributes = config["attributes"]

    def process(self, context, data):
        """
        Convert single-valued attributes from lists to strings.
        :param context: request context
        :param data: the internal request
        """

        for single_valued in self.attributes:
            if single_valued in data.attributes and data.attributes[single_valued]:
                data.attributes[single_valued] = data.attributes[single_valued][0]
            elif single_valued in data.attributes:
                del data.attributes[single_valued]

        return super().process(context, data)
