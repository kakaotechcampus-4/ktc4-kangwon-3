package kakaotech.kangwon3.beforeselling;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class BeforesellingApplication {

	public static void main(String[] args) {
		SpringApplication.run(BeforesellingApplication.class, args);
	}

}
