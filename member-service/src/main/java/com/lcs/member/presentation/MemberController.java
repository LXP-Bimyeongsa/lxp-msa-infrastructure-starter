package com.lcs.member.presentation;

import com.lcs.member.application.MemberService;
import com.lcs.member.domain.Member;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/members")
public class MemberController {

    private final MemberService memberService;

    public MemberController(MemberService memberService) {
        this.memberService = memberService;
    }

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        return Map.of(
                "service", "member-service",
                "status", "UP",
                "timestamp", Instant.now().toString()
        );
    }

    @PostMapping
    public ResponseEntity<MemberResponse> register(@Valid @RequestBody RegisterRequest request) {
        Member member = memberService.register(request.email(), request.password(), request.name());
        return ResponseEntity.status(HttpStatus.CREATED).body(MemberResponse.from(member));
    }

    @GetMapping("/{memberId}")
    public MemberResponse find(@PathVariable Long memberId) {
        return MemberResponse.from(memberService.findById(memberId));
    }

    public record RegisterRequest(
            @NotBlank @Email String email,
            @NotBlank @Size(min = 8, max = 64) String password,
            @NotBlank @Size(max = 50) String name
    ) {
    }

    // 응답에 passwordHash는 절대 담지 않는다.
    public record MemberResponse(
            Long memberId,
            String email,
            String name,
            String status,
            Instant createdAt
    ) {
        static MemberResponse from(Member member) {
            return new MemberResponse(
                    member.getId(),
                    member.getEmail(),
                    member.getName(),
                    member.getStatus().name(),
                    member.getCreatedAt()
            );
        }
    }
}
