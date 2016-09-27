#!/usr/bin/env bash

apt-get update
apt-get install -y software-properties-common
apt-add-repository ppa:ansible/ansible
apt-add-repository ppa:fkrull/deadsnakes
apt-get update
apt-get install -y ansible git python2.7

git clone https://github.com/sperka/lusheeta.git
chown -R vagrant:vagrant lusheeta
cd lusheeta

easy_install pip

pip install backports.ssl_match_hostname
pip install -i requirements.txt
