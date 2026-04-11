package com.health.app.controller;

import com.health.app.service.MemoryStore;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Comparator;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/report")
@Validated
public class ReportController {

    private final MemoryStore store;

    public ReportController(MemoryStore store) {
        this.store = store;
    }

    @GetMapping("/daily")
    public Map<String, Object> daily(@RequestParam("userId") @NotBlank String userId) {
        List<Map<String, Object>> sport = store.getListByUser(store.sportRecords(), userId);
        List<Map<String, Object>> diet = store.getListByUser(store.dietRecords(), userId);
        Map<String, Object> sleep = store.getListByUser(store.sleepRecords(), userId).stream()
                .max(Comparator.comparing(x -> String.valueOf(x.getOrDefault("date", ""))))
                .orElse(Map.of());

        double burned = sport.stream().mapToDouble(x -> parseDouble(x.get("caloriesBurned"))).sum();
        double intake = diet.stream().mapToDouble(x -> parseDouble(x.get("calories"))).sum();

        return Map.of(
                "success", true,
                "data", Map.of(
                        "sportCaloriesBurned", burned,
                        "dietCaloriesIntake", intake,
                        "calorieGap", burned - intake,
                        "lastSleep", sleep,
                        "suggestion", burned - intake > 0 ? "Good deficit. Keep balanced nutrition." : "Control dinner calories and increase light exercise."
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
