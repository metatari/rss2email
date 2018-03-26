#!/bin/sh

exit_with_error () {
    echo -n "Content-Type: text/plain\r\n\r\n"
    echo "Error: $1."
    exit 1
}

which sudo > /dev/null || exit_with_error "must have sudo installed"

sudo -u $REMOTE_USER -- r2e cgi
