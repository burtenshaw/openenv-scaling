#!/usr/bin/env bash

set -x

salloc --time 1:30:00 \
  --partition=hopper-cpu --nodes=4 --cpus-per-task=2 --mem-per-cpu=100M : \
  --partition=hopper-cpu --nodes=1 --cpus-per-task=4 --mem-per-cpu=200M \
  bash
