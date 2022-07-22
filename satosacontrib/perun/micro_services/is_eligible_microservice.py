from datetime import datetime

from dateutil.relativedelta import relativedelta
from perun.connector.utils.Logger import Logger
from satosa.context import Context
from satosa.internal import InternalData
from satosa.micro_services.base import ResponseMicroService
from satosa.response import Redirect

from satosacontrib.perun.utils.PerunConstants import PerunConstants

logger = Logger.get_logger(__name__)


class IsEligible(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("is active")

        self.__TRIGGER_ATTRIBUTE = "trigger_attribute"
        self.__ELIGIBLE_LAST_SEEN_TIMESTAMP_ATTRIBUTE = (
            "eligible_last_seen_timestamp_attribute"
        )
        self.__VALIDITY_PERIOD_MONTHS = "validity_period_months"

        self.__filter_config = config["filter_config"]

        self.__trigger_attribute = self.__filter_config[
            self.__TRIGGER_ATTRIBUTE
        ]
        self.__timestamp_attribute = self.__filter_config[
            self.__ELIGIBLE_LAST_SEEN_TIMESTAMP_ATTRIBUTE
        ]
        self.__validity_period_months = self.__filter_config.get(
            self.__VALIDITY_PERIOD_MONTHS, 12
        )

        self.__unauthorized_redirect_url = config["unauthorized_redirect_url"]

    def process(self, context: Context, data: InternalData):
        """
        Obtains timestamp of the last eligible user access and authorizes user
        for further proceeding if it's not older than the pre-configured
        validity period.

        @param context: object for sharing proxy data through the current
                        request
        @param data: data carried between frontend and backend,
                     namely timestamp of the last eligible access
        """
        attributes_released_to_sp = data.attributes.get(
            PerunConstants.DESTINATION, {}
        ).get(PerunConstants.DESTINATION_ATTRIBUTES, {})

        if self.__trigger_attribute not in attributes_released_to_sp:
            logger.info(
                "SP does not consume the trigger attribute"
                f" '{self.__trigger_attribute}'. Terminating execution of this"
                " microservice."
            )
            return

        last_seen_eligible_timestamp_string = data.attributes.get(
            PerunConstants.ATTRIBUTES, {}
        ).get(self.__timestamp_attribute)
        if last_seen_eligible_timestamp_string:
            last_seen_eligible_timestamp = datetime.fromisoformat(
                last_seen_eligible_timestamp_string[0]
            )
        else:
            logger.info(
                "Timestamp of the last seen eligibility is empty, cannot let"
                " user go through. Redirecting to unauthorized explanation"
                " page."
            )
            return self.unauthorized()

        oldest_eligible_timestamp = datetime.now() - relativedelta(
            months=self.__validity_period_months
        )
        if last_seen_eligible_timestamp < oldest_eligible_timestamp:
            logger.info(
                f"Last seen eligibility timestamp"
                f" '{last_seen_eligible_timestamp}' is older than"
                f" {self.__validity_period_months} month(s), which is the"
                f" maximum allowed period of time. Redirecting to unauthorized"
                f" explanation page."
            )
            return self.unauthorized()
        logger.info(
            f"Last seen eligibility timestamp '{last_seen_eligible_timestamp}'"
            f" is not older than {self.__validity_period_months} month(s),"
            f" which is the maximum allowed period of time. Continuing with"
            f" the next check."
        )

        return super().process(context, data)

    def unauthorized(self):
        """
        Redirects user to the pre-configured error page with more details.

        @return: Redirect to a pre-configured url with "unauthorized" page
        """
        return Redirect(self.__unauthorized_redirect_url)
