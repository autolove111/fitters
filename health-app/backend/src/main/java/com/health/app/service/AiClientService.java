package com.health.app.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@Service
public class AiClientService {

    private final RestTemplate restTemplate = new RestTemplate();

    @Value("${app.ai-service.base-url:http://localhost:5000}")
    private String aiBaseUrl;

    @SuppressWarnings("unchecked")
    public Map<String, Object> recommendMeal(Map<String, Object> payload) {
        String url = aiBaseUrl + "/v1/recommend/meal";
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload, headers);

        try {
            Object result = restTemplate.postForObject(url, request, Map.class);
            if (result instanceof Map<?, ?> map) {
                return (Map<String, Object>) map;
            }
        } catch (Exception ex) {
            Map<String, Object> fallback = new HashMap<>();
            fallback.put("source", "fallback");
            fallback.put("reason", ex.getMessage());
            fallback.put("meal", "grilled chicken salad");
            fallback.put("estimatedCalories", 420);
            fallback.put("advice", "AI service unavailable. Using local fallback suggestion.");
            return fallback;
        }

        Map<String, Object> fallback = new HashMap<>();
        fallback.put("source", "fallback");
        fallback.put("meal", "boiled egg and vegetables");
        fallback.put("estimatedCalories", 350);
        fallback.put("advice", "No valid response from AI service.");
        return fallback;
    }
}
