package com.health.app.service;

import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class MemoryStore {

    private final Map<String, Map<String, Object>> userProfiles = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> sportRecords = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> sleepRecords = new ConcurrentHashMap<>();
    private final Map<String, List<Map<String, Object>>> dietRecords = new ConcurrentHashMap<>();

    public Map<String, Map<String, Object>> userProfiles() {
        return userProfiles;
    }

    public Map<String, List<Map<String, Object>>> sportRecords() {
        return sportRecords;
    }

    public Map<String, List<Map<String, Object>>> sleepRecords() {
        return sleepRecords;
    }

    public Map<String, List<Map<String, Object>>> dietRecords() {
        return dietRecords;
    }

    public List<Map<String, Object>> getListByUser(Map<String, List<Map<String, Object>>> storage, String userId) {
        return storage.computeIfAbsent(userId, k -> new ArrayList<>());
    }

    public LocalDate today() {
        return LocalDate.now();
    }
}
