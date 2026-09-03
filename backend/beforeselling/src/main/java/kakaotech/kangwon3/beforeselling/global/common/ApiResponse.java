package kakaotech.kangwon3.beforeselling.global.common;

import lombok.AccessLevel;
import lombok.Builder;
import org.springframework.validation.FieldError;

import java.util.List;
import java.util.stream.Collectors;

@Builder(access = AccessLevel.PRIVATE)
public record ApiResponse<T>(
        String code,
        String message,
        List<FieldErrorDetail> details,
        T data
) {

    public static <T> ApiResponse<T> ofSuccess(final BaseResponseCode responseCode) {
        return ApiResponse.<T>builder()
                .code(responseCode.getCode())
                .message(responseCode.getMessage())
                .build();
    }

    public static <T> ApiResponse<T> ofSuccess(final BaseResponseCode responseCode, T data) {
        return ApiResponse.<T>builder()
                .code(responseCode.getCode())
                .message(responseCode.getMessage())
                .data(data)
                .build();
    }

    public static <T> ApiResponse<T> ofFail(final BaseResponseCode responseCode) {
        return ApiResponse.<T>builder()
                .code(responseCode.getCode())
                .message(responseCode.getMessage())
                .build();
    }

    public static <T> ApiResponse<T> ofFail(final BaseResponseCode responseCode, final List<FieldError> fieldErrors) {
        return ApiResponse.<T>builder()
                .code(responseCode.getCode())
                .message(responseCode.getMessage())
                .details(FieldErrorDetail.of(fieldErrors))
                .build();
    }

    private record FieldErrorDetail(
            String field,
            String message
    ) {

        private static FieldErrorDetail of(final FieldError fieldError) {
            return new FieldErrorDetail(fieldError.getField(), fieldError.getDefaultMessage());
        }

        private static List<FieldErrorDetail> of(final List<FieldError> fieldErrors) {
            return fieldErrors.stream()
                    .map(FieldErrorDetail::of)
                    .collect(Collectors.toList());
        }
    }
}
