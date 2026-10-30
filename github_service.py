import requests
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv
import base64


def pull_xml_from_github(file_path: str, branch: str):
    load_dotenv()
    owner = os.getenv("GITHUB_OWNER")
    repo = os.getenv("GITHUB_REPO")
    pat = os.getenv("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
    }
    response = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
    response.raise_for_status()
    data = response.json()
    sha = data["sha"]
    encoded_content = data["content"]
    encoding = data["encoding"]
    decoded_bytes = base64.b64decode(encoded_content)
    xml_content = decoded_bytes.decode("utf-8")
    try:
        root = ET.fromstring(xml_content)
        print("XML geçerli:", root.tag)

    except ET.ParseError as error:
        raise ValueError(f"XML formatı hatalı: {error}") from error

    return {
        "success": True,
        "xml_content": xml_content,
        "file_path": file_path,
        "branch": branch,
        "sha": sha,
    }


def push_xml_to_github(
    file_path: str,
    branch: str,
    xml_content: str,
    sha: str | None = None,
    commit_message: str | None = None,
):
    load_dotenv()

    owner = os.getenv("GITHUB_OWNER")
    repo = os.getenv("GITHUB_REPO")
    pat = os.getenv("GITHUB_TOKEN")

    if not all([owner, repo, pat]):
        raise ValueError("GitHub configuration is missing.")

    # XML validation
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as error:
        raise ValueError(f"Invalid XML: {error}") from error

    if not file_path or not file_path.lower().endswith(".xml"):
        raise ValueError("A valid XML file path is required.")

    if not branch:
        raise ValueError("GitHub branch is required.")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Check whether the file already exists
    current_response = requests.get(
        url, headers=headers, params={"ref": branch}, timeout=15
    )

    current_sha = None

    if current_response.status_code == 200:
        current_data = current_response.json()
        current_sha = current_data["sha"]

        current_content = base64.b64decode(current_data["content"]).decode("utf-8")

        if sha is not None and sha != current_sha:
            raise ValueError("GitHub XML has changed. Pull the latest version first.")
        # No changes → no new commit
        if current_content == xml_content:
            return {
                "success": True,
                "changed": False,
                "message": "XML is already up to date.",
                "sha": current_sha,
                "commit_sha": None,
            }

    elif current_response.status_code != 404:
        current_response.raise_for_status()
    elif sha is not None:
        raise ValueError("GitHub XML was deleted or moved during Apply.")

    encoded_content = base64.b64encode(xml_content.encode("utf-8")).decode("ascii")

    filename = file_path.rsplit("/", 1)[-1]

    payload = {
        "message": commit_message
        or (
            f"Update XML backup: {file_path}"
            if current_sha
            else f"Initial XML backup: {file_path}"
        ),
        "content": encoded_content,
        "branch": branch,
    }

    if current_sha:
        payload["sha"] = current_sha

    response = requests.put(url, headers=headers, json=payload, timeout=15)

    response.raise_for_status()
    data = response.json()

    return {
        "success": True,
        "changed": True,
        "message": f"{filename} backed up successfully.",
        "sha": data["content"]["sha"],
        "commit_sha": data["commit"]["sha"],
    }


