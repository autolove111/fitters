package com.healthapp.backend.controller;

import com.healthapp.backend.model.WorkoutRecord;
import com.healthapp.backend.repository.WorkoutRepository;
import com.healthapp.backend.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@CrossOrigin(origins = "*")
@RequestMapping("/api")
public class WorkoutController {

    private final WorkoutRepository workoutRepository;
    private final AuthService authService;

    public WorkoutController(WorkoutRepository workoutRepository, AuthService authService) {
        this.workoutRepository = workoutRepository;
        this.authService = authService;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok", "service", "backend");
    }

    @GetMapping("/workouts")
    public ResponseEntity<?> list(@RequestHeader(value = "Authorization", required = false) String authorization) {
        var userOptional = authService.findUserByToken(extractToken(authorization));
        if (userOptional.isEmpty()) {
            return ResponseEntity.status(401).body(Map.of("message", "未登录或 token 无效"));
        }
        List<WorkoutRecord> result = workoutRepository.findByUserOrderByIdAsc(userOptional.get());
        return ResponseEntity.ok(result);
    }

    @PostMapping("/workouts")
    public ResponseEntity<?> create(@RequestHeader(value = "Authorization", required = false) String authorization,
                                    @Valid @RequestBody WorkoutRecord input) {
        var userOptional = authService.findUserByToken(extractToken(authorization));
        if (userOptional.isEmpty()) {
            return ResponseEntity.status(401).body(Map.of("message", "未登录或 token 无效"));
        }
        input.setId(null);
        input.setUser(userOptional.get());
        WorkoutRecord saved = workoutRepository.save(input);
        return ResponseEntity.ok(saved);
    }

    @DeleteMapping("/workouts/{id}")
    public ResponseEntity<?> delete(@RequestHeader(value = "Authorization", required = false) String authorization,
                                    @PathVariable Long id) {
        var userOptional = authService.findUserByToken(extractToken(authorization));
        if (userOptional.isEmpty()) {
            return ResponseEntity.status(401).body(Map.of("message", "未登录或 token 无效"));
        }

        var recordOptional = workoutRepository.findById(id);
        if (recordOptional.isEmpty()) {
            return ResponseEntity.notFound().build();
        }
        if (!recordOptional.get().getUser().getId().equals(userOptional.get().getId())) {
            return ResponseEntity.status(403).body(Map.of("message", "无权删除该记录"));
        }

        workoutRepository.deleteById(id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/summary")
    public ResponseEntity<?> summary(@RequestHeader(value = "Authorization", required = false) String authorization) {
        var userOptional = authService.findUserByToken(extractToken(authorization));
        if (userOptional.isEmpty()) {
            return ResponseEntity.status(401).body(Map.of("message", "未登录或 token 无效"));
        }

        List<WorkoutRecord> records = workoutRepository.findByUserOrderByIdAsc(userOptional.get());
        int totalMinutes = records.stream().mapToInt(WorkoutRecord::getDurationMinutes).sum();
        int totalCalories = records.stream().mapToInt(WorkoutRecord::getCalories).sum();

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("count", records.size());
        result.put("totalMinutes", totalMinutes);
        result.put("totalCalories", totalCalories);
        return ResponseEntity.ok(result);
    }

    private String extractToken(String authorization) {
        if (authorization == null || authorization.isBlank()) {
            return "";
        }
        if (authorization.startsWith("Bearer ")) {
            return authorization.substring(7).trim();
        }
        return authorization.trim();
    }
}
