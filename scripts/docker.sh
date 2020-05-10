#!/bin/sh

docker run \
      --rm \
      --attach STDOUT \
      -v ~/.aws/:/root/.aws/:ro \
      --name xray-daemon \
      -p 2000:2000/udp \
      amazon/aws-xray-daemon -o -n ap-northeast-2
