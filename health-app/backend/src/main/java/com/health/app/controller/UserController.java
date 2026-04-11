package com.health.app.controller;

import com.health.app.service.MemoryStore;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/user")
@Validated
public class UserController {

    private final MemoryStore store;

    public UserController(MemoryStore store) {
        this.store = store;
    }

    @PostMapping("/register")
    public Map<String, Object> register(@RequestBody Map<String, Object> body) {
        String userId = String.valueOf(body.getOrDefault("userId", UUID.randomUUID().toString()));
        Map<String, Object> profile = new HashMap<>(body);
        profile.put("userId", userId);
        store.userProfiles().put(userId, profile);

        return Map.of(
                "success", true,
                "message", "user registered",
                "data", profile
        );
    }

    @GetMapping("/profile")
    public Map<String, Object> profile(@RequestParam("userId") @NotBlank String userId) {
        Map<String, Object> profile = store.userProfiles().get(userId);
        if (profile == null) {
            return Map.of(
                    "success", false,
                    "message", "user not found",
                    "data", Map.of()
            );
        }
        return Map.of("success", true, "data", profile);
    }
}
