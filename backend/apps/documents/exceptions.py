from rest_framework import status
from rest_framework.exceptions import APIException


class PayloadTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "Файл больше допустимого размера."
    default_code = "payload_too_large"


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Заявку в этом статусе изменить нельзя."
    default_code = "invalid_transition"
