"""Albertos customer/reference-implementation content.

This subpackage — public website pages, templates, static assets, and the
embedded chat widget front-end (club pages, trainers, schedule, sections,
history, news, contact) — is specific to Albertos, the first Shiruno
customer. It is not part of the reusable Shiruno Platform: unlike
``api/``, ``application/``, ``domain/``, ``infra/``, ``persistence/``, and
``providers/``, nothing outside this subpackage depends on it, and it
depends on nothing from the platform beyond the public ``/api/v1/chat``
contract. See ``docs/architecture.md`` for the full product/customer
boundary and why this stays physically nested here rather than under a
separate top-level tree (specs/008-shiruno-repository-architecture/
research.md §2).
"""
