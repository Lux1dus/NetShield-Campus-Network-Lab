#!/bin/bash
iptables -F FORWARD
iptables -P FORWARD ACCEPT
