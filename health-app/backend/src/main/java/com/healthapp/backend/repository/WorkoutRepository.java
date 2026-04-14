package com.healthapp.backend.repository;

import com.healthapp.backend.model.UserAccount;
import com.healthapp.backend.model.WorkoutRecord;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface WorkoutRepository extends JpaRepository<WorkoutRecord, Long> {
    List<WorkoutRecord> findByUserOrderByIdAsc(UserAccount user);
}
