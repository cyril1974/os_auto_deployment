#!/bin/bash

URL="https://www.google.com"
HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}\n" "$URL")

echo "URL: $URL"
echo "HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "Network OK"
else
    echo "Network FAIL (expected 200, got $HTTP_CODE)"
    exit 1
fi
