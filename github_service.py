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


def get_xml_history(file_path: str, branch: str):
    load_dotenv()

    owner = os.getenv("GITHUB_OWNER")
    repo = os.getenv("GITHUB_REPO")
    pat = os.getenv("GITHUB_TOKEN")

    if not all([owner, repo, pat]):
        raise ValueError("GitHub configuration is missing.")

    if not file_path.startswith("xml-definitions/") or not file_path.endswith(".xml"):
        raise ValueError("Invalid XML file path.")

    if not branch:
        raise ValueError("GitHub branch is required.")

    url = f"https://api.github.com/repos/{owner}/{repo}/commits"

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(
        url,
        headers=headers,
        params={
            "path": file_path,
            "sha": branch,
            "per_page": 50,
        },
        timeout=15,
    )
    response.raise_for_status()

    history = []

    for item in response.json():
        commit = item["commit"]

        history.append(
            {
                "sha": item["sha"],
                "message": commit["message"],
                "author": commit["author"]["name"] if commit["author"] else None,
                "date": commit["author"]["date"] if commit["author"] else None,
                "url": item["html_url"],
            }
        )

    return {
        "success": True,
        "file_path": file_path,
        "branch": branch,
        "total": len(history),
        "history": history,
    }


def get_xml_commit_diff(file_path: str, commit_sha: str):
    load_dotenv()

    owner = os.getenv("GITHUB_OWNER")
    repo = os.getenv("GITHUB_REPO")
    pat = os.getenv("GITHUB_TOKEN")

    if not all([owner, repo, pat]):
        raise ValueError("GitHub configuration is missing.")

    if (
        not file_path
        or not file_path.lower().endswith(".xml")
        or file_path.startswith("/")
        or any(part in ("", ".", "..") for part in file_path.split("/"))
    ):
        raise ValueError("Invalid XML file path.")

    import re

    if not re.fullmatch(r"[a-fA-F0-9]{40}", commit_sha):
        raise ValueError("Invalid commit SHA.")

    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}"

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()

    commit_data = response.json()

    matching_file = next(
        (
            item
            for item in commit_data.get("files", [])
            if item["filename"] == file_path
        ),
        None,
    )

    if matching_file is None:
        raise ValueError("The selected commit does not contain changes to this XML.")

    return {
        "success": True,
        "file_path": file_path,
        "commit_sha": commit_sha,
        "message": commit_data["commit"]["message"],
        "date": commit_data["commit"]["author"]["date"],
        "status": matching_file["status"],
        "additions": matching_file["additions"],
        "deletions": matching_file["deletions"],
        "patch": matching_file.get("patch"),
        "commit_url": commit_data["html_url"],
    }


if __name__ == "__main__":
    result = pull_xml_from_github(
        "xml-definitions/sample.xml", "refactor/local-witadmin"
    )

    print("GitHub'daki güncel XML:")
    print(result["xml_content"])

    print("Güncel SHA:", result["sha"])


def list_github_xml_files(branch: str):
    load_dotenv()

    owner = os.getenv("GITHUB_OWNER")
    repo = os.getenv("GITHUB_REPO")
    pat = os.getenv("GITHUB_TOKEN")

    if not all([owner, repo, pat]):
        raise ValueError("GitHub environment variables are missing.")

    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"

    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
    }

    response = requests.get(
        url,
        headers=headers,
        params={"recursive": "1"},
        timeout=15,
    )
    response.raise_for_status()

    data = response.json()

    if data.get("truncated"):
        raise ValueError("GitHub repository tree is too large to list completely.")

    xml_files = sorted(
        item["path"]
        for item in data.get("tree", [])
        if item.get("type") == "blob"
        and item.get("path", "").lower().endswith(".xml")
        and item.get("path", "").startswith("xml-definitions/")
    )

    return {
        "success": True,
        "branch": branch,
        "files": xml_files,
        "total": len(xml_files),
    }
