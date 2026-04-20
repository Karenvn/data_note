from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AuthorPerson:
    given_names: str
    surname: str
    email: str | None = None
    orcid: str | None = None
    affiliation: str | None = None
    roles: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AuthorPerson":
        return cls(
            given_names=str(data.get("given-names", "")),
            surname=str(data.get("surname", "")),
            email=data.get("email"),
            orcid=data.get("orcid"),
            affiliation=data.get("affiliation"),
            roles=[dict(item) for item in data.get("roles", [])],
        )

    def to_mapping(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "given-names": self.given_names,
            "surname": self.surname,
            "roles": [dict(item) for item in self.roles],
        }
        if self.email is not None:
            data["email"] = self.email
        if self.orcid:
            data["orcid"] = self.orcid
        if self.affiliation is not None:
            data["affiliation"] = self.affiliation
        return data


@dataclass(slots=True)
class AuthorAffiliation:
    id: str
    organization: str
    city: str | None = None
    state: str | None = None
    country: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "AuthorAffiliation":
        return cls(
            id=str(data.get("id", "")),
            organization=str(data.get("organization", "")),
            city=data.get("city"),
            state=data.get("state"),
            country=data.get("country"),
        )

    def to_mapping(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "organization": self.organization,
        }
        if self.city is not None:
            data["city"] = self.city
        if self.state is not None:
            data["state"] = self.state
        if self.country is not None:
            data["country"] = self.country
        return data


@dataclass(slots=True)
class AuthorInfo:
    people: list[AuthorPerson] = field(default_factory=list)
    affiliations: list[AuthorAffiliation] = field(default_factory=list)
    yaml_block: str = ""

    @classmethod
    def from_legacy_parts(
        cls,
        *,
        people: list[dict[str, Any]] | None = None,
        affiliations: list[dict[str, Any]] | None = None,
        yaml_block: str = "",
    ) -> "AuthorInfo":
        return cls(
            people=[AuthorPerson.from_mapping(item) for item in (people or [])],
            affiliations=[AuthorAffiliation.from_mapping(item) for item in (affiliations or [])],
            yaml_block=yaml_block,
        )

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "author_people": [person.to_mapping() for person in self.people],
            "author_affiliations": [affiliation.to_mapping() for affiliation in self.affiliations],
            "author_yaml_block": self.yaml_block,
        }
