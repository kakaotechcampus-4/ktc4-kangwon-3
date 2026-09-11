package kakaotech.kangwon3.beforeselling.global.exception;

import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler extends ResponseEntityExceptionHandler {

    @ExceptionHandler(BaseException.class)
    public ResponseEntity<ApiResponse<Void>> handleBaseException(BaseException e) {
        log.error("BaseException: ", e);
        BaseResponseCode responseCode = e.getResponseCode();

        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode));
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ApiResponse<Void>> handleDataIntegrityViolationException(DataIntegrityViolationException e) {
        log.error("DataIntegrityViolationException: ", e);
        BaseResponseCode responseCode = CommonResponseCode.DATA_INTEGRITY_VIOLATION;

        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode));
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ApiResponse<Void>> handleAccessDeniedException(AccessDeniedException e) {
        log.error("AccessDeniedException: ", e);
        BaseResponseCode responseCode = CommonResponseCode.FORBIDDEN;

        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleException(Exception e) {
        log.error("Exception: ", e);
        BaseResponseCode responseCode = CommonResponseCode.INTERNAL_SERVER_ERROR;

        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode));
    }

    @Override
    protected ResponseEntity<Object> handleNoResourceFoundException(NoResourceFoundException e, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        BaseResponseCode responseCode = CommonResponseCode.NOT_FOUND;
        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode));
    }

    @Override
    protected ResponseEntity<Object> handleHttpRequestMethodNotSupported(HttpRequestMethodNotSupportedException e, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        log.error("HttpRequestMethodNotSupportedException: ", e);
        BaseResponseCode responseCode = CommonResponseCode.METHOD_NOT_ALLOWED;
        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode));
    }

    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException e, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        log.error("MethodArgumentNotValidException: ", e);
        BaseResponseCode responseCode = CommonResponseCode.INVALID_METHOD_ARGUMENT;
        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode, e.getBindingResult().getFieldErrors()));
    }

    @Override
    protected ResponseEntity<Object> handleHttpMessageNotReadable(HttpMessageNotReadableException e, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        log.error("JSON Parse Error: ", e);
        BaseResponseCode responseCode = CommonResponseCode.BAD_REQUEST;
        return ResponseEntity
                .status(responseCode.getStatus())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiResponse.ofFail(responseCode));
    }
}
