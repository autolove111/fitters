package com.healthapp.backend.service;

import com.healthapp.backend.model.UserAccount;
import com.healthapp.backend.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final Map<String, Long> tokenToUserId = new ConcurrentHashMap<>();

    public AuthService(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    public UserAccount register(String username, String password) {
        userRepository.findByUsername(username).ifPresent(user -> {
            throw new IllegalArgumentException("用户名已存在");
        });

        UserAccount user = new UserAccount();
        user.setUsername(username);
        user.setPasswordHash(hash(password));
        return userRepository.save(user);
    }

    public String login(String username, String password) {
        UserAccount user = userRepository.findByUsername(username)
                .orElseThrow(() -> new IllegalArgumentException("用户名或密码错误"));

        if (!user.getPasswordHash().equals(hash(password))) {
            throw new IllegalArgumentException("用户名或密码错误");
        }

        String token = UUID.randomUUID().toString();
        tokenToUserId.put(token, user.getId());
        return token;
    }

    public Optional<UserAccount> findUserByToken(String token) {
        Long userId = tokenToUserId.get(token);
        if (userId == null) {
            return Optional.empty();
        }
        return userRepository.findById(userId);
    }

    private String hash(String raw) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(raw.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(bytes);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 not available", e);
        }
    }
}
