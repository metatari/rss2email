#!/bin/sh

printf "Content-Type: text/html\r\n\r\n"

sudo -u $REMOTE_USER -- r2e cgi
