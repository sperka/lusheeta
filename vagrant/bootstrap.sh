#!/usr/bin/env bash

apt-get update
apt-get install -y software-properties-common
apt-add-repository ppa:ansible/ansible
apt-get update
apt-get install -y ansible git

git clone https://github.com/sperka/lusheeta.git
chown -R vagrant:vagrant lusheeta
cd lusheeta

easy_install pip

pip install backports.ssl_match_hostname
pip install -i requirements.txt
