#!/bin/sh

SET=$(seq 1 15)

for i in $SET; do
    http post http://localhost:8080/posts username="haandol" title="haandol$i" content="haandol$1"
    http post http://localhost:8080/posts username="vincent" title="vincent$i" content="vincent$1"
    sleep 0.5
done
