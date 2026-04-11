package com.health.app.controller;

import com.health.app.service.AiClientService;
import com.health.app.service.MemoryStore;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/diet")
@Validated
public class DietController {

    private final MemoryStore store;
    private final AiClientService aiClientService;

    public DietController(MemoryStore store, AiClientService aiClientService) {
        this.store = store;
        this.aiClientService = aiClientService;
    }

    @PostMapping("/record")
    public Map<String, Object> record(@RequestBody Map<String, Object> body) {
        String userId = String.valueOf(body.getOrDefault("userId", "demo-user"));
        body.putIfAbsent("mealTime", LocalDateTime.now().toString());
        store.getListByUser(store.dietRecords(), userId).add(body);
        return Map.of("success", true, "data", body);
    }

    @GetMapping("/history")
    public Map<String, Object> history(@RequestParam("userId") @NotBlank String userId) {
        List<Map<String, Object>> records = store.getListByUser(store.dietRecords(), userId).stream()
                .sorted(Comparator.comparing(x -> String.valueOf(x.getOrDefault("mealTime", ""))))
                .toList();

        return Map.of("success", true, "data", records);
    }

    @GetMapping("/recommend")
    public Map<String, Object> recommend(@RequestParam("userId") @NotBlank String userId) {
        Map<String, Object> userProfile = store.userProfiles().getOrDefault(userId, Map.of());
        double todayBurned = store.getListByUser(store.sportRecords(), userId).stream()
                .mapToDouble(x -> parseDouble(x.get("caloriesBurned"))).sum();

        int sleepScore = store.getListByUser(store.sleepRecords(), userId).stream()
                .max(Comparator.comparing(x -> String.valueOf(x.getOrDefault("date", ""))))
                .map(x -> Integer.parseInt(String.valueOf(x.getOrDefault("qualityScore", 60))))
                .orElse(60);

        Map<String, Object> payload = new HashMap<>();
        payload.put("userId", userId);
        payload.put("todayCaloriesBurned", todayBurned);
        payload.put("lastSleepScore", sleepScore);
        payload.put("targetWeight", userProfile.getOrDefault("targetWeight", 60));

        Map<String, Object> aiResult = aiClientService.recommendMeal(payload);

        return Map.of(
                "success", true,
                "data", Map.of(
                        "input", payload,
                        "recommendation", aiResult
                )
        );
    }

    private double parseDouble(Object value) {
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (Exception ex) {
            return 0;
        }
    }
}
