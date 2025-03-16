import hmac
import logging
import typing
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, Request

from .controller import controller
from .github import CommitInfo
from .settings import settings

_logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_github_signature(
    x_hub_signature_256: str | None, secret: bytes | None, body: bytes
) -> bool:
    if not secret:
        return True
    if not x_hub_signature_256:
        _logger.warning("Got payload without X-Hub-Signature-256")
        return False
    signature = "sha256=" + hmac.new(secret, body, "sha256").hexdigest()
    if not hmac.compare_digest(signature, x_hub_signature_256):
        _logger.warning("Got payload with invalid X-Hub-Signature-256")
        return False
    return True


def receive_push(background_tasks: BackgroundTasks, payload: typing.Any) -> None:
    repo = payload["repository"]["full_name"]
    target_branch = payload["ref"].split("/")[-1]
    if not settings.is_repo_and_branch_supported(repo, target_branch):
        _logger.debug(
            "Ignoring push payload for unsupported repo %s or target branch %s",
            repo,
            target_branch,
        )
        return
    background_tasks.add_task(
        controller.deploy_commit,
        CommitInfo(
            repo=repo,
            target_branch=target_branch,
            pr=None,
            git_commit=payload["after"],
        ),
    )


def receive_pull_request(
    background_tasks: BackgroundTasks, payload: typing.Any
) -> None:
    repo = payload["repository"]["full_name"]
    target_branch = payload["pull_request"]["base"]["ref"]
    if not settings.is_repo_and_branch_supported(repo, target_branch):
        _logger.debug(
            "Ignoring pull_request payload for unsupported repo %s or target branch %s",
            repo,
            target_branch,
        )
        return
    if payload["action"] in ("opened", "synchronize"):
        background_tasks.add_task(
            controller.deploy_commit,
            CommitInfo(
                repo=repo,
                target_branch=target_branch,
                pr=payload["pull_request"]["number"],
                git_commit=payload["pull_request"]["head"]["sha"],
            ),
        )
    elif payload["action"] in ("closed",):
        background_tasks.add_task(
            controller.undeploy_builds,
            repo=repo,
            pr=payload["pull_request"]["number"],
        )


@router.post("/webhooks/github")
async def receive_payload(
    background_tasks: BackgroundTasks,
    request: Request,
    x_github_event: Annotated[str, Header(...)],
    x_hub_signature_256: Annotated[str | None, Header(...)] = None,
) -> None:
    body = await request.body()
    if not _verify_github_signature(
        x_hub_signature_256, settings.github_webhook_secret, body
    ):
        return
    payload = await request.json()
    if x_github_event == "pull_request":
        receive_pull_request(background_tasks, payload)
    elif x_github_event == "push":
        receive_push(background_tasks, payload)
