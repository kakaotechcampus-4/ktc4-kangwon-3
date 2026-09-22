package kakaotech.kangwon3.beforeselling.verify;

import jakarta.persistence.EntityManager;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ApiVerificationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DiagnosesService diagnosesService;

    // H2에서 s3_files 테이블 생성이 실패하므로(컬럼명 key가 H2 예약어) 이 검증에서는 목으로 대체한다.
    @MockitoBean
    private S3FileService s3FileService;

    @Autowired
    private EntityManager entityManager;

    private static final Long USER = 1L;
    private static final Long OTHER = 2L;

    @Test
    @DisplayName("전체 API 검증")
    void verifyAll() throws Exception {
        section("1. POST /api/v1/diagnoses  — 상품 2개로 진단서 생성");
        String createBody = """
                {"products":[
                  {"productName":"대나무 헬리콥터","productImageKey":"product-main/1/uuid_a.jpg",
                   "sourceType":"URL","sourceUrl":"https://ko.aliexpress.com/item/100500628491"},
                  {"productName":"타임머신","productImageKey":"product-main/1/uuid_b.jpg",
                   "sourceType":"TEXT_IMAGE","sourceText":"상세페이지 본문",
                   "imageKeys":["product-detail/1/uuid_b1.jpg","product-detail/1/uuid_b2.jpg"]}
                ]}""";
        String res = call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(createBody), USER, createBody);
        Long id = extractId(res);

        section("2. GET /api/v1/diagnoses/{id}  — 단건 조회");
        call(get("/api/v1/diagnoses/" + id), USER, null);

        section("3. GET /api/v1/diagnoses  — 목록 조회 (기본)");
        call(get("/api/v1/diagnoses"), USER, null);

        section("4. GET /api/v1/diagnoses/{id}  — 남의 진단서 조회");
        call(get("/api/v1/diagnoses/" + id), OTHER, null);

        section("5. GET /api/v1/diagnoses/999999  — 없는 진단서");
        call(get("/api/v1/diagnoses/999999"), USER, null);

        section("6. GET /api/v1/diagnoses/{id}  — 비인증");
        callNoAuth(get("/api/v1/diagnoses/" + id));

        section("7. POST /api/v1/diagnoses  — 상품 배열이 비어 있음");
        String empty = "{\"products\":[]}";
        call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(empty), USER, empty);

        section("8. POST /api/v1/diagnoses  — URL 타입인데 sourceUrl 없음 (중첩 @Valid 동작 확인)");
        String badNested = "{\"products\":[{\"productName\":\"타임머신\",\"sourceType\":\"URL\"}]}";
        call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(badNested), USER, badNested);

        section("9. POST /api/v1/diagnoses  — 상품명 누락 (중첩 @NotBlank 동작 확인)");
        String noName = "{\"products\":[{\"sourceType\":\"URL\",\"sourceUrl\":\"https://a.com\"}]}";
        call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(noName), USER, noName);

        section("10. GET /api/v1/diagnoses?resultStatus=RECHECK_REQUIRED  — 결과 필터");
        call(get("/api/v1/diagnoses").param("resultStatus", "RECHECK_REQUIRED"), USER, null);

        section("11. GET /api/v1/diagnoses?page=-1  — 잘못된 페이징");
        call(get("/api/v1/diagnoses").param("page", "-1"), USER, null);

        section("12. DELETE /api/v1/diagnoses/{id}  — 남의 진단서 삭제 시도");
        call(delete("/api/v1/diagnoses/" + id), OTHER, null);

        section("13. DB 상태 — 삭제 전");
        printCounts();

        section("14. DELETE /api/v1/diagnoses/{id}  — 본인 진단서 삭제");
        call(delete("/api/v1/diagnoses/" + id), USER, null);

        section("15. DB 상태 — 삭제 후 (2단 cascade 확인)");
        printCounts();

        section("16. 회원 탈퇴 시 전체 삭제 (removeAllByUserId)");
        String c2 = """
                {"products":[{"productName":"어디로든 문","productImageKey":"product-main/1/uuid_c.jpg",
                 "sourceType":"TEXT_IMAGE","sourceText":"본문","imageKeys":["product-detail/1/uuid_c1.jpg"]}]}""";
        call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(c2), USER, c2);
        System.out.println(">> 탈퇴 전:");
        printCounts();
        diagnosesService.removeAllByUserId(USER);
        System.out.println(">> removeAllByUserId(1) 실행 후:");
        printCounts();
    }

    private String call(org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder req,
                        Long userId, String body) throws Exception {
        if (body != null) {
            System.out.println("[요청 본문]\n" + body);
        }
        MvcResult result = mockMvc.perform(req.with(authentication(login(userId)))).andReturn();
        String content = result.getResponse().getContentAsString();
        System.out.println("[응답] HTTP " + result.getResponse().getStatus() + "\n" + content + "\n");
        return content;
    }

    private void callNoAuth(org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder req) throws Exception {
        MvcResult result = mockMvc.perform(req).andReturn();
        System.out.println("[응답] HTTP " + result.getResponse().getStatus() + "\n"
                + result.getResponse().getContentAsString() + "\n");
    }

    @Transactional
    void printCounts() {
        System.out.println("   diagnoses=" + count("Diagnoses")
                + ", product=" + count("Product")
                + ", product_image=" + count("ProductImage")
                );
    }

    private long count(String entity) {
        return entityManager.createQuery("select count(e) from " + entity + " e", Long.class).getSingleResult();
    }

    private Long extractId(String json) {
        int i = json.indexOf("\"diagnosesId\":");
        int end = i;
        while (end < json.length() && json.charAt(end) != '}' && json.charAt(end) != ',') end++;
        return Long.parseLong(json.substring(i + 14, end).trim());
    }

    private void section(String title) {
        System.out.println("\n@@@@@ " + title);
    }

    private Authentication login(Long userId) {
        return UsernamePasswordAuthenticationToken.authenticated(
                new UserPrincipal(userId, Role.USER), null,
                List.of(new SimpleGrantedAuthority(Role.USER.getAuthority())));
    }
}
