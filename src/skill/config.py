import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    """Bot Configuration"""

    HOST = os.getenv("HOST", "localhost")
    PORT = int(os.getenv("PORT", 8080))

    # DO NOT CHANGE THIS KEYS!!
    # These keys are used to validate the bot's identity
    # and must match these named as Bot configuration expects
    APP_ID = os.getenv("BOT_APP_ID")
    APP_PASSWORD = os.getenv("BOT_PASSWORD")
    APP_TENANTID = os.getenv("BOT_TENANT_ID")
    APP_TYPE = os.getenv("APP_TYPE", "singletenant")

    TEAMS_APP_ID = os.getenv("TEAMS_APP_ID")
    TEAMS_APP_NAME = os.getenv("TEAMS_APP_NAME")

    # Required for Copilot Skill
    # Can be a list of allowed agent Ids,
    # or "*" to allow any agent
    ALLOWED_CALLERS = os.getenv("ALLOWED_CALLERS", ["*"])

    def validate(self):
        if not self.HOST or not self.PORT:
            raise Exception(
                "Missing required configuration. HOST and PORT must be set."
            )
        if not self.APP_ID or not self.APP_PASSWORD or not self.APP_TENANTID:
            raise Exception(
                "Missing required configuration. APP_ID, APP_PASSWORD, and APP_TENANT_ID must be set."
            )
        if not self.ALLOWED_CALLERS:
            raise Exception(
                "Missing required configuration. ALLOWED_CALLERS must be set."
            )
        if not self.TEAMS_APP_ID or not self.TEAMS_APP_NAME:
            raise Exception(
                "Missing required configuration. TEAMS_APP_ID and TEAMS_APP_NAME must be set."
            )


config = Config()
config.validate()
