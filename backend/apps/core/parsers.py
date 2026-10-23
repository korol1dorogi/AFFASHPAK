from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser as DrfJSONParser

TOO_DEEP = "Слишком глубокая вложенность JSON."


class JSONParser(DrfJSONParser):
    """DRF's parser, plus a 400 for nesting so deep that Python's json hits the recursion limit.

    DRF turns ValueError into 400 but lets RecursionError through as a 500 (red team, S8).
    """

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError as exc:
            raise ParseError(TOO_DEEP) from exc
