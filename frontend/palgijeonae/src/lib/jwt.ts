function base64UrlDecode(segment: string): string {
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const binary = atob(padded);

    return decodeURIComponent(
        Array.from(binary)
            .map((char) => "%" + char.charCodeAt(0).toString(16).padStart(2, "0"))
            .join(""),
    );
}

// 서명 검증 없이 payload만 디코딩한다 (Sentry 유저 식별용으로만 사용)
export function getUserIdFromAccessToken(accessToken: string): string | null {
    try {
        const payload = JSON.parse(base64UrlDecode(accessToken.split(".")[1]));
        return payload.sub == null ? null : String(payload.sub);
    } catch {
        return null;
    }
}
