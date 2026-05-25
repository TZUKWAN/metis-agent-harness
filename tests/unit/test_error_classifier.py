from metis.recovery.classifier import ErrorCategory, ErrorClassifier


def test_error_classifier_maps_common_errors():
    classifier = ErrorClassifier()

    assert classifier.classify("timeout while connecting") == ErrorCategory.NETWORK
    assert classifier.classify("HTTP 429 rate limit") == ErrorCategory.RATE_LIMIT
    assert classifier.classify("401 invalid api key") == ErrorCategory.AUTH
    assert classifier.classify("invalid json in tool call") == ErrorCategory.PARSER
    assert classifier.classify("unexpected") == ErrorCategory.UNKNOWN
