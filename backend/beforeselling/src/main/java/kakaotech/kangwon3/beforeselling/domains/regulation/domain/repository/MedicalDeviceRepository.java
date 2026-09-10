package kakaotech.kangwon3.beforeselling.domains.regulation.domain.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity.MedicalDevice;

public interface MedicalDeviceRepository extends JpaRepository<MedicalDevice, Long> {
}
