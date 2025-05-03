
import logging
import sys

# --- Add NullHandler for library use ---
# Get the root logger for the 'mwlib' namespace package.
_mwlib_root_logger = logging.getLogger('mwlib')

# Check if a NullHandler (or any handler) has already been added.
# This prevents adding it multiple times if this module is imported
# repeatedly or via different paths. Aim is idempotent setup.
if not _mwlib_root_logger.hasHandlers():
    _mwlib_root_logger.addHandler(logging.NullHandler())
    # You could add a debug log here, but it requires the level
    # to be set *before* this runs, which is unlikely.
    # print("DEBUG: NullHandler added to 'mwlib' logger.", file=sys.stderr) # Temporary debug

CONSOLE_LOG_FORMAT = '%(levelname)s: %(message)s'
_logging_configured_by_tool = False

DEFAULT_SILENCED_LOGGERS = {
    'urllib3': logging.WARNING,
    'PIL.Image': logging.WARNING, # Pillow uses 'PIL.Image' or just 'PIL'
    'PIL': logging.WARNING,
}

def setup_console_logging(
    level=logging.WARNING,
    stream=sys.stderr,
    log_format=CONSOLE_LOG_FORMAT,
    silence_loggers=None
):
    """
    Configures logging for mwlib command-line tools.

    Sets up a StreamHandler for the 'mwlib' package logger and optionally
    sets the level of noisy third-party loggers to a higher threshold.

    Args:
        level: The minimum logging level for the 'mwlib' logger.
        stream: The output stream (default: sys.stderr).
        log_format: The format string for log messages.
        silence_loggers (dict): A dictionary mapping logger names (str) to
            their desired minimum level (int). Defaults to silencing
            common noisy libraries like urllib3 and PIL to WARNING.
            Set to None or {} to disable silencing.
    """
    silence_loggers = silence_loggers or DEFAULT_SILENCED_LOGGERS
    global _logging_configured_by_tool
    if _logging_configured_by_tool:
        _mwlib_root_logger.debug("Console logging already configured by tool. Skipping setup.")
        return

    package_logger = _mwlib_root_logger  # Use the same root logger

    # --- Configure mwlib console handler ---
    if isinstance(level, str):
        level = logging.getLevelName(level.upper())
        if not isinstance(level, int):
            level = logging.WARNING
            package_logger.warning(
                "Invalid mwlib log level string provided. Defaulting to WARNING."
            )

    # Set level on the root logger *for tool operation*
    # This might override a level set by a consuming application
    # if the tool is run after library usage in the same process.
    package_logger.setLevel(level)

    # Remove NullHandler if it exists, before adding console handler
    # (avoids logging to nowhere if level allows it)
    for handler in package_logger.handlers[:]:  # Iterate over a copy
        if isinstance(handler, logging.NullHandler):
            package_logger.removeHandler(handler)

    # Create and add console handler if not already present
    formatter = logging.Formatter(log_format)
    # Check if a similar stream handler already exists
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and h.stream == stream
        for h in package_logger.handlers
    )

    if not has_stream_handler:
        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel(level)  # Important: Set level on handler too
        console_handler.setFormatter(formatter)
        package_logger.addHandler(console_handler)

    # Prevent propagation IF the root Python logger has handlers,
    # otherwise allow it so basicConfig might catch it.
    # Generally safer to control propagation explicitly.
    # If mwlib tools are the main entry point, preventing propagation
    # avoids potential duplicate messages if user also configures root.
    package_logger.propagate = False

    # --- Silence other loggers ---
    if silence_loggers:
        for logger_name, silenced_level in silence_loggers.items():
            try:
                logger_to_silence = logging.getLogger(logger_name)
                effective_silence_level = max(silenced_level, level)
                current_level = logger_to_silence.getEffectiveLevel()
                if current_level < effective_silence_level or current_level == logging.NOTSET:
                    # print(f"DEBUG: Silencing {logger_name} to {logging.getLevelName(effective_silence_level)}", file=sys.stderr)
                    logger_to_silence.setLevel(effective_silence_level)
            except Exception as e:
                package_logger.warning(
                    f"Could not configure level for logger '{logger_name}': {e}"
                )

    _logging_configured_by_tool = True
    package_logger.debug(
        f"mwlib console logging configured by tool to level {logging.getLevelName(level)}."
    )
    if silence_loggers:
         package_logger.debug(f"Attempted to silence loggers: {list(silence_loggers.keys())}")
