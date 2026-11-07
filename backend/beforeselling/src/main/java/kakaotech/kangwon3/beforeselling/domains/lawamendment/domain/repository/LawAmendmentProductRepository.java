package kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.repository;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.UUID;

public interface LawAmendmentProductRepository extends JpaRepository<LawAmendmentProduct, UUID> {

    // 사용자의 재확인 대상 상품. 최근 법령 변경부터, 같은 변경 안에서는 최근 상품부터 가져온다.
    @Query("""
            select lap from LawAmendmentProduct lap
            join fetch lap.lawAmendment la
            join fetch lap.product p
            where p.diagnoses.userId = :userId
            order by la.createdAt desc, p.createdAt desc
            """)
    List<LawAmendmentProduct> findWithLawAmendmentAndProductByUserId(@Param("userId") UUID userId);

    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("delete from LawAmendmentProduct lap where lap.product.id = :productId")
    int deleteByProductId(@Param("productId") UUID productId);
}
