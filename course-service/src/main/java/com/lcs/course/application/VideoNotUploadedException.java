package com.lcs.course.application;

public class VideoNotUploadedException extends RuntimeException {

    public VideoNotUploadedException(String courseId) {
        super("동영상이 업로드되지 않았습니다: courseId=" + courseId);
    }
}
