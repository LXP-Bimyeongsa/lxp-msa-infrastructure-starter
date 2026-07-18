package com.lcs.course.application;

public class CourseNotFoundException extends RuntimeException {

    public CourseNotFoundException(String courseId) {
        super("강의를 찾을 수 없습니다: id=" + courseId);
    }
}
