package kakaotech.kangwon3.beforeselling.global.config;

import com.fasterxml.jackson.annotation.JsonProperty;
import org.hibernate.validator.HibernateValidatorConfiguration;
import org.hibernate.validator.spi.nodenameprovider.JavaBeanProperty;
import org.hibernate.validator.spi.nodenameprovider.Property;
import org.springframework.boot.validation.autoconfigure.ValidationConfigurationCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.ReflectionUtils;

import java.lang.reflect.Field;

@Configuration
public class ValidationConfig {

    // 검증 실패 응답(details[].field)에 Java 필드명 대신 요청에 쓰인 JSON 키(@JsonProperty)가 나오게 한다.
    @Bean
    public ValidationConfigurationCustomizer jsonPropertyNodeNameCustomizer() {
        return configuration -> {
            if (configuration instanceof HibernateValidatorConfiguration hibernateConfiguration) {
                hibernateConfiguration.propertyNodeNameProvider(ValidationConfig::resolveJsonName);
            }
        };
    }

    private static String resolveJsonName(Property property) {
        if (property instanceof JavaBeanProperty beanProperty) {
            Field field = ReflectionUtils.findField(beanProperty.getDeclaringClass(), property.getName());
            JsonProperty jsonProperty = field == null ? null : field.getAnnotation(JsonProperty.class);
            if (jsonProperty != null && !jsonProperty.value().isEmpty()) {
                return jsonProperty.value();
            }
        }
        return property.getName();
    }
}
