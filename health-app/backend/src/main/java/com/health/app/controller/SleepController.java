package com.health.app.controller;

import com.health.app.service.MemoryStore;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/sleep")
@Validated
public class SleepController {

    private final MemoryStore store;

    public SleepController(MemoryStore store) {
        this.store = store;
    }

    @PostMapping("/record")
    public Map<String, Object> record(@RequestBody Map<String, Object> body) {
        String userId = String.valueOf(body.getOrDefault("userId", "demo-user"));
        body.putIfAbsent("date", LocalDate.now().minusDays(1).toString());
        body.put("qualityScore", calculateScore(body));
        store.getListByUser(store.sleepRecords(), userId).add(body);
        return Map.of("success", true, "data", body);
    }

    @GetMapping("/last")
    public Map<String, Object> last(@RequestParam("userId") @NotBlank String userId) {
        List<Map<String, Object>> records = store.getListByUser(store.sleepRecords(), userId);
        return records.stream()
                .max(Comparator.comparing(x -> String.valueOf(x.getOrDefault("date", ""))))
                .map(x -> Map.of("success", true, "data", x))
                .orElseGet(() -> Map.of("success", false, "message", "no sleep data", "data", Map.of()));
    }

    private int calculateScore(Map<String, Object> body) {
        double hours = parseDouble(body.get("hours"));
        double deepSleepRatio = parseDouble(body.get("deepSleepRatio"));

        int hourScore = (int) Math.min(60, Math.max(0, (hours / 8.0) * 60));
        int deepScore = (int) Math.min(40, Math.max(0, deepSleepRatio * 40));
        return hourScore + deepScore;
    }

    private double parseDouble(Object value) {
        try {
            return Double.parseDouble(String.valueOf(value));
        } catch (Exception ex) {
            return 0;
        }
    }
}
