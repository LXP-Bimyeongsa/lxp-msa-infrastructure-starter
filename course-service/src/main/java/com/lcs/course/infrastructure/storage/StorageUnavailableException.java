package com.lcs.course.infrastructure.storage;

public class StorageUnavailableException extends RuntimeException {

    public StorageUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
