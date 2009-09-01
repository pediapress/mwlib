import os

def getenv_bool(name, default=False):
    val = os.environ.get(name, None)
    if val is None:
        return default
    val = val.lower()
    if val in ("yes", "true"):
        return True
    if val in ("no", "false"):
        return False
    
    try:
        val = int(val)
    except ValueError:
        pass
    
    return bool(val)

noedits = getenv_bool("NOEDITS")
