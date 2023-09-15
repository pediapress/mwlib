class InvalidArticleStructureError(Exception):
    pass


class ImageDbError(Exception):
    pass


class WikiIdValidationError(Exception):
    pass


class InvalidTreeNodesError(Exception):
    pass


class SanityException(Exception):
    pass


class InconsistentPathLengthException(Exception):
    def __init__(self, expected_length, actual_length):
        super().__init__(
            f"Expected path length of {expected_length}, but got {actual_length}."
        )


class RenderException(Exception):
    pass
