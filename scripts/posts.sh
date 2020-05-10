#!/bin/sh

SET=$(seq 1 10)

for i in $SET; do
    http post http://localhost:8080/posts username="haandol" title="title$i" content="content$1"
    sleep 0.5
done