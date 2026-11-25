# HTML first (cold, expect MISS + HTML sentinel)
GET http://127.0.0.1:18765/doc
Accept: text/html
HTTP 200
[Asserts]
header "X-Test-Cache-Status" == "MISS"
header "Content-Type" == "text/html; charset=utf-8"
body contains "AT_HTML_SENTINEL_001"

# Markdown second (warm, correct proxy: new MISS + Markdown sentinel)
GET http://127.0.0.1:18765/doc
Accept: text/markdown
HTTP 200
[Asserts]
header "X-Test-Cache-Status" == "MISS"
header "Content-Type" == "text/markdown; charset=utf-8"
body contains "AT_MARKDOWN_SENTINEL_001"
