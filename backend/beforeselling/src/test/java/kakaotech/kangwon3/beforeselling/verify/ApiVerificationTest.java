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

        section("17. === 상품 API (마이페이지) ===");
        String multi = """
                {"products":[
                  {"productName":"대나무 헬리콥터","productImageKey":"product-main/1/uuid_a.jpg",
                   "sourceType":"URL","sourceUrl":"https://ko.aliexpress.com/item/1"},
                  {"productName":"타임머신","productImageKey":"product-main/1/uuid_b.jpg",
                   "sourceType":"TEXT_IMAGE","sourceText":"본문","imageKeys":["product-detail/1/uuid_b1.jpg"]},
                  {"productName":"어디로든 문","productImageKey":"product-main/1/uuid_c.jpg",
                   "sourceType":"URL","sourceUrl":"https://ko.aliexpress.com/item/3"}
                ]}""";
        call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(multi), USER, multi);
        // 두 번째 진단서 — 여러 진단서의 상품이 한 목록으로 합쳐지는지 확인
        String second = """
                {"products":[{"productName":"타케콥터 대나무","productImageKey":"product-main/1/uuid_d.jpg",
                 "sourceType":"URL","sourceUrl":"https://ko.aliexpress.com/item/4"}]}""";
        call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(second), USER, second);
        // 남의 상품
        String others = """
                {"products":[{"productName":"남의 상품","productImageKey":"product-main/2/uuid_x.jpg",
                 "sourceType":"URL","sourceUrl":"https://ko.aliexpress.com/item/9"}]}""";
        call(post("/api/v1/diagnoses").contentType(MediaType.APPLICATION_JSON).content(others), OTHER, others);

        section("18. GET /api/v1/products  — 마이페이지 목록 (진단서 2개의 상품이 합쳐짐)");
        String listRes = call(get("/api/v1/products"), USER, null);
        Long productId = extractProductId(listRes);

        section("19. GET /api/v1/products?keyword=대나무  — 상품명 검색");
        call(get("/api/v1/products").param("keyword", "대나무"), USER, null);

        section("20. GET /api/v1/products?keyword=  — 빈 검색어는 전체 조회");
        call(get("/api/v1/products").param("keyword", ""), USER, null);

        section("21. GET /api/v1/products?resultStatus=RECHECK_REQUIRED  — 결과 필터");
        call(get("/api/v1/products").param("resultStatus", "RECHECK_REQUIRED"), USER, null);

        section("22. GET /api/v1/products?page=-1  — 잘못된 페이징 (ProductApi 검증)");
        call(get("/api/v1/products").param("page", "-1"), USER, null);

        section("23. GET /api/v1/products  — 남의 상품은 제외되는지 (user=2)");
        call(get("/api/v1/products"), OTHER, null);

        section("24. DELETE /api/v1/products/{id}  — 남의 상품 삭제 시도");
        call(delete("/api/v1/products/" + productId), OTHER, null);

        section("25. DB 상태 — 상품 삭제 전 (진단서 3 / 상품 5 / 이미지 1)");
        printCounts();

        section("26. DELETE — 상품이 1개뿐인 진단서의 상품 삭제 → 빈 진단서도 함께 삭제된다");
        call(delete("/api/v1/products/" + productId), USER, null);
        printCounts();

        section("27. DELETE — 상품이 여러 개인 진단서에서 1개만 삭제 → 진단서는 유지된다");
        String remainingRes = call(get("/api/v1/products"), USER, null);
        List<Long> remainingIds = extractProductIdsOfDiagnoses(remainingRes);
        call(delete("/api/v1/products/" + remainingIds.getFirst()), USER, null);
        printCounts();

        section("28. DELETE — 남은 상품을 모두 삭제 → 진단서도 사라지고 남의 데이터만 남는다");
        for (Long remaining : remainingIds.subList(1, remainingIds.size())) {
            call(delete("/api/v1/products/" + remaining), USER, null);
        }
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

    private Long extractProductId(String json) {
        int i = json.indexOf("\"productId\":");
        int end = i + 12;
        while (end < json.length() && Character.isDigit(json.charAt(end))) end++;
        return Long.parseLong(json.substring(i + 12, end));
    }

    // 목록 응답에서 productId를 모두 뽑는다.
    private java.util.List<Long> extractProductIdsOfDiagnoses(String json) {
        java.util.List<Long> ids = new java.util.ArrayList<>();
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\"productId\":(\\d+)").matcher(json);
        while (m.find()) ids.add(Long.parseLong(m.group(1)));
        return ids;
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
