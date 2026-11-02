package kakaotech.kangwon3.beforeselling.global.ratelimit;

public record RateLimitResult(
        boolean allowed,
        long retryAfterSeconds
) {

    public static RateLimitResult allow() {
        return new RateLimitResult(true, 0);
    }

    public static RateLimitResult reject(long retryAfterSeconds) {
        return new RateLimitResult(false, retryAfterSeconds);
    }
}
