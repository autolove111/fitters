package com.health.app.controller;

import com.health.app.service.MemoryStore;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/sport")
@Validated
public class SportController {

    private final MemoryStore store;

    public SportController(MemoryStore store) {
        this.store = store;
    }

    @PostMapping("/record")
    public Map<String, Object> record(@RequestBody Map<String, Object> body) {
        String userId = String.valueOf(body.getOrDefault("userId", "demo-user"));
        body.putIfAbsent("date", LocalDate.now().toString());
        store.getListByUser(store.sportRecords(), userId).add(body);
        return Map.of("success", true, "data", body);
    }

    @GetMapping("/today")
    public Map<String, Object> today(@RequestParam("userId") @NotBlank String userId) {
        String today = LocalDate.now().toString();
        List<Map<String, Object>> all = store.getListByUser(store.sportRecords(), userId);
        List<Map<String, Object>> records = all.stream()
                .filter(x -> today.equals(String.valueOf(x.get("date"))))
                .toList();

        double totalCalories = records.stream()
                .mapToDouble(x -> parseDouble(x.get("caloriesBurned")))
                .sum();

        return Map.of(
                "success", true,
                "data", Map.of(
                        "records", records,
                        "totalCaloriesBurned", totalCalories
                )
        );
    }

    @GetMapping("/summary7d")
    public Map<String, Object> summary7d(@RequestParam("userId") @NotBlank String userId) {
        LocalDate boundary = LocalDate.now().minusDays(6);
        List<Map<String, Object>> all = store.getListByUser(store.sportRecords(), userId);

        List<Map<String, Object>> records = all.stream().filter(x -> {
            try {
                LocalDate date = LocalDate.parse(String.valueOf(x.get("date")));
                return !date.isBefore(boundary);
            } catch (Exception ex) {
                return false;
            }
        }).toList();

        double totalCalories = records.stream().mapToDouble(x -> parseDouble(x.get("caloriesBurned"))).sum();

        return Map.of(
                "success", true,
                "data", Map.of(
                        "count", records.size(),
                        "totalCaloriesBurned", totalCalories,
                        "records", records
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
