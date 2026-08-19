from typing import ClassVar


class TravelBackendError(Exception):
    """A domain error whose string representation is safe for API clients."""

    code: ClassVar[str] = "INTERNAL_ERROR"
    public_message: ClassVar[str] = "요청을 처리하지 못했습니다."
    status_code: ClassVar[int] = 500

    def __init__(self) -> None:
        super().__init__(self.public_message)


class KakaoNotConfiguredError(TravelBackendError):
    code = "KAKAO_NOT_CONFIGURED"
    public_message = "Kakao Local API가 설정되지 않았습니다."
    status_code = 503


class KakaoUpstreamError(TravelBackendError):
    code = "KAKAO_UPSTREAM_ERROR"
    public_message = "장소 정보를 가져오지 못했습니다."
    status_code = 502


class UpstreamTimeoutError(TravelBackendError):
    code = "UPSTREAM_TIMEOUT"
    public_message = "외부 서비스 응답 시간이 초과되었습니다."
    status_code = 504


class InvalidKakaoResponseError(KakaoUpstreamError):
    public_message = "장소 서비스 응답을 처리하지 못했습니다."
