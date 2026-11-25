GET http://127.0.0.1:18765/__control__/reset
HTTP 200
[Asserts]
jsonpath "$.entry_count" == 0

GET http://127.0.0.1:18766/__origin_stats__
HTTP 200
[Captures]
count_before: jsonpath "$.count"

GET http://127.0.0.1:18765/doc
Accept: text/html
HTTP 200
[Asserts]
header "X-Test-Cache-Status" == "MISS"
body contains "AT_HTML_SENTINEL_001"

GET http://127.0.0.1:18765/doc
Accept: text/markdown
HTTP 200
[Asserts]
header "X-Test-Cache-Status" == "MISS"
body contains "AT_MARKDOWN_SENTINEL_001"

GET http://127.0.0.1:18766/__origin_stats__
HTTP 200
[Asserts]
jsonpath "$.count" == 9
