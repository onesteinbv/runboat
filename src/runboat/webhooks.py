import hmac
import logging
import re
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
    if not settings.is_repo_and_branch_supported(
        repo, target_branch, check_run=None, package=None
    ):
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
    params = {}
    if payload["action"] in ("opened", "synchronize"):
        params.update(check_run=None, package=None)
    if not settings.is_repo_and_branch_supported(repo, target_branch, **params):
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


def receive_check_run(background_tasks: BackgroundTasks, payload: typing.Any) -> None:
    repo = payload["repository"]["full_name"]
    check_run = payload["check_run"]["name"]
    if payload["action"] != "completed":
        return
    if payload["check_run"]["conclusion"] != "success":
        return

    target_branch = payload["check_run"]["check_suite"].get("head_branch", None)
    if not target_branch:
        return
    if not settings.is_repo_and_branch_supported(
        repo, target_branch, check_run=check_run, package=None
    ):
        _logger.debug(
            "Ignoring check_run payload for unsupported repo %s or target branch %s",
            repo,
            target_branch,
        )
        return
    commit = payload["check_run"]["head_sha"]
    background_tasks.add_task(
        controller.deploy_commit,
        CommitInfo(
            repo=repo,
            target_branch=target_branch,
            pr=None,
            check_run=check_run,
            git_commit=commit,
        ),
    )


def receive_package(background_tasks: BackgroundTasks, payload: typing.Any) -> None:
    repo = payload["repository"]["full_name"]
    package = payload["package"]["name"]
    if payload["action"] != "published":
        return

    container_metadata = payload["package"]["package_version"]["container_metadata"]
    match = re.match(r"^([^-]+)-(\d+)-([^-]+)$", container_metadata["tag"]["name"])
    if not match:
        return
    semver, pr, commit = match.groups()

    if not settings.is_repo_and_branch_supported(
        repo, semver, check_run=None, package=package
    ):
        _logger.debug(
            "Ignoring check_run payload for unsupported repo %s or target branch %s",
            repo,
            semver,
        )
        return
    background_tasks.add_task(
        controller.deploy_commit,
        CommitInfo(
            repo=repo,
            target_branch=semver,
            pr=pr,
            package=package,
            git_commit=commit,
        ),
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
    elif x_github_event == "check_run":
        receive_check_run(background_tasks, payload)
    elif x_github_event == "package":
        receive_package(background_tasks, payload)
