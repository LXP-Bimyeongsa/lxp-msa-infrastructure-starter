package com.lcs.member;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling // Outbox 릴레이 폴링(D-11)
public class MemberServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(MemberServiceApplication.class, args);
    }
}
