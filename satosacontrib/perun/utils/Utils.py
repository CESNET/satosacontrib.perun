import hmac
import json
import random
import string
import requests
import time

from perun.connector.utils.Logger import Logger
from jwcrypto import jwk, jwt
from jwcrypto.jwk import JWKSet, JWK
from satosa.internal import InternalData
from satosa.context import Context
from satosa.response import Redirect


class Utils:
    @staticmethod
    def generate_nonce() -> str:
        letters = string.ascii_lowercase
        actual_time = str(int(time.time()))
        rand = random.SystemRandom()
        return actual_time + "".join(rand.choice(letters) for _ in range(54))

    @staticmethod
    def __import_keys(file_path: str) -> JWKSet:
        jwk_set = jwk.JWKSet()
        with open(file_path, "r") as keystore:
            jwk_set.import_keyset(keystore.read())
        return jwk_set

    @staticmethod
    def __get_signing_jwk(keystore: str, key_id: str) -> JWK:
        jwk_set = Utils.__import_keys(keystore)
        return jwk_set.get_key(key_id)

    @staticmethod
    def __get_jwt(data: dict[str, str], jwk_key: JWK, token_alg: str):
        token = jwt.JWT(header={"alg": token_alg, "typ": "JWT"}, claims=data)
        token.make_signed_token(jwk_key)
        return token.serialize()

    @staticmethod
    def sign_data(
        data: dict[str, str], keystore: str, key_id: str, token_alg: str
    ) -> str:
        token_signing_key = Utils.__get_signing_jwk(keystore, key_id)

        return Utils.__get_jwt(data, token_signing_key, token_alg)

    @staticmethod
    def secure_redirect_with_nonce(
        context: Context,
        data: InternalData,
        request_data: dict[str, str],
        url: str,
        signing_cfg: dict[str, str],
        caller_name: str,
    ) -> Redirect:
        """
        Performs secure redirect to given url using signed data with nonce

        @param caller_name: name of invoking microservice
        @param signing_cfg: config with data necessary for signing
        @param context: object for sharing proxy data through the current
                        request
        @param data: data carried between frontend and backend
        @param request_data: data to be signed, it also carries nonce
        @param url: url where secure redirect should be performed
        @return: secure redirect to the desired url using signed request
        with nonce
        """
        nonce = Utils.generate_nonce()
        request_data["nonce"] = nonce
        request_data["time"] = str(int(time.time()))
        signed_request_data = Utils.sign_data(
            request_data,
            signing_cfg["keystore"],
            signing_cfg["key_id"],
            signing_cfg["token_alg"],
        )
        data["nonce"] = nonce
        context.state[caller_name] = data.to_dict()

        return Redirect(f"{url}/{signed_request_data}")

    @staticmethod
    def handle_registration_response(
        context: Context,
        signing_cfg: dict[str, str],
        registration_result_url: str,
        caller_name: str,
    ) -> tuple[Context, InternalData]:
        """
        Handles response from external service with the result of registration
        @param caller_name: name of invoking microservice
        @param registration_result_url: url where result of registration is
               sent
        @param signing_cfg: config with data necessary for signing
        @param context: request context
        @return: loaded newly registered group if registration was successful
        """
        saved_state = context.state[caller_name]
        internal_response = InternalData.from_dict(saved_state)
        request_data = {
            "nonce": internal_response["nonce"],
            "time": str(int(time.time())),
        }
        signed_data = Utils.sign_data(
            request_data,
            signing_cfg["keystore"],
            signing_cfg["key_id"],
            signing_cfg["token_alg"],
        )
        request = f"{registration_result_url}/{signed_data}"
        response = requests.get(request)
        response_dict = json.loads(response.text)

        if response_dict["result"] != "okay" or not hmac.compare_digest(
            response_dict["nonce"], internal_response["nonce"]
        ):
            logger = Logger.get_logger(__name__)
            logger.info("Registration was unsuccessful.")

        return context, internal_response
