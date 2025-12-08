import os
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests


class DockerhubClient:
    BASE_URL = "https://hub.docker.com/v2"
    ENDPOINTS = {
        "auth": "/auth/token",
        "repositories": "/namespaces/{namespace}/repositories",
        "repository": "/namespaces/{namespace}/repositories/{repository}",
        "tags": "/namespaces/{namespace}/repositories/{repository}/tags",
        "tag": "/namespaces/{namespace}/repositories/{repository}/tags/{tag}",
    }

    def __init__(self, identifier: str = None, secret: str = None):
        self.identifier = identifier or os.getenv("DOCKERHUB_USERNAME")
        if not self.identifier:
            raise ValueError(
                "Docker Hub login identifier (username or organization) must be provided as an argument or using the "
                "environment variable 'DOCKERHUB_USERNAME'."
            )
        self.secret = secret or os.getenv("DOCKERHUB_PASSWORD")
        if not self.secret:
            raise ValueError(
                "Docker Hub login secret (password, PAT, or OAT) must be provided as an argument or using the "
                "environment variable 'DOCKERHUB_PASSWORD'."
            )

        self.token_expiration = datetime.now() + timedelta(minutes=10)
        self.access_token = self.create_token(identifier, secret)

    @classmethod
    def endpoint(cls, endpoint_name: str, **kwargs) -> str:
        endpoint_template = cls.ENDPOINTS.get(endpoint_name)
        if endpoint_template is None:
            raise ValueError(f"Endpoint '{endpoint_name}' not found.")
        return urljoin(cls.BASE_URL, endpoint_template.format(**kwargs))

    @classmethod
    def create_token(cls, identifier: str, secret: str) -> str:
        target = cls.endpoint("auth")
        params = {"identifier": identifier, "secret": secret}

        response = requests.post(target, json=params)
        response.raise_for_status()

        access_token = response.json().get("access_token")
        if access_token is None:
            raise Exception("Failed to obtain access token from Docker Hub")

        return access_token

    def _get_headers(self) -> dict:
        if datetime.now() >= self.token_expiration:
            self.token_expiration = datetime.now() + timedelta(minutes=10)
            self.access_token = self.create_token(self.identifier, self.secret)
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_repositories(self, namespace: str = None) -> list[dict]:
        if namespace is None:
            namespace = self.identifier
        target = self.endpoint("repositories", namespace=namespace)
        params = {"page_size": 100}

        response = requests.get(target, headers=self._get_headers(), params=params)
        response.raise_for_status()
        response_data = response.json()
        results = response_data["results"]
        while response_data.get("next"):
            response = requests.get(response_data["next"], headers=self._get_headers())
            response.raise_for_status()
            response_data = response.json()
            results.extend(response_data["results"])

        return results

    def get_repository(self, namespace: str = None, repository: str = None) -> dict:
        if namespace is None:
            namespace = self.identifier
        if repository is None:
            raise ValueError("Repository name must be provided.")
        target = self.endpoint("repository", namespace=namespace, repository=repository)

        response = requests.get(target, headers=self._get_headers())
        response.raise_for_status()

        return response.json()

    def get_tags(self, namespace: str = None, repository: str = None) -> list[dict]:
        if namespace is None:
            namespace = self.identifier
        if repository is None:
            raise ValueError("Repository name must be provided.")
        target = self.endpoint("tags", namespace=namespace, repository=repository)
        params = {"page_size": 100}

        response = requests.get(target, headers=self._get_headers(), params=params)
        response.raise_for_status()
        response_data = response.json()
        results = response_data["results"]
        while response_data.get("next"):
            response = requests.get(response_data["next"], headers=self._get_headers())
            response.raise_for_status()
            response_data = response.json()
            results.extend(response_data["results"])

        return results

    def get_tag(self, namespace: str = None, repository: str = None, tag: str = None) -> dict:
        if namespace is None:
            namespace = self.identifier
        if repository is None:
            raise ValueError("Repository name must be provided.")
        if tag is None:
            raise ValueError("Tag name must be provided.")
        target = self.endpoint("tag", namespace=namespace, repository=repository, tag=tag)

        response = requests.get(target, headers=self._get_headers())
        response.raise_for_status()

        return response.json()

    def delete_tag(self, namespace: str = None, repository: str = None, tag: str = None) -> None:
        if namespace is None:
            namespace = self.identifier
        if repository is None:
            raise ValueError("Repository name must be provided.")
        if tag is None:
            raise ValueError("Tag name must be provided.")
        target = self.endpoint("tag", namespace=namespace, repository=repository, tag=tag)

        response = requests.delete(target, headers=self._get_headers())
        response.raise_for_status()
