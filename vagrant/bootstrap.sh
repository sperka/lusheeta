#!/usr/bin/env bash

apt-get update
apt-get install -y software-properties-common
apt-add-repository ppa:ansible/ansible
apt-get update
apt-get install -y ansible git

git clone https://github.com/sperka/lusheeta.git
cd lusheeta