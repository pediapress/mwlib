#! /usr/bin/env python

"""Workflow helpers for fetch orchestration."""


def collect_page_data(pages, title2latest):
    revids = set()
    images = set()
    templates = set()

    for page in pages:
        revisions = page.get("revisions", [])
        revision_ids = [revision.get("revid") for revision in revisions if revision.get("revid")]
        revids.update(revision_ids)
        if revision_ids:
            latest = max(revision_ids)
            title = page.get("title")
            title2latest[title] = max(title2latest.get(title, 0), latest)

        images.update(entry.get("title") for entry in page.get("images", []) if entry.get("title"))
        templates.update(
            entry.get("title") for entry in page.get("templates", []) if entry.get("title")
        )

    return revids, images, templates


def enqueue_missing(items, todo_list, scheduled):
    for item in items:
        if item in scheduled:
            continue
        todo_list.append(item)
        scheduled.add(item)
