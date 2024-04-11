import asyncio
import os
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx
import requests
from loguru import logger

PORT_API_URL = "https://api.getport.io/v1"
PORT_CLIENT_ID = os.getenv("PORT_CLIENT_ID")
PORT_CLIENT_SECRET = os.getenv("PORT_CLIENT_SECRET")
REPOSITORY_NAME = os.getenv("REPO_NAME")

CODEOWNERS_PATTERN_BLUEPRINT = "githubCodeownersPattern"
CODEOWNERS_BLUEPRINT = "githubCodeowners"

CODEOWNERS_FILE_PATHS = [
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
]


def get_codeowner_file():
    for path in CODEOWNERS_FILE_PATHS:
        if os.path.isfile(path):
            return path

    return None


CODEOWNERS_FILE = get_codeowner_file()

if not CODEOWNERS_FILE:
    logger.error("Error parsing file: CODEOWNERS not found in the right location")
    sys.exit(1)


# Get Port Access Token
credentials = {"clientId": PORT_CLIENT_ID, "clientSecret": PORT_CLIENT_SECRET}
token_response = requests.post(f"{PORT_API_URL}/auth/access_token", json=credentials)
if not token_response.ok:
    logger.error(f"Error retrieving access token: {token_response.json()}")
    sys.exit(1)

access_token = token_response.json()["accessToken"]

# You can now use the value in access_token when making further requests
headers = {"Authorization": f"Bearer {access_token}"}


async def add_entity_to_port(client: httpx.AsyncClient, blueprint_id, entity_object):
    """A function to create the passed entity in Port

    Params
    --------------
    blueprint_id: str
        The blueprint id to create the entity in Port

    entity_object: dict
        The entity to add in your Port catalog

    Returns
    --------------
    response: dict
        The response object after calling the webhook
    """
    logger.info(f"Adding entity to Port: {entity_object}")
    response = await client.post(
        (
            f"{PORT_API_URL}/blueprints/"
            f"{blueprint_id}/entities?upsert=true&merge=true"
        ),
        json=entity_object,
        headers=headers,
    )
    if not response.is_success:
        logger.info("Ingesting {blueprint_id} entity to port failed, skipping...")
    logger.info(f"Added entity to Port: {entity_object}")


def remove_comment_lines(text: list[str]):
    COMMENT_CHAR = "#"
    for line in text:
        if (current_line := line.strip()) and not current_line.startswith(COMMENT_CHAR):
            yield line


def split_pattern_into_tokens(text: str):
    return text.split()


EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
TEAM_REGEX = r"\@[\w|-]+\/[\w+|-]+"
USERNAME_REGEX = r"\@[\w|-]+"


class GithubEntityType(StrEnum):
    USERNAME = "username"
    EMAIL = "email"
    TEAM = "team"


@dataclass
class GithubEntity:
    type: GithubEntityType
    value: str
    pattern: str


PATTERNS = {
    GithubEntityType.USERNAME: USERNAME_REGEX,
    GithubEntityType.EMAIL: EMAIL_REGEX,
    GithubEntityType.TEAM: TEAM_REGEX,
}

def convert_to_valid_characters(input_string):
    pattern = r"[^A-Za-z0-9@_.:\\/=-]"
    output_string = re.sub(pattern, "@", input_string)

    return output_string

def parse_string_to_entity_type(text: str):
    for key, value in PATTERNS.items():
        if re.fullmatch(value, text):
            return key, text

    return None


def create_entity_from_value(
    entity_type: GithubEntityType, value: str, pattern: str
) -> GithubEntity:
    if entity_type == GithubEntityType.USERNAME:
        value = value.replace("@", "")
    entity = GithubEntity(entity_type, value, pattern)
    return entity


async def provide_entities():
    with open(CODEOWNERS_FILE) as codeowners:
        # CODEOWNERS files aren't supposed to be more than 3mb so we can
        # safely load into memory
        cleaned_lines = remove_comment_lines(codeowners.readlines())

    for cleaned_line in cleaned_lines:
        tokens = split_pattern_into_tokens(cleaned_line)
        pattern, *entities = tokens
        valid_entries = list(filter(None, map(parse_string_to_entity_type, entities)))
        for entry in valid_entries:
            yield create_entity_from_value(*entry, pattern)


def prepare_codeowner_pattern_entity(entity: GithubEntity, codeowner: dict[str, Any]):

    entity_object = {
        "identifier": convert_to_valid_characters(entity.pattern),
        "title": f"{entity.pattern} | {REPOSITORY_NAME}",
        "properties": {},
        "relations": {
            "team": [entity.value] if entity.type == GithubEntityType.TEAM else [],
            "service": REPOSITORY_NAME,
            "user": [entity.value]
            if entity.type in [GithubEntityType.USERNAME, GithubEntityType.EMAIL]
            else [],
            "codeownersFile": codeowner["identifier"],
        },
    }

    return entity_object


def crunch_entities(existing_entities: dict[str, Any], entity: dict[str, Any]):
    if entity["identifier"] in existing_entities:
        teams = set(
            [
                *entity["relations"]["team"],
                *existing_entities[entity["identifier"]]["relations"]["team"],
            ]
        )
        users = set(
            [
                *entity["relations"]["user"],
                *existing_entities[entity["identifier"]]["relations"]["user"],
            ]
        )
        existing_entities[entity["identifier"]]["relations"]["team"] = list(teams)
        existing_entities[entity["identifier"]]["relations"]["user"] = list(users)
    else:
        existing_entities[entity["identifier"]] = entity

    return existing_entities


async def main():
    logger.info("Starting Port integration")
    crunched_entities: dict[str, Any] = {}
    async with httpx.AsyncClient() as client:
        entities = provide_entities()
        codeowner_entity = {
            "identifier": REPOSITORY_NAME,
            "title": f"Codeowners in {REPOSITORY_NAME}",
            "properties": {"location": CODEOWNERS_FILE},
            "relations": {"service": REPOSITORY_NAME},
        }
        await add_entity_to_port(client, CODEOWNERS_BLUEPRINT, codeowner_entity)

        async for pattern in entities:
            pattern_entity = prepare_codeowner_pattern_entity(pattern, codeowner_entity)
            crunched_entities = crunch_entities(crunched_entities, pattern_entity)

        for entity in crunched_entities.values():
            await add_entity_to_port(client, CODEOWNERS_PATTERN_BLUEPRINT, entity)

    logger.info("Finished Port integration")


if __name__ == "__main__":
    asyncio.run(main())
