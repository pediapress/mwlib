from mwlib.core import metabook as metabook_module
from mwlib.core import wiki
from mwlib.utils.status import Status


def create_zip_from_wiki_env(
    env,
    pod_client,
    wiki_options,
    make_zip,
):
    if not env.metabook:
        raise ValueError("no metabook")
    status_file = wiki_options.get("status_file")
    status = Status(
        status_file, podclient=pod_client, progress_range=(1, 90)
    )
    status(progress=0)
    make_zip(
        metabook=env.metabook,
        wiki_options=wiki_options,
        pod_client=pod_client,
        status=status,
    )
    return status



def make_wiki_env_from_options(
    metabook,
    wiki_options,
):
    wiki_options_with_metabook = wiki_options.copy()
    wiki_options_with_metabook["metabook"] = metabook
    env = wiki.make_wiki(
        **wiki_options_with_metabook,
    )
    if not env.metabook:
        env.metabook = metabook_module.Collection()
        env.init_metabook()

    noimages = wiki_options.get("noimages")
    if noimages:
        env.images = None

    title = wiki_options.get("title")
    subtitle = wiki_options.get("subtitle")
    editor = wiki_options.get("editor")

    if title:
        env.metabook.title = title
    if subtitle:
        env.metabook.subtitle = subtitle
    if editor:
        env.metabook.editor = editor
    # add default licenses

    config = wiki_options.get("config")
    cfg = config or ""
    if cfg.startswith(":") and not env.metabook.licenses:
        mw_license_url = wiki.wpwikis.get(cfg[1:])["mw_license_url"]
        env.metabook.licenses.append(
            {"mw_license_url": mw_license_url, "type": "License"}
        )
    return env
