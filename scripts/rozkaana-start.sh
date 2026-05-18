#!/bin/bash
set -a
source /opt/hemanth/rozkaana/.env
set +a

export PYTHONPATH=/opt/hemanth/rozkaana
export PATH=/home/hemanth/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export HOME=/home/hemanth

cd /opt/hemanth/rozkaana
exec make host
