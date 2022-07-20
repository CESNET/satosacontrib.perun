import logging
import sqlalchemy
from sqlalchemy.dialects.postgresql import insert
from datetime import date

from satosa.micro_services.base import ResponseMicroService

logger = logging.getLogger(__name__)


class ProxyStatistics(ResponseMicroService):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = config["user_identificator"]
        self.stats_user = config["stats_user"]
        self.stats_password = config["stats_password"]
        self.stats_db = config["stats_db"]
        self.hostname = config["stats_hostname"]
        self.port = config["stats_port"]
        self.driver = config["driver"]
        self.dialect = config["dialect"]
        logger.info("ProxyStatistics are active")

    def _get_id_from_identifier(self, cnxn, table, entity, id_column):
        identifier = entity["id"]
        name = entity["name"]
        insert_stmt = insert(table).values(identifier=identifier, name=name)
        if name is None or name == "":
            insert_stmt = insert_stmt.on_conflict_do_nothing()
        else:
            insert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=["identifier"], set_=dict(name=name)
            )
        cnxn.execute(insert_stmt)

        result = cnxn.execute(
            sqlalchemy.select(getattr(table.columns, id_column)).where(
                table.columns.identifier == identifier
            )
        )
        return result.scalar()

    def process(self, context, internal_response):
        data = dict(internal_response)
        idp = data["auth_info"]["issuer"]
        sp = data["requester"]
        sp_name = data["requester_name"][0]["text"]
        if sp_name is None:
            sp_name = ""
        user = data["subject_id"]

        if self.driver:
            self.driver = f"+{self.driver}"
        engine = sqlalchemy.create_engine(
            f"{self.dialect}{self.driver}://{self.stats_user}:{self.stats_password}@{self.hostname}:{self.port}/"
            f"{self.stats_db}"
        )
        cnxn = engine.connect()
        metadata = sqlalchemy.MetaData()
        statistics_per_user = sqlalchemy.Table(
            "statistics_per_user", metadata, autoload=True, autoload_with=engine
        )
        statistics_idp = sqlalchemy.Table(
            "statistics_idp", metadata, autoload=True, autoload_with=engine
        )
        statistics_sp = sqlalchemy.Table(
            "statistics_sp", metadata, autoload=True, autoload_with=engine
        )

        entities = {"IDP": {"id": idp, "name": ""}, "SP": {"id": sp, "name": sp_name}}
        sides = {"IDP": statistics_idp, "SP": statistics_sp}
        side_ids = {"IDP": "idp_id", "SP": "sp_id"}
        ids = {}
        for side in sides:
            table = sides[side]
            ids[side_ids[side]] = self._get_id_from_identifier(
                cnxn, table, entities[side], side_ids[side]
            )

        fields = {"day": date.today().strftime("%Y-%m-%d"), "logins": 1, "user": user}
        fields.update(ids)

        insert_stmt = insert(statistics_per_user).values(**fields)
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["day", "idp_id", "sp_id", "user"],
            set_={statistics_per_user.columns.logins: insert_stmt.excluded.logins + 1},
        )
        cnxn.execute(insert_stmt)

        logger.info(f"User {user} used IdP {idp} to log into SP {sp}")

        return super().process(context, internal_response)
